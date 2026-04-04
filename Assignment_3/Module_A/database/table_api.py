"""Transactional CRUD wrappers over DatabaseManager.

Provides ergonomic, typed access to table operations within a transaction
without exposing the raw tx_* string-based API. The wrappers are pure
delegates — no new locking, no new semantics — so WAL logging, undo, and
isolation all pass through to DatabaseManager unchanged.

Typical usage in a stress script or notebook::

    from database import DatabaseManager
    from database.table_api import DatabaseAPI

    dbm = DatabaseManager(wal_path="data/wal.log")
    api = DatabaseAPI(dbm)

    with api.transaction() as tx_id:
        offers = api.table("campus", "Offer", tx_id)
        listings = api.table("campus", "Listing", tx_id)
        row = offers.get(offer_id)
        offers.update(offer_id, {**row, "OfferStatus": "Accepted"})
        listings.update(listing_id, {**listing, "Status": "Sold"})
    # commits on clean exit, rolls back on exception
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple

from .db_manager import DatabaseManager


class TransactionalTable:
    """CRUD operations on one named table under an active transaction.

    Constructed via ``DatabaseAPI.table(db_name, table_name, tx_id)`` or
    directly. All methods delegate to the underlying ``DatabaseManager.tx_*``
    methods, so the WAL, undo log, and isolation policy are identical to
    calling those methods directly.
    """

    def __init__(
        self,
        dbm: DatabaseManager,
        db_name: str,
        table_name: str,
        tx_id: str,
    ) -> None:
        self._dbm = dbm
        self._db_name = db_name
        self._table_name = table_name
        self._tx_id = tx_id

    # ------------------------------------------------------------------
    # Transactional CRUD
    # ------------------------------------------------------------------

    def get(self, record_id: Any) -> Optional[Dict[str, Any]]:
        """Point-read a record by primary key. Returns ``None`` if not found."""
        row, _ = self._dbm.tx_get(self._tx_id, self._db_name, self._table_name, record_id)
        return row

    def insert(self, record: Dict[str, Any]) -> Tuple[bool, str]:
        """Insert *record* and log the change to the WAL."""
        return self._dbm.tx_insert(self._tx_id, self._db_name, self._table_name, record)

    def update(self, record_id: Any, new_record: Dict[str, Any]) -> Tuple[bool, str]:
        """Update the row at *record_id* with *new_record* and log to WAL."""
        return self._dbm.tx_update(self._tx_id, self._db_name, self._table_name, record_id, new_record)

    def delete(self, record_id: Any) -> Tuple[bool, str]:
        """Delete the row at *record_id* and log the before-image to WAL."""
        return self._dbm.tx_delete(self._tx_id, self._db_name, self._table_name, record_id)

    # ------------------------------------------------------------------
    # Read-only helpers (bypass the transaction; safe for reads)
    # ------------------------------------------------------------------

    def get_all(self) -> List[Tuple[Any, Dict[str, Any]]]:
        """Return all (key, record) pairs sorted by key (read-only, no WAL entry)."""
        table, _ = self._dbm.get_table(self._db_name, self._table_name)
        if table is None:
            return []
        return table.get_all()

    def count(self) -> int:
        """Return the number of rows in the table."""
        return len(self.get_all())

    def __repr__(self) -> str:
        return (
            f"TransactionalTable(db={self._db_name!r}, table={self._table_name!r}, "
            f"tx={self._tx_id!r})"
        )


class DatabaseAPI:
    """Single-import convenience wrapper: transaction lifecycle + table factory.

    Wraps a ``DatabaseManager`` and exposes the transaction lifecycle (begin,
    commit, rollback, context manager) alongside a ``table()`` factory that
    returns ``TransactionalTable`` instances bound to the current transaction.

    Example::

        api = DatabaseAPI(dbm)
        with api.transaction() as tx_id:
            offers = api.table("campus", "Offer", tx_id)
            listings = api.table("campus", "Listing", tx_id)
            row = offers.get(offer_id)
            offers.update(offer_id, {**row, "OfferStatus": "Accepted"})
    """

    def __init__(self, dbm: DatabaseManager) -> None:
        self._dbm = dbm

    # ------------------------------------------------------------------
    # Table factory
    # ------------------------------------------------------------------

    def table(self, db_name: str, table_name: str, tx_id: str) -> TransactionalTable:
        """Return a TransactionalTable bound to *tx_id* for use inside a transaction."""
        return TransactionalTable(self._dbm, db_name, table_name, tx_id)

    # ------------------------------------------------------------------
    # Transaction lifecycle (passthroughs)
    # ------------------------------------------------------------------

    def begin(self) -> str:
        """Start a new transaction and return its ID."""
        return self._dbm.begin_transaction()

    def commit(self, tx_id: str) -> Tuple[bool, str]:
        """Commit *tx_id*."""
        return self._dbm.commit_transaction(tx_id)

    def rollback(self, tx_id: str) -> Tuple[bool, str]:
        """Roll back *tx_id*, undoing all its changes."""
        return self._dbm.rollback_transaction(tx_id)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @contextmanager
    def transaction(self) -> Generator[str, None, None]:
        """Context manager: acquires the serial lock, begins a transaction,
        yields the ``tx_id``, and commits on clean exit or rolls back on error.

        Usage::

            with api.transaction() as tx_id:
                api.table("campus", "Offer", tx_id).update(oid, new_row)
            # committed; any exception triggers rollback instead
        """
        with self._dbm.isolation():
            tx_id = self._dbm.begin_transaction()
            try:
                yield tx_id
                self._dbm.commit_transaction(tx_id)
            except Exception:
                self._dbm.rollback_transaction(tx_id)
                raise
