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

    # -----------------------------------------------------------------------
    # Invariant helpers — used by stress scenarios for deep state checks
    # -----------------------------------------------------------------------

    def verify_all_rolled_back(self, initial_counts: Dict[str, int]) -> Dict[str, Any]:
        """Verify that all failed transactions were fully rolled back.

        Checks four things:
        1. All Offer rows still have OfferStatus == "Submitted" — none should be
           stuck in "Accepted" or "Declined" from a partial (rolled-back) transaction.
        2. All Listing rows still have Status == "Listed" — none wrongly "Sold".
        3. Transaction row count <= initial count (no committed inserts snuck in).
        4. Notification row count <= initial count (same).

        Returns a dict with per-check booleans and a top-level ``clean`` bool.
        """
        assert self.dbm is not None, "Call bootstrap() first"
        db = self.profile.db_name

        offer_t,   _ = self.dbm.get_table(db, "Offer")
        listing_t, _ = self.dbm.get_table(db, "Listing")

        stuck_offers: List[Dict[str, Any]] = []
        if offer_t:
            for key, row in offer_t.get_all():
                status = row.get("OfferStatus", "")
                if status != "Submitted":
                    stuck_offers.append({"offer_id": key, "status": status})

        stuck_listings: List[Dict[str, Any]] = []
        if listing_t:
            for key, row in listing_t.get_all():
                status = row.get("Status", "")
                if status != "Listed":
                    stuck_listings.append({"listing_id": key, "status": status})

        final_counts = self.table_row_counts()
        txn_ok   = final_counts["Transaction"]   <= initial_counts["Transaction"]
        notif_ok = final_counts["Notification"]  <= initial_counts["Notification"]

        return {
            "stuck_offers":            stuck_offers,
            "stuck_listings":          stuck_listings,
            "offer_statuses_clean":    len(stuck_offers) == 0,
            "listing_statuses_clean":  len(stuck_listings) == 0,
            "transaction_count_ok":    txn_ok,
            "notification_count_ok":   notif_ok,
            "clean": (
                len(stuck_offers) == 0
                and len(stuck_listings) == 0
                and txn_ok
                and notif_ok
            ),
        }

    def assert_race_invariants(self, threads: int) -> Dict[str, Any]:
        """Deep state check after a concurrent race on the same listing.

        After N threads compete to accept different offers on one listing,
        verifies:
        - Exactly 1 Offer is "Accepted".
        - Exactly N-1 Offers are "Declined".
        - Exactly 1 Listing has Status "Sold".
        - Exactly 1 Transaction has Status "Completed".
        - The Accepted Offer's primary key matches the Completed Transaction's
          OfferID field (cross-table referential integrity between Offer and
          Transaction).

        Works for both pure-race (all threads try to succeed) and mixed
        scenarios (some threads have fail_after_step), because a failing thread
        either rolls back cleanly before the winner runs, or fails validation
        after the winner has already committed.
        """
        assert self.dbm is not None, "Call bootstrap() first"
        db = self.profile.db_name

        offer_t,   _ = self.dbm.get_table(db, "Offer")
        listing_t, _ = self.dbm.get_table(db, "Listing")
        txn_t,     _ = self.dbm.get_table(db, "Transaction")

        accepted_offers = [
            (k, r) for k, r in (offer_t.get_all() if offer_t else [])
            if r.get("OfferStatus") == "Accepted"
        ]
        declined_offers = [
            (k, r) for k, r in (offer_t.get_all() if offer_t else [])
            if r.get("OfferStatus") == "Declined"
        ]
        sold_listings = [
            (k, r) for k, r in (listing_t.get_all() if listing_t else [])
            if r.get("Status") == "Sold"
        ]
        completed_txns = [
            (k, r) for k, r in (txn_t.get_all() if txn_t else [])
            if r.get("Status") == "Completed"
        ]

        offer_txn_match = False
        if len(accepted_offers) == 1 and len(completed_txns) == 1:
            accepted_offer_id       = accepted_offers[0][0]
            completed_txn_offer_id  = completed_txns[0][1].get("OfferID")
            offer_txn_match = (accepted_offer_id == completed_txn_offer_id)

        exactly_one_accepted  = len(accepted_offers) == 1
        exactly_one_sold      = len(sold_listings)   == 1
        exactly_one_completed = len(completed_txns)  == 1
        declined_count_ok     = len(declined_offers) == threads - 1

        return {
            "accepted_offer_count":        len(accepted_offers),
            "declined_offer_count":        len(declined_offers),
            "sold_listing_count":          len(sold_listings),
            "completed_transaction_count": len(completed_txns),
            "offer_txn_referential_match": offer_txn_match,
            "exactly_one_accepted":        exactly_one_accepted,
            "exactly_one_sold_listing":    exactly_one_sold,
            "exactly_one_completed_txn":   exactly_one_completed,
            "declined_count_correct":      declined_count_ok,
            "all_invariants_pass": (
                exactly_one_accepted
                and exactly_one_sold
                and exactly_one_completed
                and offer_txn_match
                and declined_count_ok
            ),
        }

    def check_referential_integrity(self) -> Dict[str, Any]:
        """Verify cross-table referential integrity across all four campus tables.

        For every Transaction row, checks:
        - OfferID exists in the Offer table.
        - ListingID exists in the Listing table.
        - SellerID matches the referenced Listing's SellerID.
        - For "Completed" Transactions, AgreedPrice matches the Offer's AgreedPrice.

        Also checks that no two "Completed" Transactions share the same OfferID
        (duplicate commit detection).

        Returns a dict with a ``violations`` list (empty = clean) and a
        ``referential_integrity_ok`` bool.
        """
        assert self.dbm is not None, "Call bootstrap() first"
        db = self.profile.db_name

        offer_t,   _ = self.dbm.get_table(db, "Offer")
        listing_t, _ = self.dbm.get_table(db, "Listing")
        txn_t,     _ = self.dbm.get_table(db, "Transaction")

        violations: List[str] = []

        if txn_t and offer_t and listing_t:
            offer_keys   = {k for k, _ in offer_t.get_all()}
            listing_keys = {k for k, _ in listing_t.get_all()}
            completed_offer_ids: List[Any] = []

            for txn_key, txn_row in txn_t.get_all():
                offer_id   = txn_row.get("OfferID")
                listing_id = txn_row.get("ListingID")
                seller_id  = txn_row.get("SellerID")

                if offer_id not in offer_keys:
                    violations.append(
                        f"Transaction {txn_key}: OfferID {offer_id} "
                        f"not found in Offer table"
                    )
                if listing_id not in listing_keys:
                    violations.append(
                        f"Transaction {txn_key}: ListingID {listing_id} "
                        f"not found in Listing table"
                    )
                if listing_id in listing_keys:
                    listing_row = listing_t.get(listing_id)
                    if listing_row and listing_row.get("SellerID") != seller_id:
                        violations.append(
                            f"Transaction {txn_key}: SellerID {seller_id} does not "
                            f"match Listing {listing_id} SellerID "
                            f"{listing_row.get('SellerID')}"
                        )

                if txn_row.get("Status") == "Completed" and offer_id in offer_keys:
                    offer_row = offer_t.get(offer_id)
                    if offer_row:
                        txn_price   = txn_row.get("AgreedPrice")
                        offer_price = offer_row.get("AgreedPrice")
                        if txn_price != offer_price:
                            violations.append(
                                f"Transaction {txn_key}: AgreedPrice {txn_price} "
                                f"!= Offer {offer_id} AgreedPrice {offer_price}"
                            )
                    completed_offer_ids.append(offer_id)

            if len(completed_offer_ids) != len(set(completed_offer_ids)):
                violations.append(
                    "Multiple Completed transactions share the same OfferID "
                    "— duplicate commit detected"
                )

        return {
            "violations":              violations,
            "violation_count":         len(violations),
            "referential_integrity_ok": len(violations) == 0,
        }
