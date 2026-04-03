"""Stress-testing helpers: OperationMetrics and StressEngine.

StressEngine wraps DatabaseManager to provide the bootstrap / accept_offer /
metrics / recover cycle that stress scenarios need, without coupling the
database package to stress-testing concerns.

Module B (run_experiments.py) drives stress_driver.py which uses this module.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Allow importing the database package when running as a script from scripts/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager  # noqa: E402
from database.wal import WriteAheadLog  # noqa: E402
from database.recovery import RecoveryManager  # noqa: E402
from database.campus_schema import (  # noqa: E402
    SeedProfile,
    CAMPUS_TABLE_NAMES,
    install_campus_schema,
    seed_campus_tables,
)
from database.campus_workflow import accept_offer_atomic  # noqa: E402


# ---------------------------------------------------------------------------
# Operation metrics
# ---------------------------------------------------------------------------

@dataclass
class OperationMetrics:
    """Thread-safe latency and success/failure counters for stress runs."""

    ops_ok: int = 0
    ops_fail: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)

    def record(self, ok: bool, elapsed_ms: float) -> None:
        with self._lock:
            if ok:
                self.ops_ok += 1
            else:
                self.ops_fail += 1
            self.latencies_ms.append(elapsed_ms)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            total = self.ops_ok + self.ops_fail
            lats = list(self.latencies_ms)

        if lats:
            avg = sum(lats) / len(lats)
            p99 = sorted(lats)[int(len(lats) * 0.99)]
            max_lat = max(lats)
        else:
            avg = p99 = max_lat = 0.0

        return {
            "ops_total": total,
            "ops_ok": self.ops_ok,
            "ops_fail": self.ops_fail,
            "success_rate": round(self.ops_ok / total, 4) if total else 0.0,
            "latency_avg_ms": round(avg, 3),
            "latency_p99_ms": round(p99, 3),
            "latency_max_ms": round(max_lat, 3),
        }

    def reset(self) -> None:
        with self._lock:
            self.ops_ok = 0
            self.ops_fail = 0
            self.latencies_ms.clear()


# ---------------------------------------------------------------------------
# Stress engine
# ---------------------------------------------------------------------------

class StressEngine:
    """Bootstrapped campus database engine for stress scenarios.

    Lifecycle::

        engine = StressEngine(wal_path, profile)
        engine.bootstrap()                             # schema + seed data
        ok, msg = engine.accept_offer(offer_id, seller_id)
        counts = engine.table_row_counts()
        summary = engine.recover_and_reopen()          # simulate restart

    ``dbm`` is public so scenarios can read table state directly for
    invariant checks without going through the workflow.
    """

    def __init__(self, wal_path: str, profile: SeedProfile) -> None:
        self.profile = profile
        self._wal_path = wal_path
        self.dbm: Optional[DatabaseManager] = None
        self.metrics = OperationMetrics()

    def bootstrap(self, reset_wal: bool = True) -> None:
        """Install campus schema, seed deterministic data, and reset metrics.

        Calling ``bootstrap()`` again tears down previous in-memory state and
        re-seeds from scratch — ideal for repeatable stress runs.
        """
        if reset_wal and os.path.exists(self._wal_path):
            os.remove(self._wal_path)
        self.dbm = DatabaseManager(wal_path=self._wal_path)
        install_campus_schema(self.dbm, self.profile)
        seed_campus_tables(self.dbm, self.profile)
        self.metrics.reset()

    def accept_offer(
        self,
        offer_id: int,
        seller_id: int,
        agreed_price: Optional[float] = None,
        include_notifications: bool = False,
        create_declined_transactions: bool = True,
        fail_after_step: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Accept *offer_id* atomically, recording timing in ``self.metrics``."""
        assert self.dbm is not None, "Call bootstrap() before accept_offer()"
        t0 = time.monotonic()
        ok, msg = accept_offer_atomic(
            self.dbm,
            self.profile.db_name,
            offer_id,
            seller_id,
            agreed_price=agreed_price,
            include_notifications=include_notifications,
            create_declined_transactions=create_declined_transactions,
            fail_after_step=fail_after_step,
        )
        self.metrics.record(ok, (time.monotonic() - t0) * 1000)
        return ok, msg

    def table_row_counts(self) -> Dict[str, int]:
        """Return row counts for all campus tables (Offer, Listing, Transaction, Notification)."""
        assert self.dbm is not None, "Call bootstrap() first"
        counts: Dict[str, int] = {}
        for table_name in CAMPUS_TABLE_NAMES:
            table, _ = self.dbm.get_table(self.profile.db_name, table_name)
            counts[table_name] = len(table.get_all()) if table else 0
        return counts

    def metrics_snapshot(self) -> Dict[str, Any]:
        """Return a JSON-serializable metrics summary."""
        return self.metrics.snapshot()

    def recover_and_reopen(self) -> Dict[str, Any]:
        """Simulate a crash-and-restart: replay WAL into a fresh DatabaseManager.

        Reinstalls the campus schema in the new manager so the recovery engine
        can resolve table references from the WAL. Returns the recovery summary
        dict (``applied_redo``, ``applied_undo``, etc.) for invariant checks.
        """
        wal = WriteAheadLog(self._wal_path)
        rm = RecoveryManager(wal)
        new_dbm = DatabaseManager(wal_path=self._wal_path)
        install_campus_schema(new_dbm, self.profile)
        summary = rm.recover_into(new_dbm)
        self.dbm = new_dbm
        return summary
