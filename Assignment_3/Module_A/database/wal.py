"""
Write-ahead logging (WAL) scaffolding for Assignment 3 Module A.

This module provides a simple JSONL append-only log with helper methods for
transaction lifecycle and row-level change records.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List


class WriteAheadLog:
    """Append-only JSONL WAL writer/reader."""

    def __init__(self, log_path: str, sync_on_commit: bool = True):
        self.log_path = log_path
        self.sync_on_commit = sync_on_commit
        self._lock = threading.Lock()
        self._lsn = 0       # LSN(log sequence number) counter for sequence numbers
        self._bootstrap_lsn()

    def _bootstrap_lsn(self) -> None:
        """Initialize LSN counter from existing WAL entries."""
        entries = self.read_entries()
        if entries:
            self._lsn = max(int(entry.get("lsn", 0)) for entry in entries)

    def _next_lsn(self) -> int:
        self._lsn += 1
        return self._lsn

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def append(self, record: Dict[str, Any], durable: bool = False) -> Dict[str, Any]:
        """Append one record to WAL and return the final stored object.

        When durable=True, force the write to stable storage via fsync.
        """
        os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)

        with self._lock:
            payload = dict(record)
            payload.setdefault("lsn", self._next_lsn())
            payload.setdefault("ts", self._now_iso())

            with open(self.log_path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, ensure_ascii=True) + "\n")
                fp.flush()
                if durable:
                    os.fsync(fp.fileno())

            return payload

    def log_begin(self, tx_id: str) -> Dict[str, Any]:
        return self.append({"tx_id": tx_id, "type": "BEGIN"})

    def log_change(
        self,
        tx_id: str,
        table: str,
        key: Any,
        operation: str,
        before: Dict[str, Any] | None,
        after: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        return self.append(
            {
                "tx_id": tx_id,
                "type": operation,
                "table": table,
                "key": key,
                "before": before,
                "after": after,
            }
        )

    def log_commit(self, tx_id: str) -> Dict[str, Any]:
        return self.append(
            {"tx_id": tx_id, "type": "COMMIT"},
            durable=self.sync_on_commit,
        )

    def log_rollback(self, tx_id: str) -> Dict[str, Any]:
        return self.append({"tx_id": tx_id, "type": "ROLLBACK"})

    def read_entries(self) -> List[Dict[str, Any]]:
        """Return all WAL records from disk."""
        if not os.path.exists(self.log_path):
            return []

        out: List[Dict[str, Any]] = []
        with open(self.log_path, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                out.append(json.loads(line))
        return out

    def clear(self) -> None:
        """Clear WAL file. Intended for tests only."""
        with self._lock:
            if os.path.exists(self.log_path):
                os.remove(self.log_path)
            self._lsn = 0
