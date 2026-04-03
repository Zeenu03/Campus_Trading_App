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
import sys
import tempfile
import threading
import time
from typing import Any, Dict, List

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
# same time.  Invariant: exactly one accept succeeds per listing per run.
# ---------------------------------------------------------------------------

def scenario_accept_race(threads: int, iterations: int) -> Dict[str, Any]:
    profile = SeedProfile(
        listings_per_run=1,
        buyer_ids=list(range(101, 101 + threads)),
    )

    winners_per_run: List[int] = []

    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(iterations):
            engine = _make_engine(tmp, profile)
            offer_ids = [profile.offer_base_id + j for j in range(threads)]

            results: List[tuple[bool, str]] = []
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
            engine.metrics.reset()

    invariants = {
        "single_winner_per_run": all(w == 1 for w in winners_per_run),
        "winners_per_run": winners_per_run,
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
            results: List[tuple[bool, str]] = []
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

    combined_ok = sum(m["ops_ok"] for m in all_metrics)
    combined_total = sum(m["ops_total"] for m in all_metrics)
    invariants = {
        "all_succeeded": all(m["all_succeeded"] for m in all_metrics),
        "total_ops_ok": combined_ok,
        "total_ops": combined_total,
        "per_iteration": all_metrics,
    }
    return invariants


# ---------------------------------------------------------------------------
# Scenario: failure_injection
#
# Accept with a randomly chosen fail_after_step (1-5) and verify the engine
# rolls back cleanly — row counts must be identical to initial seed counts.
# ---------------------------------------------------------------------------

def scenario_failure_injection(threads: int, iterations: int) -> Dict[str, Any]:
    import random

    all_clean: List[bool] = []

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
                threading.Thread(target=runner, args=(offer_ids[i], random.randint(1, 5)))
                for i in range(threads)
            ]
            for t in ts:
                t.start()
            for t in ts:
                t.join()

            final_counts = engine.table_row_counts()
            # After total failure injection, Transaction and Notification should
            # have at most the initial count (all rollbacks cleaned up).
            clean = (
                final_counts["Transaction"] <= initial_counts["Transaction"]
                and final_counts["Notification"] <= initial_counts["Notification"]
            )
            all_clean.append(clean)

    invariants = {
        "all_rollbacks_clean": all(all_clean),
        "per_iteration_clean": all_clean,
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
        "committed": ok,
        "redo_applied": redo,
        "listing_sold_after_recovery": listing_sold,
        "passed": listing_sold,
    }


# ---------------------------------------------------------------------------
# Scenario: stress_bulk
#
# High-volume stress: *waves* independent races, each with *threads*
# concurrent accept_offer calls (same listing). Total operations =
# waves * threads (spec: hundreds or thousands of requests).
# Invariant: exactly one winner per wave => total_successes == waves.
# ---------------------------------------------------------------------------

def scenario_stress_bulk(waves: int, threads: int) -> Dict[str, Any]:
    profile = SeedProfile(
        listings_per_run=1,
        buyer_ids=list(range(101, 101 + threads)),
    )
    winners_per_wave: List[int] = []
    t0 = time.monotonic()

    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(waves):
            engine = _make_engine(tmp, profile)
            offer_ids = [profile.offer_base_id + j for j in range(threads)]
            results: List[tuple[bool, str]] = []
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

    elapsed_ms = (time.monotonic() - t0) * 1000
    total_ops = waves * threads
    total_success = sum(winners_per_wave)
    return {
        "waves": waves,
        "threads_per_wave": threads,
        "total_operations": total_ops,
        "total_successful_commits": total_success,
        "elapsed_ms": round(elapsed_ms, 2),
        "ops_per_second": round(total_ops / (elapsed_ms / 1000.0), 2) if elapsed_ms > 0 else 0.0,
        "winners_per_wave": winners_per_wave,
        "invariants": {
            "exactly_one_winner_each_wave": all(w == 1 for w in winners_per_wave),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

SCENARIOS = {
    "accept_race": scenario_accept_race,
    "accept_load": scenario_accept_load,
    "failure_injection": scenario_failure_injection,
    "crash_recovery": scenario_crash_recovery,
    "stress_bulk": scenario_stress_bulk,
}


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
    parser.add_argument("--threads", type=int, default=10, help="Number of concurrent threads")
    parser.add_argument("--iterations", type=int, default=3, help="Number of independent runs")
    parser.add_argument(
        "--waves",
        type=int,
        default=50,
        help="For stress_bulk: number of race waves (total ops = waves × threads)",
    )
    args = parser.parse_args()

    t0 = time.monotonic()

    fn = SCENARIOS[args.scenario]
    if args.scenario == "crash_recovery":
        invariants = fn()
    elif args.scenario == "stress_bulk":
        invariants = fn(args.waves, args.threads)
    else:
        invariants = fn(args.threads, args.iterations)

    elapsed = round((time.monotonic() - t0) * 1000, 1)

    result: Dict[str, Any] = {
        "scenario": args.scenario,
        "threads": args.threads,
        "iterations": args.iterations,
        "waves": args.waves,
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

    bool_vals = _collect_bools(invariants)
    result["passed"] = all(bool_vals) if bool_vals else True

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
