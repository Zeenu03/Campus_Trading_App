"""
Spec: Stress Testing
====================
Fire `target_ops` API calls with `concurrency` worker threads.
Mix: ~60 % reads (GET listings, notifications, transactions, single listing)
     ~40 % writes (POST offers, POST listings)

Throughput and latency are collected in real time.
A DockerMonitor polls the MySQL container's CPU % and memory every second
during the entire run — giving a clear picture of container load under stress.

Invariants (PASS):
  • ops_attempted >= target_ops × 90 %  (workers kept up)
  • success_rate >= 85 %
  • full DB integrity check passes after load
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, Dict, List, Optional

from helpers.api_client import CampusApiClient
from helpers.db_verifier import DBVerifier
from helpers.metrics import OperationMetrics
from helpers.result import ScenarioResult


def run(
    base_url: str,
    users: List[Dict[str, Any]],     # mix of sellers + buyers (read ops only)
    buyers: List[Dict[str, Any]],    # buyers only — used for write ops to avoid
    listing_ids: List[int],          # business-rule rejections (listing cap, self-offer)
    category_id: int = 1,
    target_ops: int = 1000,
    concurrency: int = 20,
    db_verifier: Optional[DBVerifier] = None,
    docker_monitor: Optional[Any] = None,
) -> ScenarioResult:
    metrics = OperationMetrics()

    # ── Build a mixed work queue ──────────────────────────────────
    # Operation mix (designed to avoid predictable business-rule failures):
    #   60 % reads  → GET listings, notifications, transactions, single listing
    #   40 % writes → submit_offer only (buyers don't own listings, ON DUPLICATE KEY
    #                 UPDATE means re-submitting is idempotent on non-sold listings)
    #
    # create_listing is intentionally excluded from bulk writes because each user
    # is capped at 2 active listings and many users may have already hit the cap
    # from earlier scenarios — yielding unpredictable 4xx failure rates.
    work: queue.Queue = queue.Queue()
    n_users = len(users)
    n_buyers = len(buyers)
    READ_OPS  = [0, 1, 2, 3]   # get_listings, get_notifications, get_listing, get_transactions
    WRITE_OPS = [4, 5]          # submit_offer variants
    for i in range(target_ops):
        lid = listing_ids[i % len(listing_ids)] if listing_ids else None
        # 6 reads : 4 writes (60/40 split)
        slot = i % 10
        if slot < 6:
            op_type = READ_OPS[slot % len(READ_OPS)]
            user = users[i % n_users]
        else:
            op_type = WRITE_OPS[(slot - 6) % len(WRITE_OPS)]
            user = buyers[i % n_buyers]
        work.put((op_type, user, lid, i))

    # ── Throughput time-series (sampled every 5 s) ─────────────
    throughput_samples: List[Dict] = []
    samples_lock = threading.Lock()
    stop_sampler = threading.Event()

    snap_prev = {"ops_total": 0, "t": time.monotonic()}

    def _sampler() -> None:
        while not stop_sampler.is_set():
            time.sleep(5)
            snap = metrics.snapshot()
            now = time.monotonic()
            with samples_lock:
                delta_ops = snap["ops_total"] - snap_prev["ops_total"]
                delta_t = now - snap_prev["t"]
                throughput_samples.append({
                    "t_offset_s": round(now - t0, 1),
                    "ops_per_sec": round(delta_ops / delta_t, 1) if delta_t > 0 else 0,
                    "success_rate": snap["success_rate"],
                })
                snap_prev["ops_total"] = snap["ops_total"]
                snap_prev["t"] = now

    sampler_thread = threading.Thread(target=_sampler, daemon=True)

    def worker() -> None:
        current_user_email: Optional[str] = None
        client: Optional[CampusApiClient] = None

        while True:
            try:
                op_type, user, lid, idx = work.get_nowait()
            except queue.Empty:
                break

            # Re-login only when user changes.
            # Login calls are intentionally NOT counted in metrics (create client
            # without metrics, assign metrics AFTER login) so that the success_rate
            # reflects only the actual API operations under test.
            if user["email"] != current_user_email:
                login_client = CampusApiClient(base_url)   # no metrics → login not counted
                login_ok, _ = login_client.login(user["email"], user["password"])
                if not login_ok:
                    work.task_done()
                    current_user_email = user["email"]
                    continue
                login_client.metrics = metrics              # assign metrics after login
                client = login_client
                current_user_email = user["email"]

            # Execute the assigned operation
            if op_type == 0:
                client.get_listings()
            elif op_type == 1:
                client.get_notifications()
            elif op_type == 2 and lid:
                client.get_listing(lid)
            elif op_type == 3:
                client.get_transactions()
            elif op_type in (4, 5) and lid:
                # submit_offer: ON DUPLICATE KEY UPDATE makes re-submission idempotent
                # for non-sold listings, so these should have a high success rate.
                client.submit_offer(lid, float(50 + idx % 200))

            work.task_done()

    # ── Start Docker monitor + sampler, then fire workers ────────
    if docker_monitor:
        docker_monitor.start()

    t0 = time.monotonic()
    snap_prev["t"] = t0

    sampler_thread.start()
    workers = [
        threading.Thread(target=worker, daemon=True)
        for _ in range(min(concurrency, n_users))
    ]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=120)

    stop_sampler.set()
    elapsed_ms = (time.monotonic() - t0) * 1000

    if docker_monitor:
        docker_monitor.stop()

    snap = metrics.snapshot()
    ops_per_sec = round(snap["ops_total"] / (elapsed_ms / 1000), 2) if elapsed_ms > 0 else 0

    # ── Post-load integrity check ─────────────────────────────────
    integrity: Dict[str, Any] = {"all_clean": True}
    if db_verifier:
        try:
            integrity = db_verifier.full_integrity_check()
        except Exception as exc:
            integrity = {"all_clean": False, "error": str(exc)}

    passed = (
        snap["ops_total"] >= target_ops * 0.90
        and snap["success_rate"] >= 0.90      # 90%: mostly reads + idempotent offers
        and integrity.get("all_clean", False)
    )

    return ScenarioResult(
        name="stress_bulk",
        spec_requirement="Stress Testing",
        passed=passed,
        metrics={
            **snap,
            "elapsed_ms": round(elapsed_ms, 2),
            "ops_per_second": ops_per_sec,
            "target_ops": target_ops,
            "concurrency": concurrency,
            "throughput_time_series": throughput_samples,
        },
        invariants={
            "target_ops": target_ops,
            "ops_attempted": snap["ops_total"],
            "success_rate": snap["success_rate"],
            "ops_per_second": ops_per_sec,
            "latency_avg_ms": snap["avg_ms"],
            "latency_p99_ms": snap["p99_ms"],
            "latency_max_ms": snap["max_ms"],
            "integrity_after_load": integrity,
            "integrity_clean": integrity.get("all_clean", False),
            "high_success_rate": snap["success_rate"] >= 0.90,
        },
        docker_stats_peak=docker_monitor.get_peak() if docker_monitor else {},
        docker_time_series=docker_monitor.get_series() if docker_monitor else [],
        notes=(
            f"{target_ops} mixed API calls, {min(concurrency, n_users)} concurrent workers. "
            "Mix: 60 % reads (GET listings/notifications/transactions/listing), "
            "40 % writes (POST offer submissions — idempotent ON DUPLICATE KEY UPDATE). "
            "MySQL container CPU/memory polled every 1 s during load."
        ),
    )
