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
from typing import Any, Callable, Dict, List

from .lock_manager import LockManager
from .wal import WriteAheadLog


class TransactionState(str, Enum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass
# 
class ChangeRecord:
    """
    Represents a single row-level change within a transaction.
    This is a simple structure for tracking changes in-memory and logging to WAL(WriteAheadLog).
    The 'before' and 'after' fields can be used for REDO/UNDO purposes in later phases.
    
    Args:
    table: The name of the table being modified.
    key: Row/ojbect identifier for the change.
    operation: Type of change (e.g., "INSERT", "UPDATE", "DELETE").
    before: The state of the row before the change (None for INSERT).
    after: The state of the row after the change (None for DELETE).
    
    """

    table: str
    key: Any
    operation: str
    before: Dict[str, Any] | None
    after: Dict[str, Any] | None


@dataclass
class TransactionContext:
    """
    complete runtime context for a transaction, including state and in-memory change tracking.
    
    Args:
    tx_id: Unique identifier for the transaction.
    state: Current state of the transaction (ACTIVE, COMMITTED, ABORTED).
    changes: List of ChangeRecord objects representing the changes made in this transaction.
    """
    tx_id: str
    state: TransactionState = TransactionState.ACTIVE
    changes: List[ChangeRecord] = field(default_factory=list)


class TransactionManager:
    """
    Coordinates transaction begin/commit/rollback and WAL logging.
    
    This is a simplified transaction manager for educational purposes. It does not implement isolation levels, locking, or recovery logic yet. Those will be added in later phases.
    
    Args:
    wal: An instance of WriteAheadLog for logging transaction events and changes.
    lock_manager: An instance of LockManager for managing locks (optional).
    _lock: A threading.RLock to protect internal transaction state.
    _transactions: A dictionary mapping transaction IDs to their TransactionContext.
    
    RLock is used to allow re-entrant access to transaction context within the same thread, which can be useful for nested operations in later phases.
    """

    def __init__(
        self,
        wal: WriteAheadLog,
        lock_manager: LockManager | None = None,
        undo_change: Callable[[ChangeRecord], None] | None = None,
    ):
        
        """Initialize the TransactionManager with a WriteAheadLog and optional LockManager."""
        
        self.wal = wal
        self.lock_manager = lock_manager or LockManager()
        self._undo_change = undo_change
        self._lock = threading.RLock()
        self._transactions: Dict[str, TransactionContext] = {} # tx_id -> TransactionContext

    def set_undo_handler(self, undo_change: Callable[[ChangeRecord], None] | None) -> None:
        """Register or replace the physical undo callback used during rollback."""
        self._undo_change = undo_change

    def begin(self) -> str:
        """Start a transaction and return its id.
        
        Contex is created before WAL begin call in same critical section to ensure correct ordering of WAL entries and in-memory state.
        """
        tx_id = f"T-{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._transactions[tx_id] = TransactionContext(tx_id=tx_id)
            self.wal.log_begin(tx_id)
        return tx_id

    def get(self, tx_id: str) -> TransactionContext:
        """Get the TransactionContext for a given transaction id, or raise KeyError if not found."""
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
        """
        Record an in-transaction change and append WAL entry.
        
        In-memory append happens before WAL logging to ensure that the TransactionContext always reflects all changes that have been logged, even if the WAL append fails (e.g., due to disk issues).
        """
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

    def rollback(self, tx_id: str, apply_undo: bool = True) -> None:
        """Rollback an active transaction and optionally apply physical undo."""
        with self._lock:
            ctx = self.get(tx_id)
            if ctx.state != TransactionState.ACTIVE:
                return
            changes_snapshot = list(ctx.changes)

        if apply_undo and changes_snapshot:
            if self._undo_change is None:
                raise RuntimeError("No undo handler configured for physical rollback")

            # Reverse order preserves correctness for dependent updates/deletes.
            # _undo_change in this case is expected to be a physical undo that directly reverts the change on the database, so we apply it before logging the ROLLBACK to ensure that the WAL reflects the actual state changes.
            for change in reversed(changes_snapshot):
                self._undo_change(change)

        # Log the rollback and update state within the same critical section to ensure consistency of in-memory state and WAL entries.
        with self._lock:
            ctx = self.get(tx_id)
            if ctx.state != TransactionState.ACTIVE:
                return
            self.wal.log_rollback(tx_id)
            ctx.state = TransactionState.ABORTED

        self.lock_manager.release_all(tx_id)
