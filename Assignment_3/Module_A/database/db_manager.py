"""
Database manager for organizing multiple logical databases and tables.

The DatabaseManager is intentionally schema-neutral: it knows nothing about
campus-specific table names or column layouts. Domain workflows (e.g.
accept_offer_atomic) live in campus_workflow.py instead.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, List, Tuple

from .table import Table
from .transaction import ChangeRecord, TransactionContext, TransactionManager, TransactionState
from .wal import WriteAheadLog


class DatabaseManager:
    """Manage logical databases where each database contains named tables.

    Isolation level: SERIALIZABLE — a single global mutex (``_serial_lock``)
    is held for the full duration of each transactional operation so concurrent
    callers execute strictly one after another with no interleaving.

    This class is schema-neutral. Campus-specific domain workflows
    (e.g. accept_offer_atomic) live in ``campus_workflow`` and call
    ``isolation()`` to acquire the lock before beginning a transaction.
    """

    def __init__(self, wal_path: str | None = None):
        self.databases: Dict[str, Dict[str, Table]] = {}

        if wal_path is None:
            module_a_root = os.path.dirname(os.path.dirname(__file__))
            wal_path = os.path.join(module_a_root, "data", "wal.log")

        self.wal = WriteAheadLog(wal_path)
        self.tx_manager = TransactionManager(self.wal, undo_change=self._undo_change)
        # Global serialization mutex: ensures at most one transaction is live
        # at any point in time across all threads (serializable isolation).
        self._serial_lock = threading.Lock()

    @contextmanager
    def serialized_transaction(self) -> Generator[str, None, None]:
        """Context manager: acquire the serial lock, begin a transaction, yield
        the ``tx_id``, then commit on clean exit or rollback on exception.

        Usage::

            with dbm.serialized_transaction() as tx_id:
                dbm.tx_insert(tx_id, "mydb", "MyTable", record)
                # commit happens automatically on clean exit
            # rollback happens automatically on any exception

        The global lock is held for the entire duration so no other thread can
        begin a transaction until this one completes — serializable isolation.
        """
        with self._serial_lock:
            tx_id = self.begin_transaction()
            try:
                yield tx_id
                self.commit_transaction(tx_id)
            except Exception:
                self.rollback_transaction(tx_id)
                raise

    @contextmanager
    def isolation(self) -> Generator[None, None, None]:
        """Acquire the global serial lock for the duration of the block.

        Use this when you need to manually manage begin/commit/rollback within
        the serializable isolation boundary (e.g. in domain workflow functions)::

            with dbm.isolation():
                tx_id = dbm.begin_transaction()
                try:
                    dbm.tx_update(tx_id, db, table, key, row)
                    dbm.commit_transaction(tx_id)
                except Exception:
                    dbm.rollback_transaction(tx_id)
                    raise

        Unlike ``serialized_transaction``, this does not begin or commit a
        transaction automatically — the caller controls the lifecycle.
        """
        with self._serial_lock:
            yield

    def run_transaction(self, fn: Callable[[str], Any], *args: Any, **kwargs: Any) -> Tuple[bool, str, Any]:
        """Execute *fn(tx_id, *args, **kwargs)* inside a serialized transaction.

        Returns ``(ok, message, result)`` where *result* is whatever *fn* returns.
        The global serial lock is held for the full duration of *fn*, guaranteeing
        serializable isolation even when called concurrently from multiple threads.
        """
        with self._serial_lock:
            tx_id = self.begin_transaction()
            try:
                result = fn(tx_id, *args, **kwargs)
                ok, msg = self.commit_transaction(tx_id)
                return ok, msg, result
            except Exception as exc:
                self.rollback_transaction(tx_id)
                return False, str(exc), None

    @staticmethod
    def _qualified_table_name(db_name: str, table_name: str) -> str:
        return f"{db_name}.{table_name}"

    @staticmethod
    def _split_qualified_table_name(qualified_name: str) -> Tuple[str, str]:
        """Split a qualified table name into database name and table name."""
        if "." not in qualified_name:
            raise ValueError(f"Invalid qualified table name: {qualified_name}")
        return qualified_name.split(".", 1)

    def _active_tx(self, tx_id: str) -> Tuple[TransactionContext | None, str]:
        """Return ``(context, \"OK\")`` or ``(None, error_message)``."""
        try:
            ctx = self.tx_manager.get(tx_id)
        except KeyError as exc:
            return None, str(exc)
        if ctx.state != TransactionState.ACTIVE:
            return None, f"Transaction '{tx_id}' is not active"
        return ctx, "OK"

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
        """Transaction-aware point read (no row lock; isolation is global serialization)."""
        _, err = self._active_tx(tx_id)
        if err != "OK":
            return None, err

        table, msg = self.get_table(db_name, table_name)
        if table is None:
            return None, msg

        return table.get(record_id), "OK"

    def tx_insert(self, tx_id: str, db_name: str, table_name: str, record: Dict[str, Any]) -> Tuple[bool, str]:
        """Transaction-aware insert (upsert semantics inherited from Table.insert)."""
        _, err = self._active_tx(tx_id)
        if err != "OK":
            return False, err

        table, msg = self.get_table(db_name, table_name)
        if table is None:
            return False, msg

        key = record.get(table.search_key)
        if key is None:
            return False, f"Record must include search key '{table.search_key}'"

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
        _, err = self._active_tx(tx_id)
        if err != "OK":
            return False, err

        table, msg = self.get_table(db_name, table_name)
        if table is None:
            return False, msg

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
        _, err = self._active_tx(tx_id)
        if err != "OK":
            return False, err

        table, msg = self.get_table(db_name, table_name)
        if table is None:
            return False, msg

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
