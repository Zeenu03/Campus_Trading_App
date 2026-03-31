"""
Database manager for organizing multiple logical databases and tables.

This mirrors the instructor template workflow while using this module's Table
and B+ Tree implementations.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .table import Table
from .transaction import ChangeRecord, TransactionManager, TransactionState
from .wal import WriteAheadLog


class DatabaseManager:
    """Manage logical databases where each database contains named tables."""

    def __init__(self, wal_path: str | None = None):
        self.databases: Dict[str, Dict[str, Table]] = {}

        if wal_path is None:
            module_a_root = os.path.dirname(os.path.dirname(__file__))
            wal_path = os.path.join(module_a_root, "data", "wal.log")

        self.wal = WriteAheadLog(wal_path)
        self.tx_manager = TransactionManager(self.wal, undo_change=self._undo_change)

    @staticmethod
    def _qualified_table_name(db_name: str, table_name: str) -> str:
        return f"{db_name}.{table_name}"

    @staticmethod
    def _split_qualified_table_name(qualified_name: str) -> Tuple[str, str]:
        if "." not in qualified_name:
            raise ValueError(f"Invalid qualified table name: {qualified_name}")
        return qualified_name.split(".", 1)

    @staticmethod
    def _resource_id(db_name: str, table_name: str, key: Any) -> str:
        return f"{db_name}:{table_name}:{key}"

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _init_record_for_schema(table: Table) -> Dict[str, Any]:
        """Build a full record with None defaults for all schema columns."""
        return {column: None for column in table.schema.keys()}

    @staticmethod
    def _next_numeric_key(table: Table, key_name: str) -> int:
        """Return next integer key value based on current table contents."""
        max_key = 0
        for key, _ in table.get_all():
            if isinstance(key, int) and key > max_key:
                max_key = key
        return max_key + 1

    def _build_transaction_record(
        self,
        tx_table: Table,
        tx_id: int,
        listing_id: int,
        seller_id: int,
        buyer_id: int,
        offer_id: int,
        agreed_price: float,
    ) -> Dict[str, Any]:
        record = self._init_record_for_schema(tx_table)

        if "TransactionID" in record:
            record["TransactionID"] = tx_id
        if "ListingID" in record:
            record["ListingID"] = listing_id
        if "SellerID" in record:
            record["SellerID"] = seller_id
        if "BuyerID" in record:
            record["BuyerID"] = buyer_id
        if "OfferID" in record:
            record["OfferID"] = offer_id
        if "AgreedPrice" in record:
            record["AgreedPrice"] = float(agreed_price)
        if "Status" in record:
            record["Status"] = "Scheduled"
        if "CreatedDate" in record and tx_table.schema.get("CreatedDate") is str:
            record["CreatedDate"] = self._iso_now()

        return record

    def _build_notification_record(
        self,
        notification_table: Table,
        notification_id: int,
        recipient_id: int,
        notification_type: str,
        message: str,
        listing_id: int,
        offer_id: int,
        transaction_id: int,
    ) -> Dict[str, Any]:
        record = self._init_record_for_schema(notification_table)

        if "NotificationID" in record:
            record["NotificationID"] = notification_id
        if "RecipientID" in record:
            record["RecipientID"] = recipient_id
        if "NotificationType" in record:
            record["NotificationType"] = notification_type
        if "Title" in record:
            record["Title"] = notification_type
        if "Message" in record:
            record["Message"] = message
        if "RelatedListingID" in record:
            record["RelatedListingID"] = listing_id
        if "RelatedOfferID" in record:
            record["RelatedOfferID"] = offer_id
        if "RelatedTransactionID" in record:
            record["RelatedTransactionID"] = transaction_id
        if "CreatedDate" in record and notification_table.schema.get("CreatedDate") is str:
            record["CreatedDate"] = self._iso_now()

        return record

    def accept_offer_atomic(
        self,
        db_name: str,
        offer_id: int,
        acting_seller_id: int,
        agreed_price: float | None = None,
        include_notifications: bool = True,
        create_declined_transactions: bool = True,
        fail_after_step: int | None = None,
    ) -> Tuple[bool, str]:
        """Phase 2 service: accept an offer with multi-table atomic side effects.

        Steps:
        1) Accept chosen offer.
        2) Decline competing submitted offers on the same listing.
        3) Mark listing as sold.
        4) Insert transaction row(s).
        5) Insert notification row(s) (optional).
        """

        def maybe_fail(step_no: int) -> None:
            if fail_after_step is not None and fail_after_step == step_no:
                raise RuntimeError(f"Injected failure after step {step_no}")

        tx_id = self.begin_transaction()

        try:
            offer_table, msg = self.get_table(db_name, "Offer")
            if offer_table is None:
                raise RuntimeError(msg)

            listing_table, msg = self.get_table(db_name, "Listing")
            if listing_table is None:
                raise RuntimeError(msg)

            transaction_table, msg = self.get_table(db_name, "Transaction")
            if transaction_table is None:
                raise RuntimeError(msg)

            notification_table: Table | None = None
            if include_notifications:
                notification_table, _ = self.get_table(db_name, "Notification")

            target_offer, msg = self.tx_get(tx_id, db_name, "Offer", offer_id)
            if target_offer is None:
                raise RuntimeError(msg if msg != "OK" else f"Offer '{offer_id}' not found")

            if target_offer.get("OfferStatus") != "Submitted":
                raise RuntimeError("Offer is no longer active")

            listing_id = target_offer.get("ListingID")
            buyer_id = target_offer.get("BuyerID")
            offered_price = target_offer.get("OfferedPrice")

            if not isinstance(listing_id, int):
                raise RuntimeError("Offer record missing valid ListingID")
            if not isinstance(buyer_id, int):
                raise RuntimeError("Offer record missing valid BuyerID")

            listing_lock = self._resource_id(db_name, "Listing", listing_id)
            if not self.tx_manager.lock_manager.acquire(tx_id, listing_lock, timeout=1.0):
                raise RuntimeError(f"Could not acquire lock for {listing_lock}")

            listing_row, msg = self.tx_get(tx_id, db_name, "Listing", listing_id)
            if listing_row is None:
                raise RuntimeError(msg if msg != "OK" else f"Listing '{listing_id}' not found")

            seller_id = listing_row.get("SellerID")
            status = listing_row.get("Status")

            if seller_id != acting_seller_id:
                raise RuntimeError("Only the listing owner can accept this offer")
            if status not in {"Listed", "Pending"}:
                raise RuntimeError("Listing is not available for offer acceptance")
            if buyer_id == acting_seller_id:
                raise RuntimeError("Buyer and seller cannot be the same member")

            agreed = float(agreed_price if agreed_price is not None else offered_price)
            if agreed <= 0:
                raise RuntimeError("Agreed price must be > 0")

            accepted_offer = dict(target_offer)
            accepted_offer["OfferStatus"] = "Accepted"
            if "AgreedPrice" in accepted_offer:
                accepted_offer["AgreedPrice"] = agreed
            if "ResponseDate" in accepted_offer and offer_table.schema.get("ResponseDate") is str:
                accepted_offer["ResponseDate"] = self._iso_now()

            ok, msg = self.tx_update(tx_id, db_name, "Offer", offer_id, accepted_offer)
            if not ok:
                raise RuntimeError(msg)
            maybe_fail(1)

            competing: List[Tuple[int, Dict[str, Any]]] = []
            for key, row in offer_table.get_all():
                if (
                    row.get("ListingID") == listing_id
                    and row.get("OfferStatus") == "Submitted"
                    and key != offer_id
                ):
                    competing.append((int(key), dict(row)))

            for other_offer_id, other_row in competing:
                declined_row = dict(other_row)
                declined_row["OfferStatus"] = "Declined"
                if "Reason" in declined_row:
                    declined_row["Reason"] = "Sold to another buyer"
                if "ResponseDate" in declined_row and offer_table.schema.get("ResponseDate") is str:
                    declined_row["ResponseDate"] = self._iso_now()

                ok, msg = self.tx_update(tx_id, db_name, "Offer", other_offer_id, declined_row)
                if not ok:
                    raise RuntimeError(msg)
            maybe_fail(2)

            updated_listing = dict(listing_row)
            updated_listing["Status"] = "Sold"
            if "LastModifiedDate" in updated_listing and listing_table.schema.get("LastModifiedDate") is str:
                updated_listing["LastModifiedDate"] = self._iso_now()

            ok, msg = self.tx_update(tx_id, db_name, "Listing", listing_id, updated_listing)
            if not ok:
                raise RuntimeError(msg)
            maybe_fail(3)

            accepted_txn_id = self._next_numeric_key(transaction_table, transaction_table.search_key)
            accepted_txn_record = self._build_transaction_record(
                transaction_table,
                accepted_txn_id,
                listing_id,
                acting_seller_id,
                buyer_id,
                offer_id,
                agreed,
            )
            ok, msg = self.tx_insert(tx_id, db_name, "Transaction", accepted_txn_record)
            if not ok:
                raise RuntimeError(msg)

            declined_txns: List[Tuple[int, int]] = []
            if create_declined_transactions:
                for other_offer_id, other_row in competing:
                    other_buyer_id = other_row.get("BuyerID")
                    other_price = float(other_row.get("OfferedPrice", 0.0))
                    if not isinstance(other_buyer_id, int):
                        continue

                    next_txn_id = self._next_numeric_key(transaction_table, transaction_table.search_key)
                    other_txn = self._build_transaction_record(
                        transaction_table,
                        next_txn_id,
                        listing_id,
                        acting_seller_id,
                        other_buyer_id,
                        other_offer_id,
                        other_price,
                    )
                    ok, msg = self.tx_insert(tx_id, db_name, "Transaction", other_txn)
                    if not ok:
                        raise RuntimeError(msg)
                    declined_txns.append((other_offer_id, next_txn_id))
            maybe_fail(4)

            if include_notifications and notification_table is not None:
                winner_note_id = self._next_numeric_key(notification_table, notification_table.search_key)
                winner_note = self._build_notification_record(
                    notification_table,
                    winner_note_id,
                    buyer_id,
                    "OfferAccepted",
                    "Your offer has been accepted.",
                    listing_id,
                    offer_id,
                    accepted_txn_id,
                )
                ok, msg = self.tx_insert(tx_id, db_name, "Notification", winner_note)
                if not ok:
                    raise RuntimeError(msg)

                seller_note_id = self._next_numeric_key(notification_table, notification_table.search_key)
                seller_note = self._build_notification_record(
                    notification_table,
                    seller_note_id,
                    acting_seller_id,
                    "TransactionCompleted",
                    "Offer accepted and transaction created.",
                    listing_id,
                    offer_id,
                    accepted_txn_id,
                )
                ok, msg = self.tx_insert(tx_id, db_name, "Notification", seller_note)
                if not ok:
                    raise RuntimeError(msg)

                for other_offer_id, decline_txn_id in declined_txns:
                    other_offer = offer_table.get(other_offer_id)
                    if other_offer is None:
                        continue
                    other_buyer = other_offer.get("BuyerID")
                    if not isinstance(other_buyer, int):
                        continue

                    note_id = self._next_numeric_key(notification_table, notification_table.search_key)
                    lose_note = self._build_notification_record(
                        notification_table,
                        note_id,
                        other_buyer,
                        "OfferDeclined",
                        "Another buyer's offer was accepted on this listing.",
                        listing_id,
                        other_offer_id,
                        decline_txn_id,
                    )
                    ok, msg = self.tx_insert(tx_id, db_name, "Notification", lose_note)
                    if not ok:
                        raise RuntimeError(msg)
            maybe_fail(5)

            ok, msg = self.commit_transaction(tx_id)
            if not ok:
                raise RuntimeError(msg)

            return True, f"Offer '{offer_id}' accepted atomically"

        except Exception as exc:
            self.rollback_transaction(tx_id)
            return False, str(exc)

    def begin_transaction(self) -> str:
        """Start a transaction and return its id."""
        return self.tx_manager.begin()

    def commit_transaction(self, tx_id: str) -> Tuple[bool, str]:
        """Commit an active transaction."""
        try:
            self.tx_manager.commit(tx_id)
            return True, f"Transaction '{tx_id}' committed"
        except (KeyError, RuntimeError) as exc:
            return False, str(exc)

    def rollback_transaction(self, tx_id: str) -> Tuple[bool, str]:
        """Rollback an active transaction and undo its applied changes."""
        try:
            tx_ctx = self.tx_manager.get(tx_id)
            if tx_ctx.state != TransactionState.ACTIVE:
                return False, f"Transaction '{tx_id}' is not active"

            self.tx_manager.rollback(tx_id, apply_undo=True)
            return True, f"Transaction '{tx_id}' rolled back"
        except (KeyError, RuntimeError) as exc:
            return False, str(exc)

    def get_transaction_state(self, tx_id: str) -> Tuple[TransactionState | None, str]:
        """Return transaction state for diagnostics."""
        try:
            return self.tx_manager.get(tx_id).state, "OK"
        except KeyError as exc:
            return None, str(exc)

    def _undo_change(self, change: ChangeRecord) -> None:
        """Apply inverse of a logged change to restore pre-transaction state."""
        db_name, table_name = self._split_qualified_table_name(change.table)
        table, msg = self.get_table(db_name, table_name)
        if table is None:
            raise RuntimeError(f"Rollback failed: {msg}")

        search_key = table.search_key
        before = change.before
        after = change.after

        # INSERT undo: delete inserted row (or restore overwritten row).
        if before is None and after is not None:
            after_key = after.get(search_key, change.key)
            table.delete(after_key)
            return

        # DELETE undo: re-insert old row.
        if before is not None and after is None:
            table.insert(before)
            return

        # UPDATE undo: restore before image, including key-change case.
        if before is not None and after is not None:
            before_key = before.get(search_key)
            after_key = after.get(search_key)

            if before_key != after_key and after_key is not None:
                table.delete(after_key)

            if before_key is None:
                raise RuntimeError("Rollback failed: before-image missing search key")

            table.update(before_key, before)

    def create_database(self, db_name: str) -> Tuple[bool, str]:
        """Create an empty logical database."""
        if not db_name:
            return False, "Database name cannot be empty"

        if db_name in self.databases:
            return False, f"Database '{db_name}' already exists"

        self.databases[db_name] = {}
        return True, f"Database '{db_name}' created"

    def delete_database(self, db_name: str) -> Tuple[bool, str]:
        """Delete a database and all its tables."""
        if db_name not in self.databases:
            return False, f"Database '{db_name}' does not exist"

        del self.databases[db_name]
        return True, f"Database '{db_name}' deleted"

    def list_databases(self) -> List[str]:
        """Return all managed database names."""
        return list(self.databases.keys())

    def create_table(
        self,
        db_name: str,
        table_name: str,
        schema: Dict[str, type],
        order: int = 8,
        search_key: str | None = None,
    ) -> Tuple[bool, str]:
        """Create a table inside an existing database."""
        if db_name not in self.databases:
            return False, f"Database '{db_name}' does not exist"

        if not table_name:
            return False, "Table name cannot be empty"

        if table_name in self.databases[db_name]:
            return False, f"Table '{table_name}' already exists in '{db_name}'"

        try:
            table = Table(table_name, schema, order=order, search_key=search_key)
        except ValueError as exc:
            return False, str(exc)

        self.databases[db_name][table_name] = table
        return True, f"Table '{table_name}' created in database '{db_name}'"

    def delete_table(self, db_name: str, table_name: str) -> Tuple[bool, str]:
        """Delete a table from a database."""
        if db_name not in self.databases:
            return False, f"Database '{db_name}' does not exist"

        if table_name not in self.databases[db_name]:
            return False, f"Table '{table_name}' does not exist in '{db_name}'"

        del self.databases[db_name][table_name]
        return True, f"Table '{table_name}' deleted from '{db_name}'"

    def list_tables(self, db_name: str) -> Tuple[List[str], str]:
        """List table names in a database."""
        if db_name not in self.databases:
            return [], f"Database '{db_name}' does not exist"

        return list(self.databases[db_name].keys()), "OK"

    def get_table(self, db_name: str, table_name: str) -> Tuple[Table | None, str]:
        """Return a table handle for CRUD operations."""
        if db_name not in self.databases:
            return None, f"Database '{db_name}' does not exist"

        table = self.databases[db_name].get(table_name)
        if table is None:
            return None, f"Table '{table_name}' does not exist in '{db_name}'"

        return table, "OK"

    def tx_get(self, tx_id: str, db_name: str, table_name: str, record_id: Any) -> Tuple[Dict[str, Any] | None, str]:
        """Transaction-aware point read."""
        try:
            tx_ctx = self.tx_manager.get(tx_id)
        except KeyError as exc:
            return None, str(exc)

        if tx_ctx.state != TransactionState.ACTIVE:
            return None, f"Transaction '{tx_id}' is not active"

        table, msg = self.get_table(db_name, table_name)
        if table is None:
            return None, msg

        return table.get(record_id), "OK"

    def tx_insert(self, tx_id: str, db_name: str, table_name: str, record: Dict[str, Any]) -> Tuple[bool, str]:
        """Transaction-aware insert (upsert semantics inherited from Table.insert)."""
        table, msg = self.get_table(db_name, table_name)
        if table is None:
            return False, msg

        key = record.get(table.search_key)
        if key is None:
            return False, f"Record must include search key '{table.search_key}'"

        try:
            tx_ctx = self.tx_manager.get(tx_id)
        except KeyError as exc:
            return False, str(exc)

        if tx_ctx.state != TransactionState.ACTIVE:
            return False, f"Transaction '{tx_id}' is not active"

        resource_id = self._resource_id(db_name, table_name, key)
        if not self.tx_manager.lock_manager.acquire(tx_id, resource_id, timeout=1.0):
            return False, f"Could not acquire lock for {resource_id}"

        before = table.get(key)
        ok, insert_msg = table.insert(record)
        if not ok:
            return False, insert_msg

        after = table.get(key)
        self.tx_manager.record_change(
            tx_id,
            self._qualified_table_name(db_name, table_name),
            key,
            "INSERT",
            before,
            after,
        )
        return True, insert_msg

    def tx_update(
        self,
        tx_id: str,
        db_name: str,
        table_name: str,
        record_id: Any,
        new_record: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Transaction-aware update with before/after logging."""
        table, msg = self.get_table(db_name, table_name)
        if table is None:
            return False, msg

        try:
            tx_ctx = self.tx_manager.get(tx_id)
        except KeyError as exc:
            return False, str(exc)

        if tx_ctx.state != TransactionState.ACTIVE:
            return False, f"Transaction '{tx_id}' is not active"

        resource_id = self._resource_id(db_name, table_name, record_id)
        if not self.tx_manager.lock_manager.acquire(tx_id, resource_id, timeout=1.0):
            return False, f"Could not acquire lock for {resource_id}"

        before = table.get(record_id)
        if before is None:
            return False, f"Record with key '{record_id}' not found"

        ok, update_msg = table.update(record_id, new_record)
        if not ok:
            return False, update_msg

        after_key = new_record.get(table.search_key, record_id)
        after = table.get(after_key)
        self.tx_manager.record_change(
            tx_id,
            self._qualified_table_name(db_name, table_name),
            record_id,
            "UPDATE",
            before,
            after,
        )
        return True, update_msg

    def tx_delete(self, tx_id: str, db_name: str, table_name: str, record_id: Any) -> Tuple[bool, str]:
        """Transaction-aware delete with before-image logging."""
        table, msg = self.get_table(db_name, table_name)
        if table is None:
            return False, msg

        try:
            tx_ctx = self.tx_manager.get(tx_id)
        except KeyError as exc:
            return False, str(exc)

        if tx_ctx.state != TransactionState.ACTIVE:
            return False, f"Transaction '{tx_id}' is not active"

        resource_id = self._resource_id(db_name, table_name, record_id)
        if not self.tx_manager.lock_manager.acquire(tx_id, resource_id, timeout=1.0):
            return False, f"Could not acquire lock for {resource_id}"

        before = table.get(record_id)
        if before is None:
            return False, f"Record with key '{record_id}' not found"

        ok, delete_msg = table.delete(record_id)
        if not ok:
            return False, delete_msg

        self.tx_manager.record_change(
            tx_id,
            self._qualified_table_name(db_name, table_name),
            record_id,
            "DELETE",
            before,
            None,
        )
        return True, delete_msg
