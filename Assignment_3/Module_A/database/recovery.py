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


class RecoveryManager:
    """Analyzes WAL and prepares REDO/UNDO transaction sets."""

    def __init__(self, wal: WriteAheadLog):
        self.wal = wal

    def analyze(self) -> RecoverySummary:
        """Scan WAL and return committed vs uncommitted transactions."""
        entries = self.wal.read_entries()

        seen: Set[str] = set()
        committed: Set[str] = set()

        for entry in entries:
            tx_id = entry.get("tx_id")
            if not tx_id:
                continue
            seen.add(tx_id)

            if entry.get("type") == "COMMIT":
                committed.add(tx_id)

            if entry.get("type") == "ROLLBACK" and tx_id in committed:
                committed.remove(tx_id)

        uncommitted = seen - committed

        return RecoverySummary(
            total_records=len(entries),
            committed_transactions=sorted(committed),
            uncommitted_transactions=sorted(uncommitted),
        )

    def recover(self) -> Dict[str, Any]:
        """Perform recovery pass (analysis-only in Phase 0)."""
        summary = self.analyze()

        # REDO/UNDO hooks are intentionally deferred to the implementation phase.
        return {
            "status": "ok",
            "total_records": summary.total_records,
            "redo_transactions": summary.committed_transactions,
            "undo_transactions": summary.uncommitted_transactions,
            "applied_redo": 0,
            "applied_undo": 0,
            "note": "Phase 0 scaffold only; REDO/UNDO replay is pending.",
        }
