"""Campus Trading multi-table workflow: accept-offer atomic transaction.

This module contains campus-specific domain logic that sits on top of the
generic DatabaseManager engine. It uses the tx_* API to implement the
accept-offer business flow, which touches Offer, Listing, Transaction,
and Notification tables in one atomic unit.

Separating this from DatabaseManager keeps the engine schema-neutral.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .db_manager import DatabaseManager
from .table import Table


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _init_record(table: Table) -> Dict[str, Any]:
    """Build a dict with None defaults for every column in *table*'s schema."""
    return {col: None for col in table.schema}


def _next_autoinc_key(table: Table) -> int:
    """Return one past the current maximum integer primary key in *table*."""
    max_key = 0
    for key, _ in table.get_all():
        if isinstance(key, int) and key > max_key:
            max_key = key
    return max_key + 1


def _build_transaction_record(
    tx_table: Table,
    tx_id: int,
    listing_id: int,
    seller_id: int,
    buyer_id: int,
    offer_id: int,
    agreed_price: float,
) -> Dict[str, Any]:
    record = _init_record(tx_table)
    for col, val in (
        ("TransactionID", tx_id),
        ("ListingID", listing_id),
        ("SellerID", seller_id),
        ("BuyerID", buyer_id),
        ("OfferID", offer_id),
        ("AgreedPrice", float(agreed_price)),
        ("Status", "Scheduled"),
    ):
        if col in record:
            record[col] = val
    if "CreatedDate" in record and tx_table.schema.get("CreatedDate") is str:
        record["CreatedDate"] = _iso_now()
    return record


def _build_notification_record(
    notif_table: Table,
    notif_id: int,
    recipient_id: int,
    notif_type: str,
    message: str,
    listing_id: int,
    offer_id: int,
    transaction_id: int,
) -> Dict[str, Any]:
    record = _init_record(notif_table)
    for col, val in (
        ("NotificationID", notif_id),
        ("RecipientID", recipient_id),
        ("NotificationType", notif_type),
        ("Title", notif_type),
        ("Message", message),
        ("RelatedListingID", listing_id),
        ("RelatedOfferID", offer_id),
        ("RelatedTransactionID", transaction_id),
    ):
        if col in record:
            record[col] = val
    if "CreatedDate" in record and notif_table.schema.get("CreatedDate") is str:
        record["CreatedDate"] = _iso_now()
    return record


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def accept_offer_atomic(
    dbm: DatabaseManager,
    db_name: str,
    offer_id: int,
    acting_seller_id: int,
    agreed_price: Optional[float] = None,
    include_notifications: bool = True,
    create_declined_transactions: bool = True,
    fail_after_step: Optional[int] = None,
) -> Tuple[bool, str]:
    """Accept an offer atomically across Offer, Listing, Transaction, and Notification.

    Acquires the global serial lock via ``dbm.isolation()``, then runs a
    single transaction that:

    1. Marks the chosen offer Accepted.
    2. Marks competing Submitted offers on the same listing Declined.
    3. Marks the listing Sold.
    4. Inserts Transaction row(s).
    5. Inserts Notification row(s) if *include_notifications* is True.

    Args:
        dbm: The DatabaseManager instance owning the campus tables.
        db_name: Logical database name (e.g. ``"campus"``).
        offer_id: Primary key of the offer to accept.
        acting_seller_id: Must match the listing's SellerID.
        agreed_price: Override the offered price; defaults to ``OfferedPrice``.
        include_notifications: Insert Notification rows for buyer/seller.
        create_declined_transactions: Insert Transaction rows for declined offers.
        fail_after_step: Inject a ``RuntimeError`` after step *N* (1-5) for
            ACID atomicity testing. ``None`` means no injection.

    Returns:
        ``(True, success_message)`` on commit, ``(False, error_message)`` on rollback.
    """
    def _maybe_fail(step_no: int) -> None:
        if fail_after_step is not None and fail_after_step == step_no:
            raise RuntimeError(f"Injected failure after step {step_no}")

    with dbm.isolation():
        return _accept_offer_inner(
            dbm=dbm,
            db_name=db_name,
            offer_id=offer_id,
            acting_seller_id=acting_seller_id,
            agreed_price=agreed_price,
            include_notifications=include_notifications,
            create_declined_transactions=create_declined_transactions,
            maybe_fail=_maybe_fail,
        )


def _accept_offer_inner(
    dbm: DatabaseManager,
    db_name: str,
    offer_id: int,
    acting_seller_id: int,
    agreed_price: Optional[float],
    include_notifications: bool,
    create_declined_transactions: bool,
    maybe_fail: Callable[[int], None],
) -> Tuple[bool, str]:
    """Inner implementation — called while the serial lock is held."""
    tx_id = dbm.begin_transaction()
    try:
        offer_table, msg = dbm.get_table(db_name, "Offer")
        if offer_table is None:
            raise RuntimeError(msg)

        listing_table, msg = dbm.get_table(db_name, "Listing")
        if listing_table is None:
            raise RuntimeError(msg)

        transaction_table, msg = dbm.get_table(db_name, "Transaction")
        if transaction_table is None:
            raise RuntimeError(msg)

        notif_table: Optional[Table] = None
        if include_notifications:
            notif_table, _ = dbm.get_table(db_name, "Notification")

        # --- Validate offer ---
        target_offer, msg = dbm.tx_get(tx_id, db_name, "Offer", offer_id)
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

        # --- Validate listing ---
        listing_row, msg = dbm.tx_get(tx_id, db_name, "Listing", listing_id)
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

        # Step 1: Accept the chosen offer
        accepted_offer = dict(target_offer)
        accepted_offer["OfferStatus"] = "Accepted"
        if "AgreedPrice" in accepted_offer:
            accepted_offer["AgreedPrice"] = agreed
        if "ResponseDate" in accepted_offer and offer_table.schema.get("ResponseDate") is str:
            accepted_offer["ResponseDate"] = _iso_now()

        ok, msg = dbm.tx_update(tx_id, db_name, "Offer", offer_id, accepted_offer)
        if not ok:
            raise RuntimeError(msg)
        maybe_fail(1)

        # Step 2: Decline competing submitted offers on the same listing
        competing: List[Tuple[int, Dict[str, Any]]] = []
        for key, row in offer_table.get_all():
            if (
                row.get("ListingID") == listing_id
                and row.get("OfferStatus") == "Submitted"
                and key != offer_id
            ):
                competing.append((int(key), dict(row)))

        for other_offer_id, other_row in competing:
            declined = dict(other_row)
            declined["OfferStatus"] = "Declined"
            if "Reason" in declined:
                declined["Reason"] = "Sold to another buyer"
            if "ResponseDate" in declined and offer_table.schema.get("ResponseDate") is str:
                declined["ResponseDate"] = _iso_now()
            ok, msg = dbm.tx_update(tx_id, db_name, "Offer", other_offer_id, declined)
            if not ok:
                raise RuntimeError(msg)
        maybe_fail(2)

        # Step 3: Mark listing as Sold
        updated_listing = dict(listing_row)
        updated_listing["Status"] = "Sold"
        if "LastModifiedDate" in updated_listing and listing_table.schema.get("LastModifiedDate") is str:
            updated_listing["LastModifiedDate"] = _iso_now()
        ok, msg = dbm.tx_update(tx_id, db_name, "Listing", listing_id, updated_listing)
        if not ok:
            raise RuntimeError(msg)
        maybe_fail(3)

        # Step 4: Insert Transaction row(s)
        accepted_txn_id = _next_autoinc_key(transaction_table)
        ok, msg = dbm.tx_insert(
            tx_id, db_name, "Transaction",
            _build_transaction_record(
                transaction_table, accepted_txn_id,
                listing_id, acting_seller_id, buyer_id, offer_id, agreed,
            ),
        )
        if not ok:
            raise RuntimeError(msg)

        declined_txns: List[Tuple[int, int]] = []
        if create_declined_transactions:
            for other_offer_id, other_row in competing:
                other_buyer_id = other_row.get("BuyerID")
                other_price = float(other_row.get("OfferedPrice", 0.0))
                if not isinstance(other_buyer_id, int):
                    continue
                next_txn_id = _next_autoinc_key(transaction_table)
                ok, msg = dbm.tx_insert(
                    tx_id, db_name, "Transaction",
                    _build_transaction_record(
                        transaction_table, next_txn_id,
                        listing_id, acting_seller_id, other_buyer_id, other_offer_id, other_price,
                    ),
                )
                if not ok:
                    raise RuntimeError(msg)
                declined_txns.append((other_offer_id, next_txn_id))
        maybe_fail(4)

        # Step 5: Insert Notification rows
        if include_notifications and notif_table is not None:
            winner_note_id = _next_autoinc_key(notif_table)
            ok, msg = dbm.tx_insert(
                tx_id, db_name, "Notification",
                _build_notification_record(
                    notif_table, winner_note_id, buyer_id,
                    "OfferAccepted", "Your offer has been accepted.",
                    listing_id, offer_id, accepted_txn_id,
                ),
            )
            if not ok:
                raise RuntimeError(msg)

            seller_note_id = _next_autoinc_key(notif_table)
            ok, msg = dbm.tx_insert(
                tx_id, db_name, "Notification",
                _build_notification_record(
                    notif_table, seller_note_id, acting_seller_id,
                    "TransactionCompleted", "Offer accepted and transaction created.",
                    listing_id, offer_id, accepted_txn_id,
                ),
            )
            if not ok:
                raise RuntimeError(msg)

            for other_offer_id, decline_txn_id in declined_txns:
                other_offer = offer_table.get(other_offer_id)
                if other_offer is None:
                    continue
                other_buyer = other_offer.get("BuyerID")
                if not isinstance(other_buyer, int):
                    continue
                note_id = _next_autoinc_key(notif_table)
                ok, msg = dbm.tx_insert(
                    tx_id, db_name, "Notification",
                    _build_notification_record(
                        notif_table, note_id, other_buyer,
                        "OfferDeclined", "Another buyer's offer was accepted on this listing.",
                        listing_id, other_offer_id, decline_txn_id,
                    ),
                )
                if not ok:
                    raise RuntimeError(msg)
        maybe_fail(5)

        ok, msg = dbm.commit_transaction(tx_id)
        if not ok:
            raise RuntimeError(msg)
        return True, f"Offer '{offer_id}' accepted atomically"

    except Exception as exc:
        dbm.rollback_transaction(tx_id)
        return False, str(exc)
