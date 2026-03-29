"""
Crash recovery scaffolding for Assignment 3 Module A.

Phase 0 provides log analysis and a recovery summary. REDO/UNDO application
hooks will be implemented in a later phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set

from .wal import WriteAheadLog


@dataclass
class RecoverySummary:
    total_records: int
    committed_transactions: List[str]
    uncommitted_transactions: List[str]
    rolled_back_transactions: List[str]


class RecoveryManager:
    """Analyzes WAL and prepares REDO/UNDO transaction sets."""

    def __init__(self, wal: WriteAheadLog):
        self.wal = wal

    def analyze(self) -> RecoverySummary:
        """Scan WAL and return committed vs uncommitted transactions."""
        entries = self.wal.read_entries()

        seen: Set[str] = set()
        committed: Set[str] = set()
        rolled_back: Set[str] = set()

        for entry in entries:
            tx_id = entry.get("tx_id")
            if not tx_id:
                continue
            seen.add(tx_id)

            entry_type = entry.get("type")

            if entry_type == "COMMIT":
                committed.add(tx_id)

            if entry_type == "ROLLBACK":
                rolled_back.add(tx_id)
                committed.discard(tx_id)

        # Transactions that ended with explicit rollback are not crash-uncommitted.
        uncommitted = seen - committed - rolled_back

        return RecoverySummary(
            total_records=len(entries),
            committed_transactions=sorted(committed),
            uncommitted_transactions=sorted(uncommitted),
            rolled_back_transactions=sorted(rolled_back),
        )

    def recover(self) -> Dict[str, Any]:
        """Return recovery plan summary without mutating table state."""
        summary = self.analyze()
        return {
            "status": "ok",
            "total_records": summary.total_records,
            "redo_transactions": summary.committed_transactions,
            "undo_transactions": summary.uncommitted_transactions,
            "rolled_back_transactions": summary.rolled_back_transactions,
            "applied_redo": 0,
            "applied_undo": 0,
            "note": "Analysis only. Use recover_into(db_manager) to apply REDO/UNDO.",
        }

    @staticmethod
    def _split_qualified_table_name(qualified_name: str) -> tuple[str, str]:
        if "." not in qualified_name:
            raise ValueError(f"Invalid qualified table name: {qualified_name}")
        return qualified_name.split(".", 1)

    @staticmethod
    def _change_entries_for_tx(entries: List[Dict[str, Any]], tx_id: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for entry in entries:
            if entry.get("tx_id") != tx_id:
                continue
            if entry.get("type") in {"INSERT", "UPDATE", "DELETE"}:
                out.append(entry)
        return out

    @staticmethod
    def _apply_row_image(table: Any, key_field: str, key_value: Any, row_image: Dict[str, Any]) -> None:
        """Idempotently apply a full row image at a key."""
        current = table.get(key_value)
        if current is None:
            table.insert(row_image)
            return
        if current == row_image:
            return
        table.update(key_value, row_image)

    @staticmethod
    def _redo_change(db_manager: Any, entry: Dict[str, Any]) -> int:
        table_name = entry.get("table")
        before = entry.get("before")
        after = entry.get("after")

        if not isinstance(table_name, str):
            return 0

        db_name, t_name = RecoveryManager._split_qualified_table_name(table_name)
        table, msg = db_manager.get_table(db_name, t_name)
        if table is None:
            raise RuntimeError(f"REDO failed: {msg}")

        key_field = table.search_key
        key = entry.get("key")

        if entry.get("type") == "INSERT":
            if not isinstance(after, dict):
                return 0
            target_key = after.get(key_field, key)
            RecoveryManager._apply_row_image(table, key_field, target_key, after)
            return 1

        if entry.get("type") == "UPDATE":
            if not isinstance(after, dict):
                return 0
            old_key = before.get(key_field, key) if isinstance(before, dict) else key
            new_key = after.get(key_field, old_key)

            if old_key != new_key and table.get(old_key) is not None:
                table.delete(old_key)

            RecoveryManager._apply_row_image(table, key_field, new_key, after)
            return 1

        if entry.get("type") == "DELETE":
            del_key = key
            if isinstance(before, dict):
                del_key = before.get(key_field, del_key)
            if table.get(del_key) is not None:
                table.delete(del_key)
            return 1

        return 0

    @staticmethod
    def _undo_change(db_manager: Any, entry: Dict[str, Any]) -> int:
        table_name = entry.get("table")
        before = entry.get("before")
        after = entry.get("after")

        if not isinstance(table_name, str):
            return 0

        db_name, t_name = RecoveryManager._split_qualified_table_name(table_name)
        table, msg = db_manager.get_table(db_name, t_name)
        if table is None:
            raise RuntimeError(f"UNDO failed: {msg}")

        key_field = table.search_key
        key = entry.get("key")

        # Undo INSERT => delete inserted image.
        if before is None and isinstance(after, dict):
            inserted_key = after.get(key_field, key)
            if table.get(inserted_key) is not None:
                table.delete(inserted_key)
            return 1

        # Undo DELETE => restore before image.
        if isinstance(before, dict) and after is None:
            restore_key = before.get(key_field, key)
            RecoveryManager._apply_row_image(table, key_field, restore_key, before)
            return 1

        # Undo UPDATE => restore before image, handling key moves.
        if isinstance(before, dict) and isinstance(after, dict):
            before_key = before.get(key_field, key)
            after_key = after.get(key_field, before_key)
            if before_key != after_key and table.get(after_key) is not None:
                table.delete(after_key)

            RecoveryManager._apply_row_image(table, key_field, before_key, before)
            return 1

        return 0

    def recover_into(self, db_manager: Any) -> Dict[str, Any]:
        """Apply REDO/UNDO to a DatabaseManager-like object using WAL history."""
        summary = self.analyze()
        entries = self.wal.read_entries()

        applied_redo = 0
        applied_undo = 0

        # REDO committed transactions in log order.
        for tx_id in summary.committed_transactions:
            tx_entries = self._change_entries_for_tx(entries, tx_id)
            for entry in tx_entries:
                applied_redo += self._redo_change(db_manager, entry)

        # UNDO crash-uncommitted transactions in reverse log order.
        for tx_id in summary.uncommitted_transactions:
            tx_entries = self._change_entries_for_tx(entries, tx_id)
            for entry in reversed(tx_entries):
                applied_undo += self._undo_change(db_manager, entry)

        return {
            "status": "ok",
            "total_records": summary.total_records,
            "redo_transactions": summary.committed_transactions,
            "undo_transactions": summary.uncommitted_transactions,
            "rolled_back_transactions": summary.rolled_back_transactions,
            "applied_redo": applied_redo,
            "applied_undo": applied_undo,
            "note": "REDO/UNDO replay applied.",
        }
