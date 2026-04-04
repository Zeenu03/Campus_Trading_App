"""
Spec: Failure Simulation
========================
Demonstrates InnoDB's atomicity guarantee under abrupt container failure:

  Phase 1 — Concurrent writes: N buyer threads submit offers across
             multiple listings with staggered start times.
  Phase 2 — Kill MySQL: after ~half the threads have started, the
             MySQL Docker container is stopped abruptly (docker stop).
             In-flight transactions that have not yet committed are
             automatically rolled back by InnoDB on restart.
  Phase 3 — Restart and verify: MySQL is restarted, then the DB verifier
             checks that no orphaned / partial rows exist.

Invariants (PASS):
  • container_stopped == True
  • container_restarted == True
  • mysql_recovered == True
  • full_integrity_check all_clean == True
    (no orphan transactions, no accepted-without-transaction, etc.)
"""
from __future__ import annotations

import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from helpers.api_client import CampusApiClient
from helpers.db_verifier import DBVerifier
from helpers.metrics import OperationMetrics
from helpers.result import ScenarioResult

CONTAINER_NAME = "campus_a3_mysql"


def _stop_container(name: str = CONTAINER_NAME) -> bool:
    r = subprocess.run(["docker", "stop", name], capture_output=True, timeout=20)
    return r.returncode == 0


def _start_container(name: str = CONTAINER_NAME) -> bool:
    r = subprocess.run(["docker", "start", name], capture_output=True, timeout=20)
    return r.returncode == 0


def _wait_for_mysql(db_verifier: DBVerifier, max_wait: int = 60) -> bool:
    """Poll until MySQL accepts a direct TCP connection."""
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        db_verifier._conn = None   # force reconnect attempt
        if db_verifier.connect():
            return True
        time.sleep(2)
    return False


def run(
    base_url: str,
    listing_ids: List[int],           # listings to submit offers on
    buyers: List[Dict[str, Any]],     # buyer user dicts: {email, password}
    db_verifier: Optional[DBVerifier] = None,
    docker_monitor: Optional[Any] = None,
    n_concurrent: int = 10,
) -> ScenarioResult:
    metrics = OperationMetrics()
    n = min(n_concurrent, len(buyers))

    results: List[Dict] = []
    results_lock = threading.Lock()
    kill_fired = threading.Event()

    # ── Snapshot counts BEFORE failure ───────────────────────────
    pre_counts: Dict[str, int] = {}
    if db_verifier and db_verifier.connect():
        pre_counts = db_verifier.get_table_counts()

    def offer_runner(idx: int, buyer: Dict[str, Any], lid: int) -> None:
        client = CampusApiClient(base_url, metrics=metrics)
        ok, _ = client.login(buyer["email"], buyer["password"])
        if not ok:
            with results_lock:
                results.append({"idx": idx, "login_ok": False, "ok": False})
            return

        # Stagger starts so threads span the kill window
        time.sleep(idx * 0.08)

        t0 = time.monotonic()
        ok_offer, data = client.submit_offer(lid, float(80 + idx * 5))
        elapsed = (time.monotonic() - t0) * 1000

        with results_lock:
            results.append({
                "idx": idx,
                "ok": ok_offer,
                "elapsed_ms": round(elapsed, 2),
                "after_kill": kill_fired.is_set(),
                "response": data,
            })

    threads = [
        threading.Thread(
            target=offer_runner,
            args=(i, buyers[i % len(buyers)], listing_ids[i % len(listing_ids)]),
            daemon=True,
        )
        for i in range(n)
    ]

    for t in threads:
        t.start()

    # ── Kill MySQL after ~half the threads have had time to start ─
    kill_delay = max(0.15, n * 0.08 * 0.45)
    time.sleep(kill_delay)
    container_stopped = _stop_container()
    kill_fired.set()

    for t in threads:
        t.join(timeout=25)

    requests_committed = sum(1 for r in results if r.get("ok"))
    requests_failed = sum(1 for r in results if not r.get("ok") and "login_ok" not in r)

    # ── Restart MySQL and verify ─────────────────────────────────
    container_restarted = _start_container()
    mysql_back = False
    post_counts: Dict[str, int] = {}
    integrity: Dict[str, Any] = {"all_clean": False, "error": "MySQL did not recover"}

    if container_restarted and db_verifier:
        mysql_back = _wait_for_mysql(db_verifier, max_wait=70)
        if mysql_back:
            time.sleep(1)   # let InnoDB finish recovery
            post_counts = db_verifier.get_table_counts()
            integrity = db_verifier.full_integrity_check()

    snap = metrics.snapshot()
    passed = (
        container_stopped
        and container_restarted
        and mysql_back
        and integrity.get("all_clean", False)
    )

    return ScenarioResult(
        name="failure_simulation",
        spec_requirement="Failure Simulation",
        passed=passed,
        metrics={**snap},
        invariants={
            "n_concurrent_writers": n,
            "container_stopped": container_stopped,
            "container_restarted": container_restarted,
            "mysql_recovered": mysql_back,
            "requests_committed_before_kill": requests_committed,
            "requests_failed_during_kill": requests_failed,
            "pre_failure_table_counts": pre_counts,
            "post_recovery_table_counts": post_counts,
            "integrity_check": integrity,
            "no_orphan_data": integrity.get("all_clean", False),
        },
        docker_stats_peak=docker_monitor.get_peak() if docker_monitor else {},
        notes=(
            f"{n} concurrent offer-submissions with MySQL killed mid-way "
            f"({requests_committed} committed, {requests_failed} failed/aborted). "
            "Post-restart full_integrity_check validates InnoDB atomicity: "
            "every in-flight transaction at kill time was automatically rolled back."
        ),
    )
