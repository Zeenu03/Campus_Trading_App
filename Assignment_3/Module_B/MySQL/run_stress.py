#!/usr/bin/env python3
"""
Assignment 3 — Module B: MySQL Stress Test Suite
=================================================
Orchestrates the full stress test pipeline:

  1. Start MySQL Docker container (docker compose up -d)
  2. Start the Go backend (go run .)
  3. Seed test data via the REST API
  4. Run 4 scenarios: concurrent_users, offer_race, failure_simulation, stress_bulk
  5. Generate 4 PNG charts + a JSON results report

Usage
-----
  python3 run_stress.py                          # full run
  python3 run_stress.py --no-start-docker        # MySQL already running
  python3 run_stress.py --no-start-backend       # backend already running
  python3 run_stress.py --skip-failure-sim       # skip the docker-stop test
  python3 run_stress.py --target-ops 500         # fewer ops (faster)

See RESULTS_GUIDE.md for output interpretation.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path setup so helpers/ and scenarios/ are importable ─────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from helpers.api_client import CampusApiClient          # noqa: E402
from helpers.db_verifier import DBVerifier              # noqa: E402
from helpers.docker_monitor import DockerMonitor        # noqa: E402
from helpers.metrics import OperationMetrics            # noqa: E402  (unused here but ensures import works)
from helpers.result import ScenarioResult               # noqa: E402

import scenarios.concurrent_users as s_concurrent       # noqa: E402
import scenarios.offer_race as s_race                   # noqa: E402
import scenarios.failure_simulation as s_failure        # noqa: E402
import scenarios.stress_bulk as s_bulk                  # noqa: E402

ARTIFACTS = ROOT / "artifacts"
CHARTS    = ARTIFACTS / "charts"

# Path to the Assignment 2 Module B backend (resolved relative to this file)
DEFAULT_BACKEND_DIR = ROOT.parents[2] / "Assignment_2" / "Module_B" / "backend"
DEFAULT_COMPOSE     = ROOT / "docker-compose.yml"


# ── Infrastructure helpers ────────────────────────────────────────


def _wait_for_backend(base_url: str, timeout: int = 60) -> bool:
    """Poll /auth/me until the backend responds (401 = alive)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{base_url}/auth/me", timeout=3)
            if r.status_code in (200, 401, 403):
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _wait_for_mysql_healthy(timeout: int = 90) -> bool:
    """Poll `docker inspect` until the container health is 'healthy'."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = subprocess.run(
            ["docker", "inspect", "--format",
             "{{.State.Health.Status}}", "campus_a3_mysql"],
            capture_output=True, text=True,
        )
        if r.stdout.strip() == "healthy":
            return True
        time.sleep(3)
    return False


def start_mysql(compose_file: str) -> bool:
    print("  docker compose up -d ...")
    r = subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"  ERROR: {r.stderr.strip()}")
        return False
    print("  Waiting for MySQL healthcheck (up to 90 s) ...")
    if not _wait_for_mysql_healthy(timeout=90):
        print("  ERROR: MySQL did not become healthy in time.")
        return False
    print("  MySQL container is healthy ✓")
    return True


def start_backend(backend_dir: Path, base_url: str) -> Optional[subprocess.Popen]:
    if not backend_dir.exists():
        print(f"  ERROR: backend dir not found: {backend_dir}")
        print("  Pass --backend-dir PATH or use --no-start-backend if already running.")
        return None

    env = {
        **os.environ,
        "DB_HOST":       "127.0.0.1",
        "DB_PORT":       "3306",
        "DB_USER":       "root",
        "DB_PASSWORD":   "root",
        "DB_NAME":       "CampusTradingB",
        "PORT":          "8080",
        "FRONTEND_URL":  "http://localhost:5173",
        "AUDIT_LOG_PATH": "/tmp/campus_a3_stress_audit.log",
        "UPLOADS_DIR":   str(backend_dir / "uploads"),
    }
    uploads_dir = backend_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    print(f"  go run . (cwd={backend_dir}) ...")
    proc = subprocess.Popen(
        ["go", "run", "."],
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("  Waiting for backend to respond (up to 60 s) ...")
    if not _wait_for_backend(base_url, timeout=60):
        print("  ERROR: Backend did not start in time.")
        proc.terminate()
        return None
    print(f"  Backend ready at {base_url} ✓")
    return proc


# ── Data seeding ─────────────────────────────────────────────────


def seed_data(
    base_url: str,
    run_id: str,
    n_sellers: int = 5,
    n_buyers: int = 25,
) -> Dict[str, Any]:
    """
    Register sellers, buyers, create listings, and submit offers for the
    race condition scenario.  All resource identifiers carry `run_id` so
    parallel test runs or re-runs never collide.
    """
    PASSWORD = "Stress@1234"

    # ── Register first seller and retrieve categories ─────────────
    s0 = CampusApiClient(base_url)
    s0_email = f"s{run_id}0@iitgn.ac.in"
    ok, reg_data = s0.register(s0_email, PASSWORD, f"Seller {run_id} 0")
    if not ok:
        # Already registered (previous run with same run_id) — log and continue
        pass
    ok, _ = s0.login(s0_email, PASSWORD)
    if not ok:
        raise RuntimeError(f"Cannot log in as seed seller: {reg_data}")

    _, cats = s0.get_categories()
    cat_id: int = cats[0]["category_id"] if cats else 1

    sellers: List[Dict[str, Any]] = [{"email": s0_email, "password": PASSWORD}]

    # ── Register remaining sellers ────────────────────────────────
    for i in range(1, n_sellers):
        email = f"s{run_id}{i}@iitgn.ac.in"
        c = CampusApiClient(base_url)
        c.register(email, PASSWORD, f"Seller {run_id} {i}")
        c.login(email, PASSWORD)
        sellers.append({"email": email, "password": PASSWORD})

    # ── Register buyers ───────────────────────────────────────────
    buyers: List[Dict[str, Any]] = []
    for i in range(n_buyers):
        email = f"b{run_id}{i}@iitgn.ac.in"
        c = CampusApiClient(base_url)
        c.register(email, PASSWORD, f"Buyer {run_id} {i}")
        c.login(email, PASSWORD)
        buyers.append({"email": email, "password": PASSWORD})

    # ── Create general listings (2 per seller) ────────────────────
    listing_ids: List[int] = []
    for i, seller in enumerate(sellers):
        c = CampusApiClient(base_url)
        c.login(seller["email"], PASSWORD)
        for j in range(2):
            ok, data = c.create_listing(
                title=f"Stress item {i}-{j} [{run_id}]",
                description="Auto-generated listing for stress testing.",
                asking_price=float(250 + i * 20 + j * 5),
                category_id=cat_id,
                condition="Good",
                is_negotiable=True,
            )
            if ok and data.get("listing_id"):
                listing_ids.append(data["listing_id"])

    if not listing_ids:
        raise RuntimeError("No listings were created — check backend logs.")

    # ── Create the race-condition listing ─────────────────────────
    # Use a DEDICATED race seller (no general listings) so the backend's
    # "max 2 active listings" cap never blocks the race listing creation.
    race_seller_email = f"rs{run_id}@iitgn.ac.in"
    race_seller = CampusApiClient(base_url)
    race_seller.register(race_seller_email, PASSWORD, f"Race Seller {run_id}")
    race_seller.login(race_seller_email, PASSWORD)

    ok, data = race_seller.create_listing(
        title=f"RACE LISTING [{run_id}]",
        description="Single listing targeted by simultaneous accept() calls.",
        asking_price=500.0,
        category_id=cat_id,
        condition="New",
        is_negotiable=False,
    )
    if not ok:
        print(f"  WARNING: Race listing creation failed: {data}")
    race_listing_id: Optional[int] = data.get("listing_id") if ok else None

    # Make the race seller available for offer-race scenario
    race_seller_dict = {"email": race_seller_email, "password": PASSWORD}

    race_offer_ids: List[int] = []
    if race_listing_id:
        race_buyers = buyers[:10]
        for b in race_buyers:
            bc = CampusApiClient(base_url)
            bc.login(b["email"], PASSWORD)
            ok, odata = bc.submit_offer(
                race_listing_id,
                float(400 + race_buyers.index(b) * 5),
            )
            if ok and odata.get("offer_id"):
                race_offer_ids.append(odata["offer_id"])

    print(
        f"  Seeded: {len(sellers)} sellers · {len(buyers)} buyers · "
        f"{len(listing_ids)} listings · "
        f"race_listing={race_listing_id} ({len(race_offer_ids)} offers)"
    )

    return {
        "sellers":         sellers,
        "buyers":          buyers,
        "race_seller":     race_seller_dict,
        "listing_ids":     listing_ids,
        "race_listing_id": race_listing_id,
        "race_offer_ids":  race_offer_ids,
        "category_id":     cat_id,
        "password":        PASSWORD,
    }


# ── Chart generation ─────────────────────────────────────────────


def generate_charts(
    results: List[ScenarioResult],
    output_dir: Path,
) -> List[str]:
    """Produce 4 PNG charts and return their file paths."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not installed — skipping charts")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    saved: List[str] = []

    scenario_names = [r.name for r in results]
    x = list(range(len(scenario_names)))

    # ── Chart 1: Latency by scenario (grouped bar) ───────────────
    fig, ax = plt.subplots(figsize=(12, 5))
    w = 0.25
    avg  = [r.metrics.get("avg_ms", 0)  for r in results]
    p99  = [r.metrics.get("p99_ms", 0)  for r in results]
    maxi = [r.metrics.get("max_ms", 0)  for r in results]
    ax.bar([i - w for i in x], avg,  width=w, label="Avg latency",  color="steelblue")
    ax.bar([i     for i in x], p99,  width=w, label="p99 latency",  color="darkorange")
    ax.bar([i + w for i in x], maxi, width=w, label="Max latency",  color="tomato")
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_names, rotation=15, ha="right")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Request Latency by Scenario")
    ax.legend()
    plt.tight_layout()
    p = output_dir / "latency_by_scenario.png"
    plt.savefig(p, dpi=120)
    plt.close()
    saved.append(str(p))

    # ── Chart 2: Success vs Failure count per scenario ───────────
    fig, ax = plt.subplots(figsize=(10, 5))
    ok_counts   = [r.metrics.get("ops_ok",   0) for r in results]
    fail_counts = [r.metrics.get("ops_fail", 0) for r in results]
    ax.bar(x, ok_counts,   label="Success", color="seagreen")
    ax.bar(x, fail_counts, bottom=ok_counts, label="Failure", color="tomato")
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_names, rotation=15, ha="right")
    ax.set_ylabel("Operation count")
    ax.set_title("Operations: Success vs Failure by Scenario")
    ax.legend()
    plt.tight_layout()
    p = output_dir / "error_rate.png"
    plt.savefig(p, dpi=120)
    plt.close()
    saved.append(str(p))

    # ── Chart 3: Throughput (ops/sec) per scenario ───────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    ops_per_sec = []
    for r in results:
        total = r.metrics.get("ops_total", 0)
        elapsed_s = r.metrics.get("elapsed_ms", 1) / 1000
        ops_per_sec.append(round(total / elapsed_s, 1) if elapsed_s > 0 else 0)
    ax.bar(x, ops_per_sec, color="steelblue")
    ax.set_xticks(x)
    ax.set_xticklabels(scenario_names, rotation=15, ha="right")
    ax.set_ylabel("Operations per second")
    ax.set_title("Throughput by Scenario (ops/sec)")
    plt.tight_layout()
    p = output_dir / "throughput_by_scenario.png"
    plt.savefig(p, dpi=120)
    plt.close()
    saved.append(str(p))

    # ── Chart 4: MySQL container CPU & memory during stress_bulk ─
    stress_result = next((r for r in results if r.name == "stress_bulk"), None)
    docker_series = stress_result.docker_time_series if stress_result else []
    if docker_series:
        fig, ax1 = plt.subplots(figsize=(13, 5))
        t_origin = docker_series[0]["timestamp"]
        times = [p["timestamp"] - t_origin for p in docker_series]
        cpus  = [p["cpu_pct"]              for p in docker_series]
        mems  = [p["mem_mb"]               for p in docker_series]
        ax2 = ax1.twinx()
        ax1.plot(times, cpus, color="steelblue",  label="CPU %",      linewidth=1.5)
        ax2.plot(times, mems, color="darkorange", label="Memory MB", linewidth=1.5, linestyle="--")
        ax1.set_xlabel("Time (seconds into stress_bulk)")
        ax1.set_ylabel("CPU %",      color="steelblue")
        ax2.set_ylabel("Memory (MB)", color="darkorange")
        ax1.set_title("MySQL Docker Container Load During Stress Test")
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
        plt.tight_layout()
        p = output_dir / "container_cpu_memory.png"
        plt.savefig(p, dpi=120)
        plt.close()
        saved.append(str(p))
    else:
        print("  No Docker stats series collected — container_cpu_memory.png skipped.")

    return saved


# ── Summary table ─────────────────────────────────────────────────


def print_summary_table(results: List[ScenarioResult]) -> None:
    header = f"{'Scenario':<22} {'Spec Requirement':<28} {'Result':<7} {'Ops':>6} {'Success%':>9} {'Avg ms':>8} {'p99 ms':>8} {'ops/s':>7}"
    sep    = "─" * len(header)
    print(f"\n{sep}")
    print(header)
    print(sep)
    for r in results:
        status  = "✅ PASS" if r.passed else "❌ FAIL"
        ops     = r.metrics.get("ops_total", "-")
        rate    = f"{r.metrics.get('success_rate', 0):.1%}"
        avg_ms  = f"{r.metrics.get('avg_ms', 0):.1f}"
        p99_ms  = f"{r.metrics.get('p99_ms', 0):.1f}"
        ops_sec_val = r.metrics.get("ops_per_second") or (
            round(r.metrics.get("ops_total", 0) / max(r.metrics.get("elapsed_ms", 1) / 1000, 0.001), 1)
        )
        ops_sec = f"{ops_sec_val:.1f}"
        print(
            f"{r.name:<22} {r.spec_requirement:<28} {status:<7} "
            f"{str(ops):>6} {rate:>9} {avg_ms:>8} {p99_ms:>8} {ops_sec:>7}"
        )
    print(sep)

    # Per-scenario invariant notes
    print()
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.name}")
        # Print key invariants
        for k, v in r.invariants.items():
            if k in ("server_error_details", "per_thread", "db_ground_truth",
                     "integrity_check", "integrity_after_load",
                     "pre_failure_table_counts", "post_recovery_table_counts"):
                continue
            print(f"       {k}: {v}")
        if r.notes:
            # Wrap at 90 chars
            words = r.notes.split()
            line  = "       NOTE: "
            for w in words:
                if len(line) + len(w) > 90:
                    print(line)
                    line = "             " + w + " "
                else:
                    line += w + " "
            if line.strip():
                print(line)
        print()


# ── Main orchestration ────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Campus Trading MySQL Stress Test Suite",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--backend-url", default="http://localhost:8080/api/v1",
        help="Base URL of the Go backend API",
    )
    parser.add_argument(
        "--backend-dir", default=str(DEFAULT_BACKEND_DIR),
        help="Path to the Go backend source directory (Assignment_2/Module_B/backend)",
    )
    parser.add_argument(
        "--compose-file", default=str(DEFAULT_COMPOSE),
        help="Path to docker-compose.yml for the MySQL container",
    )
    parser.add_argument(
        "--no-start-docker", action="store_true",
        help="Skip starting MySQL container (assume it's already running)",
    )
    parser.add_argument(
        "--no-start-backend", action="store_true",
        help="Skip starting the Go backend (assume it's already running)",
    )
    parser.add_argument(
        "--skip-failure-sim", action="store_true",
        help="Skip the failure_simulation scenario (which temporarily stops Docker)",
    )
    parser.add_argument(
        "--target-ops", type=int, default=1000,
        help="Number of operations for the stress_bulk scenario",
    )
    args = parser.parse_args()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)

    base_url    = args.backend_url.rstrip("/")
    backend_dir = Path(args.backend_dir)
    backend_proc: Optional[subprocess.Popen] = None

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   Campus Trading — MySQL Stress Test Suite (Module B)    ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # ── 1. MySQL ──────────────────────────────────────────────────
    print("\n[1/5] MySQL Docker container")
    if not args.no_start_docker:
        if not start_mysql(args.compose_file):
            return 1
    else:
        print("  Skipping (--no-start-docker)")

    # ── 2. Go backend ─────────────────────────────────────────────
    print("\n[2/5] Go backend")
    if not args.no_start_backend:
        backend_proc = start_backend(backend_dir, base_url)
        if backend_proc is None:
            return 1
    else:
        print("  Skipping (--no-start-backend)")
        if not _wait_for_backend(base_url, timeout=10):
            print(f"  WARNING: backend at {base_url} is not responding.")

    # ── 3. Seed ───────────────────────────────────────────────────
    print("\n[3/5] Seeding test data")
    run_id = secrets.token_hex(3)
    try:
        seed = seed_data(base_url, run_id, n_sellers=5, n_buyers=25)
    except Exception as exc:
        print(f"  ERROR during seeding: {exc}")
        if backend_proc:
            backend_proc.terminate()
        return 1

    # ── 4. Scenarios ──────────────────────────────────────────────
    print("\n[4/5] Running scenarios")

    db_verifier    = DBVerifier()
    docker_monitor = DockerMonitor(container="campus_a3_mysql")
    all_results: List[ScenarioResult] = []

    # 4a — concurrent_users
    print("  ▶ concurrent_users ...")
    r1 = s_concurrent.run(
        base_url=base_url,
        users=seed["sellers"] + seed["buyers"],
        listing_ids=seed["listing_ids"],
        category_id=seed["category_id"],
        docker_monitor=None,
    )
    all_results.append(r1)
    print(f"    {'✅' if r1.passed else '❌'} success_rate={r1.invariants['success_rate']:.1%}"
          f"  server_5xx={r1.invariants['server_errors_5xx']}")

    # 4b — offer_race
    print("  ▶ offer_race ...")
    if seed["race_listing_id"] and seed["race_offer_ids"]:
        r2 = s_race.run(
            base_url=base_url,
            seller=seed["race_seller"],
            buyers=seed["buyers"][:10],
            listing_id=seed["race_listing_id"],
            offer_ids=seed["race_offer_ids"],
            db_verifier=db_verifier,
            docker_monitor=None,
        )
    else:
        r2 = ScenarioResult(
            name="offer_race",
            spec_requirement="Race Condition Testing",
            passed=False,
            metrics={},
            invariants={"error": "race listing was not seeded correctly"},
        )
    all_results.append(r2)
    db_gt = r2.invariants.get("db_ground_truth", {})
    race_flag = "⚠ RACE DETECTED" if r2.invariants.get("race_condition_detected") else "contained by MySQL"
    print(f"    {'✅' if r2.passed else '❌'} accepted={db_gt.get('accepted_offers','?')}"
          f"  transactions={db_gt.get('total_transactions','?')}  [{race_flag}]")

    # 4c — failure_simulation (optional)
    if not args.skip_failure_sim:
        print("  ▶ failure_simulation ...")
        r3 = s_failure.run(
            base_url=base_url,
            listing_ids=seed["listing_ids"],
            buyers=seed["buyers"][10:20],
            db_verifier=db_verifier,
            docker_monitor=None,
            n_concurrent=10,
        )
        all_results.append(r3)
        print(f"    {'✅' if r3.passed else '❌'}"
              f" mysql_recovered={r3.invariants.get('mysql_recovered')}"
              f"  integrity={'OK' if r3.invariants.get('no_orphan_data') else 'VIOLATION'}")

        # Reconnect DB verifier after the container was restarted
        time.sleep(2)
        db_verifier.connect()
    else:
        print("  ▶ failure_simulation ... SKIPPED (--skip-failure-sim)")

    # 4d — stress_bulk
    print(f"  ▶ stress_bulk ({args.target_ops} ops, 20 concurrent workers) ...")
    r4 = s_bulk.run(
        base_url=base_url,
        users=seed["sellers"] + seed["buyers"],   # all users for reads
        buyers=seed["buyers"],                     # buyers only for writes
        listing_ids=seed["listing_ids"],
        category_id=seed["category_id"],
        target_ops=args.target_ops,
        concurrency=20,
        db_verifier=db_verifier,
        docker_monitor=docker_monitor,
    )
    all_results.append(r4)
    print(f"    {'✅' if r4.passed else '❌'}"
          f" ops/sec={r4.metrics.get('ops_per_second', 0):.0f}"
          f"  p99={r4.metrics.get('p99_ms', 0):.1f} ms"
          f"  cpu_peak={r4.docker_stats_peak.get('cpu_pct', 0):.1f}%"
          f"  mem_peak={r4.docker_stats_peak.get('mem_mb', 0):.0f} MB")

    # ── 5. Report ─────────────────────────────────────────────────
    print("\n[5/5] Report & charts")

    chart_paths = generate_charts(all_results, CHARTS)
    if chart_paths:
        print(f"  Charts saved: {', '.join(Path(p).name for p in chart_paths)}")

    print_summary_table(all_results)

    all_passed = all(r.passed for r in all_results)

    def _serialise(r: ScenarioResult) -> Dict[str, Any]:
        d = r.__dict__.copy()
        # docker_time_series can be large — summarise in JSON, keep full in charts
        d["docker_time_series_samples"] = len(d.pop("docker_time_series", []))
        return d

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend_url":       base_url,
        "run_id":            run_id,
        "all_passed":        all_passed,
        "scenarios":         [_serialise(r) for r in all_results],
        "charts":            chart_paths,
    }

    results_json = ARTIFACTS / "results.json"
    results_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    stdout_lines: List[str] = []
    for r in all_results:
        stdout_lines += [
            f"=== {r.name} ({r.spec_requirement}) ===",
            f"passed: {r.passed}",
            json.dumps(_serialise(r), indent=2, default=str),
            "",
        ]
    (ARTIFACTS / "stdout.txt").write_text("\n".join(stdout_lines), encoding="utf-8")

    print(f"\n  Artifacts  : {ARTIFACTS}")
    print(f"  JSON report: {results_json}")
    print()
    status_line = "✅ ALL SCENARIOS PASSED" if all_passed else "❌ SOME SCENARIOS FAILED — see report"
    print(f"  {status_line}")
    print()

    # ── Cleanup ───────────────────────────────────────────────────
    db_verifier.disconnect()
    if backend_proc:
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
        except Exception:
            pass

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
