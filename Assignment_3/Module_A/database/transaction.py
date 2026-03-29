"""
Transaction manager scaffolding for Assignment 3 Module A.

This module defines transaction lifecycle APIs and in-memory change tracking.
Execution/recovery semantics will be expanded in later phases.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from .lock_manager import LockManager
from .wal import WriteAheadLog


class TransactionState(str, Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass
class ChangeRecord:
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
    """Coordinates transaction begin/commit/rollback and WAL logging."""

    def __init__(self, wal: WriteAheadLog, lock_manager: LockManager | None = None):
        self.wal = wal
        self.lock_manager = lock_manager or LockManager()
        self._lock = threading.RLock()
        self._transactions: Dict[str, TransactionContext] = {}

    def begin(self) -> str:
        """Start a transaction and return its id."""
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
        """Record an in-transaction change and append WAL entry."""
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
        """Commit transaction state and release all held locks."""
        with self._lock:
            ctx = self.get(tx_id)
            if ctx.state != TransactionState.ACTIVE:
                raise RuntimeError(f"Transaction is not active: {tx_id}")

            self.wal.log_commit(tx_id)
            ctx.state = TransactionState.COMMITTED

        self.lock_manager.release_all(tx_id)

    def rollback(self, tx_id: str) -> None:
        """Mark transaction aborted and release all locks.

        NOTE: Undo application to tables/B+Trees will be implemented in later phases.
        """
        with self._lock:
            ctx = self.get(tx_id)
            if ctx.state != TransactionState.ACTIVE:
                return

            self.wal.log_rollback(tx_id)
            ctx.state = TransactionState.ABORTED

        self.lock_manager.release_all(tx_id)
