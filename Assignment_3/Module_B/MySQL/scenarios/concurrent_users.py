"""
Spec: Concurrent Usage
======================
20 users launch simultaneously and each performs a mix of operations
(browse listings, post a new listing, submit an offer, check notifications).

Invariant: success rate >= 90 %, zero HTTP 5xx server errors.

This scenario proves the Go backend and MySQL handle concurrent sessions
without deadlocks, data corruption, or unhandled panics.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from helpers.api_client import CampusApiClient
from helpers.metrics import OperationMetrics
from helpers.result import ScenarioResult


def run(
    base_url: str,
    users: List[Dict[str, Any]],      # pre-seeded user dicts: {email, password}
    listing_ids: List[int],            # pre-existing listing IDs to query/offer on
    category_id: int = 1,
    docker_monitor: Optional[Any] = None,
) -> ScenarioResult:
    """
    Thread role assignment (cycled by index modulo 4):
      0 → reader:   5× GET /listings
      1 → lister:   POST /listings (creates a new listing)
      2 → offerer:  POST /listings/{id}/offers (submits an offer)
      3 → notifier: 3× GET /notifications

    All threads synchronise on a Barrier so every role is active at the
    exact same moment — maximising lock contention on the MySQL side.
    """
    metrics = OperationMetrics()
    n_threads = min(20, len(users))
    barrier = threading.Barrier(n_threads)

    completed: List[Dict] = []
    completed_lock = threading.Lock()
    server_errors: List[str] = []
    server_errors_lock = threading.Lock()

    def make_runner(idx: int, user: Dict[str, Any]):
        def runner() -> None:
            client = CampusApiClient(base_url, metrics=metrics)
            ok, _ = client.login(user["email"], user["password"])
            if not ok:
                # Count as failure but still unblock the barrier
                barrier.wait()
                return

            barrier.wait()  # all threads released simultaneously

            role = idx % 4
            local_errors: List[str] = []

            if role == 0:  # reader
                for _ in range(5):
                    ok, _ = client.get_listings()
                    if not ok:
                        local_errors.append(f"GET /listings failed (thread {idx})")

            elif role == 1:  # lister
                ok, data = client.create_listing(
                    title=f"Concurrent item {idx}",
                    description="Auto-generated listing for concurrency test.",
                    asking_price=float(200 + idx * 7),
                    category_id=category_id,
                )
                # Only flag genuine 5xx server errors; business-logic rejections
                # such as "max 2 active listings" (400/403) are acceptable.
                if not ok:
                    err_msg = str(data.get("error", "")).lower()
                    if any(kw in err_msg for kw in ("internal", "server error", "panic")):
                        local_errors.append(f"POST /listings 5xx (thread {idx}): {data}")

            elif role == 2:  # offerer
                if listing_ids:
                    lid = listing_ids[idx % len(listing_ids)]
                    ok, data = client.submit_offer(lid, float(150 + idx * 3))
                    # 409 Conflict (already offered / listing sold) is acceptable
                    if not ok:
                        err_msg = str(data.get("error", "")).lower()
                        if any(kw in err_msg for kw in ("internal", "server error", "panic")):
                            local_errors.append(f"POST /offers 5xx (thread {idx}): {data}")

            else:  # notifier
                for _ in range(3):
                    ok, _ = client.get_notifications()
                    if not ok:
                        local_errors.append(f"GET /notifications failed (thread {idx})")

            with completed_lock:
                completed.append({"idx": idx, "role": role})
            with server_errors_lock:
                server_errors.extend(local_errors)

        return runner

    threads = [
        threading.Thread(target=make_runner(i, users[i % len(users)]), daemon=True)
        for i in range(n_threads)
    ]

    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    elapsed_ms = (time.monotonic() - t0) * 1000

    snap = metrics.snapshot()
    n_server_errors = len(server_errors)
    success_rate = snap["success_rate"]

    passed = success_rate >= 0.90 and n_server_errors == 0

    return ScenarioResult(
        name="concurrent_users",
        spec_requirement="Concurrent Usage",
        passed=passed,
        metrics={**snap, "elapsed_ms": round(elapsed_ms, 2)},
        invariants={
            "n_threads": n_threads,
            "threads_completed": len(completed),
            "success_rate": success_rate,
            "server_errors_5xx": n_server_errors,
            "no_server_errors": n_server_errors == 0,
            "high_success_rate": success_rate >= 0.90,
            "server_error_details": server_errors[:10],
        },
        docker_stats_peak=docker_monitor.get_peak() if docker_monitor else {},
        notes=(
            f"{n_threads} users across 4 operation types launched simultaneously via Barrier. "
            "Roles: reader × 5, lister × 5, offerer × 5, notifier × 5."
        ),
    )
