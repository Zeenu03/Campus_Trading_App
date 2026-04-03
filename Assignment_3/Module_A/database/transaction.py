"""Transaction lifecycle, in-memory change list, and WAL integration."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List

from .wal import WriteAheadLog


class TransactionState(str, Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass
class ChangeRecord:
    """One row-level change: used for rollback undo and recovery replay."""

    table: str
    key: Any
    operation: str
    before: Dict[str, Any] | None
    after: Dict[str, Any] | None


@dataclass
class TransactionContext:
    tx_id: str
    state: TransactionState = TransactionState.ACTIVE
    changes: List[ChangeRecord] = field(default_factory=list)


class TransactionManager:
    """BEGIN / COMMIT / ROLLBACK with WAL logging.

    Cross-transaction isolation is enforced by ``DatabaseManager._serial_lock``;
    this class only serializes access to its own ``_transactions`` map.
    """

    def __init__(
        self,
        wal: WriteAheadLog,
        undo_change: Callable[[ChangeRecord], None] | None = None,
    ) -> None:
        self.wal = wal
        self._undo_change = undo_change
        self._lock = threading.RLock()
        self._transactions: Dict[str, TransactionContext] = {} # tx_id -> TransactionContext

    def begin(self) -> str:
        """Create context, append WAL BEGIN, return ``tx_id``."""
        tx_id = f"T-{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._transactions[tx_id] = TransactionContext(tx_id=tx_id)
            self.wal.log_begin(tx_id)
        return tx_id

    def get(self, tx_id: str) -> TransactionContext:
        with self._lock:
            ctx = self._transactions.get(tx_id)
            if ctx is None:
                raise KeyError(f"Unknown transaction id: {tx_id}")
            return ctx

    def record_change(
        self,
        tx_id: str,
        table: str,
        key: Any,
        operation: str,
        before: Dict[str, Any] | None,
        after: Dict[str, Any] | None,
    ) -> None:
        with self._lock:
            ctx = self.get(tx_id)
            if ctx.state != TransactionState.ACTIVE:
                raise RuntimeError(f"Transaction is not active: {tx_id}")

            change = ChangeRecord(
                table=table,
                key=key,
                operation=operation,
                before=before,
                after=after,
            )
            ctx.changes.append(change)
            self.wal.log_change(tx_id, table, key, operation, before, after)

    def commit(self, tx_id: str) -> None:
        with self._lock:
            ctx = self.get(tx_id)
            if ctx.state != TransactionState.ACTIVE:
                raise RuntimeError(f"Transaction is not active: {tx_id}")

            self.wal.log_commit(tx_id)
            ctx.state = TransactionState.COMMITTED

    def rollback(self, tx_id: str, apply_undo: bool = True) -> None:
        with self._lock:
            ctx = self.get(tx_id)
            if ctx.state != TransactionState.ACTIVE:
                return
            changes_snapshot = list(ctx.changes)

        if apply_undo and changes_snapshot:
            if self._undo_change is None:
                raise RuntimeError("No undo handler configured for physical rollback")
            for change in reversed(changes_snapshot):
                self._undo_change(change)

        with self._lock:
            ctx = self.get(tx_id)
            if ctx.state != TransactionState.ACTIVE:
                return
            self.wal.log_rollback(tx_id)
            ctx.state = TransactionState.ABORTED
