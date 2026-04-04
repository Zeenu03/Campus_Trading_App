#!/usr/bin/env python3
"""
Module A / Module B stress driver.

Runs concurrent stress scenarios against the custom B+ Tree engine and prints
a JSON result summary to stdout. Module B scripts can shell-out to this or
import StressEngine directly from stress_engine.py.

Usage
-----
From the Assignment_3/Module_A directory:

    # Race scenario: N threads compete to accept offers on the same listing
    python3 scripts/stress_driver.py --scenario accept_race --threads 20 --iterations 5

    # Load scenario: N threads each accept a separate offer (different listings)
    python3 scripts/stress_driver.py --scenario accept_load --threads 10 --iterations 3

    # Failure injection: randomly inject failures and verify rollback
    python3 scripts/stress_driver.py --scenario failure_injection --threads 8 --iterations 5

    # Recovery: commit some transactions, simulate crash, recover, verify
    python3 scripts/stress_driver.py --scenario crash_recovery

    # Bulk stress: waves × threads total accept_offer calls (e.g. 50×20 = 1000)
    python3 scripts/stress_driver.py --scenario stress_bulk --waves 50 --threads 20

    # Consistency: race then deep referential-integrity check across all four tables
    python3 scripts/stress_driver.py --scenario consistency_check --threads 10

    # Mixed failures: half threads compete normally, half have injected failures
    python3 scripts/stress_driver.py --scenario mixed_concurrent_failure --threads 10 --iterations 5

Output
------
A single JSON object on stdout:

{
  "scenario": "accept_race",
  "threads": 20,
  "iterations": 5,
  "metrics": { "ops_total": 25, "ops_ok": 5, "ops_fail": 20, ... },
  "invariants": { "single_winner_per_listing": true, ... },
  "passed": true
}

Exit code 0 = all invariants passed; 1 = one or more invariant violations.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional

# Allow running as `python3 scripts/stress_driver.py` from Module_A root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.campus_schema import SeedProfile  # noqa: E402
from scripts.stress_engine import StressEngine  # noqa: E402


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------

def _make_engine(wal_dir: str, profile: SeedProfile) -> StressEngine:
    wal_path = os.path.join(wal_dir, "wal.log")
    engine = StressEngine(wal_path=wal_path, profile=profile)
    engine.bootstrap()
    return engine


# ---------------------------------------------------------------------------
# Scenario: accept_race
#
# N threads all try to accept competing offers on the SAME listing at the
# same time.  Invariants (G2 — deep state check):
#   - Exactly one accept succeeds per run (winner count).
#   - Exactly N-1 Offers are "Declined" (winner's step 2 ran cleanly).
#   - Exactly 1 Listing is "Sold".
#   - Exactly 1 "Completed" Transaction, whose OfferID matches the Accepted offer.
# ---------------------------------------------------------------------------

def scenario_accept_race(threads: int, iterations: int) -> Dict[str, Any]:
    profile = SeedProfile(
        listings_per_run=1,
        buyer_ids=list(range(101, 101 + threads)),
    )

    winners_per_run: List[int] = []
    deep_checks: List[Dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(iterations):
            engine = _make_engine(tmp, profile)
            offer_ids = [profile.offer_base_id + j for j in range(threads)]

            results: List[tuple] = []
            lock = threading.Lock()
            barrier = threading.Barrier(threads)

            def runner(oid: int) -> None:
                barrier.wait()
                ok, msg = engine.accept_offer(oid, profile.seller_id, include_notifications=False)
                with lock:
                    results.append((ok, msg))

            ts = [threading.Thread(target=runner, args=(oid,)) for oid in offer_ids]
            for t in ts:
                t.start()
            for t in ts:
                t.join()

            winners = sum(1 for ok, _ in results if ok)
            winners_per_run.append(winners)

            # G2: deep four-table state verification after the race
            deep = engine.assert_race_invariants(threads)
            deep_checks.append(deep)

            engine.metrics.reset()

    all_deep_pass = all(d["all_invariants_pass"] for d in deep_checks)
    invariants = {
        "single_winner_per_run":       all(w == 1 for w in winners_per_run),
        "winners_per_run":             winners_per_run,
        "deep_state_all_iterations":   all_deep_pass,
        "per_iteration_deep":          deep_checks,
    }
    return invariants


# ---------------------------------------------------------------------------
# Scenario: accept_load
#
# Each thread gets its OWN listing with its OWN offer (no contention).
# All N transactions should succeed. Tests throughput under serial lock.
# ---------------------------------------------------------------------------

def scenario_accept_load(threads: int, iterations: int) -> Dict[str, Any]:
    all_metrics: List[Dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(iterations):
            profile = SeedProfile(
                listings_per_run=threads,
                buyer_ids=[200],
            )
            engine = _make_engine(tmp, profile)

            offer_ids = [profile.offer_base_id + i for i in range(threads)]
            results: List[tuple] = []
            lock = threading.Lock()
            barrier = threading.Barrier(threads)

            def runner(oid: int, sid: int) -> None:
                barrier.wait()
                ok, msg = engine.accept_offer(oid, sid, include_notifications=False)
                with lock:
                    results.append((ok, msg))

            ts = [
                threading.Thread(target=runner, args=(offer_ids[i], profile.seller_id))
                for i in range(threads)
            ]
            for t in ts:
                t.start()
            for t in ts:
                t.join()

            snap = engine.metrics_snapshot()
            snap["all_succeeded"] = all(ok for ok, _ in results)
            all_metrics.append(snap)

    combined_ok    = sum(m["ops_ok"]    for m in all_metrics)
    combined_total = sum(m["ops_total"] for m in all_metrics)
    invariants = {
        "all_succeeded":   all(m["all_succeeded"] for m in all_metrics),
        "total_ops_ok":    combined_ok,
        "total_ops":       combined_total,
        "per_iteration":   all_metrics,
    }
    return invariants


# ---------------------------------------------------------------------------
# Scenario: failure_injection
#
# Each thread gets its own listing but is assigned a random fail_after_step
# (1–5).  Every transaction is guaranteed to fail.  Verifies (G1):
#   - All Offer rows remain "Submitted" (none stuck in "Accepted"/"Declined").
#   - All Listing rows remain "Listed" (none wrongly "Sold").
#   - Transaction and Notification row counts do not exceed initial seed counts.
# ---------------------------------------------------------------------------

def scenario_failure_injection(threads: int, iterations: int) -> Dict[str, Any]:
    all_rollback_results: List[Dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(iterations):
            profile = SeedProfile(
                listings_per_run=threads,
                buyer_ids=[300],
            )
            engine = _make_engine(tmp, profile)
            initial_counts = engine.table_row_counts()

            offer_ids = [profile.offer_base_id + i for i in range(threads)]
            barrier = threading.Barrier(threads)

            def runner(oid: int, fail_step: int) -> None:
                barrier.wait()
                engine.accept_offer(oid, profile.seller_id, fail_after_step=fail_step)

            ts = [
                threading.Thread(
                    target=runner,
                    args=(offer_ids[i], random.randint(1, 5)),
                )
                for i in range(threads)
            ]
            for t in ts:
                t.start()
            for t in ts:
                t.join()

            # G1: deep rollback check — all four tables must be pristine
            rb = engine.verify_all_rolled_back(initial_counts)
            all_rollback_results.append(rb)

    all_clean = all(r["clean"] for r in all_rollback_results)
    invariants = {
        "all_rollbacks_clean":       all_clean,
        "offer_statuses_always_ok":  all(r["offer_statuses_clean"]   for r in all_rollback_results),
        "listing_statuses_always_ok":all(r["listing_statuses_clean"] for r in all_rollback_results),
        "txn_counts_always_ok":      all(r["transaction_count_ok"]   for r in all_rollback_results),
        "notif_counts_always_ok":    all(r["notification_count_ok"]  for r in all_rollback_results),
        "per_iteration_clean":       all_rollback_results,
    }
    return invariants


# ---------------------------------------------------------------------------
# Scenario: crash_recovery
#
# Commit one transaction, then simulate crash (no explicit close), replay
# WAL into fresh manager, verify committed row is present.
# ---------------------------------------------------------------------------

def scenario_crash_recovery() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        profile = SeedProfile(listings_per_run=1, buyer_ids=[400])
        engine = _make_engine(tmp, profile)

        offer_id = profile.offer_base_id  # 2000
        ok, msg = engine.accept_offer(offer_id, profile.seller_id, include_notifications=False)
        if not ok:
            return {"committed": False, "error": msg, "redo_applied": 0}

        recovery_summary = engine.recover_and_reopen()
        redo = recovery_summary.get("applied_redo", 0)

        listing_table, _ = engine.dbm.get_table(profile.db_name, "Listing")
        listing_row = listing_table.get(profile.listing_base_id)
        listing_sold = listing_row is not None and listing_row.get("Status") == "Sold"

    return {
        "committed":                   ok,
        "redo_applied":                redo,
        "listing_sold_after_recovery": listing_sold,
        "passed":                      listing_sold,
    }


# ---------------------------------------------------------------------------
# Scenario: stress_bulk
#
# High-volume stress: *waves* independent races, each with *threads*
# concurrent accept_offer calls (same listing). Total operations =
# waves * threads (spec: hundreds or thousands of requests).
# Invariant: exactly one winner per wave => total_successes == waves.
# G5: reports per-operation latency (avg, p99, max) across all waves.
# ---------------------------------------------------------------------------

def scenario_stress_bulk(waves: int, threads: int) -> Dict[str, Any]:
    profile = SeedProfile(
        listings_per_run=1,
        buyer_ids=list(range(101, 101 + threads)),
    )
    winners_per_wave: List[int] = []
    all_latencies_ms: List[float] = []   # accumulated across all waves for G5
    t0 = time.monotonic()

    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(waves):
            engine = _make_engine(tmp, profile)
            offer_ids = [profile.offer_base_id + j for j in range(threads)]
            results: List[tuple] = []
            lock = threading.Lock()
            barrier = threading.Barrier(threads)

            def runner(oid: int) -> None:
                barrier.wait()
                ok, msg = engine.accept_offer(oid, profile.seller_id, include_notifications=False)
                with lock:
                    results.append((ok, msg))

            ts = [threading.Thread(target=runner, args=(oid,)) for oid in offer_ids]
            for t in ts:
                t.start()
            for t in ts:
                t.join()

            winners_per_wave.append(sum(1 for ok, _ in results if ok))

            # G5: collect raw per-operation latencies before resetting
            all_latencies_ms.extend(engine.metrics.latencies_ms)

    elapsed_ms   = (time.monotonic() - t0) * 1000
    total_ops    = waves * threads
    total_success = sum(winners_per_wave)

    # Compute global latency stats across all waves and all threads
    if all_latencies_ms:
        sorted_lats      = sorted(all_latencies_ms)
        latency_avg_ms   = round(sum(sorted_lats) / len(sorted_lats), 3)
        latency_p99_ms   = round(sorted_lats[int(len(sorted_lats) * 0.99)], 3)
        latency_max_ms   = round(max(sorted_lats), 3)
    else:
        latency_avg_ms = latency_p99_ms = latency_max_ms = 0.0

    return {
        "waves":                    waves,
        "threads_per_wave":         threads,
        "total_operations":         total_ops,
        "total_successful_commits": total_success,
        "elapsed_ms":               round(elapsed_ms, 2),
        "ops_per_second":           round(total_ops / (elapsed_ms / 1000.0), 2) if elapsed_ms > 0 else 0.0,
        "latency_avg_ms":           latency_avg_ms,
        "latency_p99_ms":           latency_p99_ms,
        "latency_max_ms":           latency_max_ms,
        "winners_per_wave":         winners_per_wave,
        "invariants": {
            "exactly_one_winner_each_wave": all(w == 1 for w in winners_per_wave),
            "total_winners_equals_waves":   total_success == waves,
        },
    }


# ---------------------------------------------------------------------------
# Scenario: consistency_check  (G3 — referential integrity)
#
# Runs a race with include_notifications=True and create_declined_transactions=True
# so all four tables have data.  After the race verifies:
#   1. Deep four-table state (assert_race_invariants).
#   2. Full cross-table referential integrity (check_referential_integrity):
#      - Every Transaction.OfferID exists in Offer.
#      - Every Transaction.ListingID exists in Listing.
#      - Transaction.SellerID matches Listing.SellerID.
#      - Completed Transaction.AgreedPrice == Offer.AgreedPrice.
#      - No duplicate Completed transactions for the same OfferID.
# ---------------------------------------------------------------------------

def scenario_consistency_check(threads: int) -> Dict[str, Any]:
    profile = SeedProfile(
        listings_per_run=1,
        buyer_ids=list(range(101, 101 + threads)),
    )

    with tempfile.TemporaryDirectory() as tmp:
        engine = _make_engine(tmp, profile)
        offer_ids = [profile.offer_base_id + j for j in range(threads)]

        results: List[tuple] = []
        lock    = threading.Lock()
        barrier = threading.Barrier(threads)

        def runner(oid: int) -> None:
            barrier.wait()
            ok, msg = engine.accept_offer(
                oid,
                profile.seller_id,
                include_notifications=True,
                create_declined_transactions=True,
            )
            with lock:
                results.append((ok, msg))

        ts = [threading.Thread(target=runner, args=(oid,)) for oid in offer_ids]
        for t in ts:
            t.start()
        for t in ts:
            t.join()

        race_inv = engine.assert_race_invariants(threads)
        ref_inv  = engine.check_referential_integrity()

    winners = sum(1 for ok, _ in results if ok)
    passed  = (
        winners == 1
        and race_inv["all_invariants_pass"]
        and ref_inv["referential_integrity_ok"]
    )
    return {
        "winners":                winners,
        "race_invariants":        race_inv,
        "referential_integrity":  ref_inv,
        "passed":                 passed,
    }


# ---------------------------------------------------------------------------
# Scenario: mixed_concurrent_failure  (G4 — failures under concurrency)
#
# Half the threads have fail_after_step=None (compete normally to be the
# winner); the other half have a random fail_after_step (1–5) and are
# guaranteed to fail mid-transaction.  Both groups run simultaneously.
#
# Invariants:
#   - Exactly 1 winner (from the non-failing threads).
#   - All failing threads left no partial state:
#       exactly N-1 "Declined" offers, 1 "Sold" listing, 1 "Completed" txn.
#   - Cross-table referential integrity holds (check_referential_integrity).
# ---------------------------------------------------------------------------

def scenario_mixed_concurrent_failure(threads: int, iterations: int) -> Dict[str, Any]:
    # Need at least 2 threads so there is at least one from each group.
    threads = max(threads, 4)

    profile = SeedProfile(
        listings_per_run=1,
        buyer_ids=list(range(101, 101 + threads)),
    )

    per_iter: List[Dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(iterations):
            engine = _make_engine(tmp, profile)
            offer_ids = [profile.offer_base_id + j for j in range(threads)]

            # threads // 2 non-failing, rest forced to fail at a random step
            n_normal  = threads // 2
            fail_steps: List[Optional[int]] = (
                [None] * n_normal
                + [random.randint(1, 5)] * (threads - n_normal)
            )
            random.shuffle(fail_steps)

            results: List[tuple] = []
            lock    = threading.Lock()
            barrier = threading.Barrier(threads)

            def runner(oid: int, fail_step: Optional[int]) -> None:
                barrier.wait()
                ok, msg = engine.accept_offer(
                    oid,
                    profile.seller_id,
                    fail_after_step=fail_step,
                )
                with lock:
                    results.append((ok, msg, fail_step))

            ts = [
                threading.Thread(target=runner, args=(offer_ids[i], fail_steps[i]))
                for i in range(threads)
            ]
            for t in ts:
                t.start()
            for t in ts:
                t.join()

            winners = sum(1 for ok, _, _ in results if ok)

            # Deep state: assert_race_invariants works for mixed scenarios —
            # the single winner declines all N-1 remaining "Submitted" offers
            # regardless of when failing threads ran (their rollbacks restore
            # any offers they temporarily mutated).
            deep    = engine.assert_race_invariants(threads)
            ref_inv = engine.check_referential_integrity()

            per_iter.append({
                "winners":                      winners,
                "n_normal_threads":             n_normal,
                "n_failing_threads":            threads - n_normal,
                "exactly_one_winner":           winners == 1,
                "deep_state":                   deep,
                "referential_integrity":        ref_inv,
                "iteration_passed": (
                    winners == 1
                    and deep["all_invariants_pass"]
                    and ref_inv["referential_integrity_ok"]
                ),
            })

    all_passed = all(r["iteration_passed"] for r in per_iter)
    return {
        "threads":                    threads,
        "iterations":                 iterations,
        "all_exactly_one_winner":     all(r["exactly_one_winner"]             for r in per_iter),
        "all_deep_state_pass":        all(r["deep_state"]["all_invariants_pass"] for r in per_iter),
        "all_referential_integrity":  all(r["referential_integrity"]["referential_integrity_ok"] for r in per_iter),
        "per_iteration":              per_iter,
        "passed":                     all_passed,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

SCENARIOS = {
    "accept_race":             scenario_accept_race,
    "accept_load":             scenario_accept_load,
    "failure_injection":       scenario_failure_injection,
    "crash_recovery":          scenario_crash_recovery,
    "stress_bulk":             scenario_stress_bulk,
    "consistency_check":       scenario_consistency_check,
    "mixed_concurrent_failure":scenario_mixed_concurrent_failure,
}

# Scenarios that take only threads (no iterations)
_THREADS_ONLY = {"consistency_check"}
# Scenarios that take waves + threads
_WAVES_THREADS = {"stress_bulk"}
# Scenarios with no arguments
_NO_ARGS = {"crash_recovery"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Module A/B stress driver — runs concurrent scenarios and prints JSON results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        required=True,
        help="Stress scenario to run",
    )
    parser.add_argument("--threads",    type=int, default=10, help="Number of concurrent threads")
    parser.add_argument("--iterations", type=int, default=3,  help="Number of independent runs")
    parser.add_argument(
        "--waves",
        type=int,
        default=50,
        help="For stress_bulk: number of race waves (total ops = waves × threads)",
    )
    args = parser.parse_args()

    t0 = time.monotonic()

    fn = SCENARIOS[args.scenario]
    if args.scenario in _NO_ARGS:
        invariants = fn()
    elif args.scenario in _WAVES_THREADS:
        invariants = fn(args.waves, args.threads)
    elif args.scenario in _THREADS_ONLY:
        invariants = fn(args.threads)
    else:
        invariants = fn(args.threads, args.iterations)

    elapsed = round((time.monotonic() - t0) * 1000, 1)

    result: Dict[str, Any] = {
        "scenario":   args.scenario,
        "threads":    args.threads,
        "iterations": args.iterations,
        "waves":      args.waves,
        "elapsed_ms": elapsed,
        "invariants": invariants,
    }

    def _collect_bools(obj: Any) -> List[bool]:
        out: List[bool] = []
        if isinstance(obj, bool):
            out.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                out.extend(_collect_bools(v))
        return out

    # Top-level "passed" key: if invariants contains its own "passed" use that,
    # otherwise collect all booleans recursively.
    if isinstance(invariants, dict) and "passed" in invariants:
        result["passed"] = invariants["passed"]
    else:
        bool_vals = _collect_bools(invariants)
        result["passed"] = all(bool_vals) if bool_vals else True

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
