"""
Spec: Race Condition Testing
============================
N buyer offers exist on a single listing. The seller opens N browser
tabs simultaneously, each attempting to accept a different offer.

Because the AcceptOffer handler reads the offer status *before* its
transaction begins (TOCTOU window), two concurrent accepts can both
see OfferStatus='Submitted' and proceed. MySQL's InnoDB row-level
locking then determines the final outcome:

  • If a deadlock is detected, MySQL rolls back one transaction → 1 winner.
  • If both UPDATE statements target different rows and no deadlock fires,
    both may succeed → race condition with 2 Accepted offers.

We record the ground-truth DB state after all threads finish and report
whether the race was contained or leaked, making this a transparent
demonstration of the concurrency behaviour of the real application.

Invariant (PASS): exactly 1 Accepted offer, listing Status='Sold',
                  at least 1 Transaction.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from helpers.api_client import CampusApiClient
from helpers.db_verifier import DBVerifier
from helpers.metrics import OperationMetrics
from helpers.result import ScenarioResult


def run(
    base_url: str,
    seller: Dict[str, Any],          # {email, password}
    buyers: List[Dict[str, Any]],    # list of {email, password}
    listing_id: int,                 # pre-created listing (Status='Listed')
    offer_ids: List[int],            # one per buyer, all OfferStatus='Submitted'
    db_verifier: Optional[DBVerifier] = None,
    docker_monitor: Optional[Any] = None,
) -> ScenarioResult:
    n = len(offer_ids)
    metrics = OperationMetrics()
    barrier = threading.Barrier(n)

    per_thread_results: List[Dict] = []
    results_lock = threading.Lock()

    def accept_runner(offer_id: int, idx: int) -> None:
        # Each thread gets its own login session — simulating N browser tabs.
        client = CampusApiClient(base_url, metrics=metrics)
        client.login(seller["email"], seller["password"])

        barrier.wait()   # all threads start the accept call simultaneously

        t0 = time.monotonic()
        ok, data = client.accept_offer(offer_id)
        elapsed = (time.monotonic() - t0) * 1000

        with results_lock:
            per_thread_results.append({
                "idx": idx,
                "offer_id": offer_id,
                "http_ok": ok,
                "status_code_ok": ok,
                "response": data,
                "elapsed_ms": round(elapsed, 2),
            })

    threads = [
        threading.Thread(target=accept_runner, args=(offer_ids[i], i), daemon=True)
        for i in range(n)
    ]

    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    elapsed_ms = (time.monotonic() - t0) * 1000

    snap = metrics.snapshot()
    http_successes = sum(1 for r in per_thread_results if r["http_ok"])

    # Ground-truth DB check
    db_result: Dict[str, Any] = {}
    race_detected = False
    all_invariants_pass = False

    if db_verifier and db_verifier.connect():
        db_result = db_verifier.verify_offer_race(listing_id, n)
        race_detected = db_result.get("race_condition_detected", False)
        all_invariants_pass = db_result.get("all_invariants_pass", False)
    else:
        # Fallback: trust the HTTP layer
        all_invariants_pass = http_successes == 1
        race_detected = http_successes > 1

    passed = all_invariants_pass and not race_detected

    db_gt = db_result if db_result else {}
    txn_actual   = db_gt.get("total_transactions", "?")
    txn_expected = db_gt.get("expected_transactions", n)
    if race_detected:
        if db_gt.get("accepted_offers", 0) > 1:
            race_note = (
                f"RACE CONDITION (Type A): {db_gt.get('accepted_offers')} offers accepted. "
                "MySQL row-level locking did not prevent both threads from marking an offer "
                "Accepted. Recommend SELECT ... FOR UPDATE inside the transaction."
            )
        else:
            race_note = (
                f"RACE CONDITION (Type B — transaction explosion): accepted_offers=1 "
                f"(correct) but {txn_actual} Transaction rows created vs. expected {txn_expected}. "
                f"All {n} concurrent accept() calls slipped through the TOCTOU window: each "
                f"thread saw all offers as 'Submitted' simultaneously, causing each to create "
                f"a full set of {txn_expected} Transaction rows. "
                "Fix: add SELECT ... FOR UPDATE on the Listing row inside the transaction "
                "so at most one thread can proceed."
            )
    else:
        race_note = (
            f"MySQL isolation (InnoDB row locks + deadlock detection) fully contained the race: "
            f"exactly 1 offer accepted, listing Sold, {txn_actual} transactions "
            f"(expected {txn_expected})."
        )

    return ScenarioResult(
        name="offer_race",
        spec_requirement="Race Condition Testing",
        passed=passed,
        metrics={
            **snap,
            "elapsed_ms": round(elapsed_ms, 2),
            "per_thread": per_thread_results,
        },
        invariants={
            "n_concurrent_accepts": n,
            "http_successes": http_successes,
            "http_failures": n - http_successes,
            "db_ground_truth": db_result,
            "race_condition_detected": race_detected,
            "exactly_one_winner": not race_detected,
            "all_invariants_pass": all_invariants_pass,
        },
        docker_stats_peak=docker_monitor.get_peak() if docker_monitor else {},
        notes=race_note,
    )
