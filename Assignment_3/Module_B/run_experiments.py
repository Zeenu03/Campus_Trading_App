#!/usr/bin/env python3
"""
Assignment 3 — Module B experiment batch.

Runs the stress_driver scenarios with parameters aligned to the assignment
spec (concurrency, race conditions, failure injection, high-volume stress).

Outputs:
  Assignment_3/artifacts/module_b_results.json
  Assignment_3/artifacts/module_b_stdout.txt   (optional human-readable log)

Run from anywhere:
  python3 Assignment_3/Module_B/run_experiments.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ASSIGNMENT_3 = Path(__file__).resolve().parents[1]
MODULE_A = ASSIGNMENT_3 / "Module_A"
ARTIFACTS = ASSIGNMENT_3 / "artifacts"
STRESS = MODULE_A / "scripts" / "stress_driver.py"
PYTHON = sys.executable


def _run_scenario(args: list[str]) -> dict:
    proc = subprocess.run(
        [PYTHON, str(STRESS), *args],
        cwd=str(MODULE_A),
        capture_output=True,
        text=True,
        check=False,
    )
    payload: dict
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {
            "parse_error": True,
            "raw_stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }
    payload["exit_code"] = proc.returncode
    if proc.stderr:
        payload["stderr_tail"] = proc.stderr[-2000:]
    return payload


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    experiments = [
        {
            "name": "concurrent_race_same_listing",
            "description": "Many threads compete to accept offers on the same listing (Module B: race / same data).",
            "args": ["--scenario", "accept_race", "--threads", "25", "--iterations", "10"],
        },
        {
            "name": "concurrent_load_separate_listings",
            "description": "Parallel accepts on distinct listings (throughput under global serialization).",
            "args": ["--scenario", "accept_load", "--threads", "15", "--iterations", "5"],
        },
        {
            "name": "failure_injection_rollback",
            "description": "Random mid-transaction failures; verify no partial committed state.",
            "args": ["--scenario", "failure_injection", "--threads", "10", "--iterations", "8"],
        },
        {
            "name": "crash_recovery_durability",
            "description": "Commit then WAL replay (durability after restart).",
            "args": ["--scenario", "crash_recovery"],
        },
        {
            "name": "stress_bulk_1000_ops",
            "description": "≥1000 accept_offer attempts (50 waves × 20 threads); correctness + timing.",
            "args": ["--scenario", "stress_bulk", "--waves", "50", "--threads", "20"],
        },
        {
            "name": "stress_bulk_2500_ops",
            "description": "Extended load: 2500 operations for robustness under load reporting.",
            "args": ["--scenario", "stress_bulk", "--waves", "125", "--threads", "20"],
        },
    ]

    lines: list[str] = []
    results: list[dict] = []
    all_passed = True

    for ex in experiments:
        lines.append(f"=== {ex['name']} ===")
        lines.append(ex["description"])
        out = _run_scenario(ex["args"])
        out["experiment_name"] = ex["name"]
        results.append(out)
        passed = out.get("passed", False) and out.get("exit_code") == 0
        if not passed:
            all_passed = False
        lines.append(json.dumps({k: out[k] for k in out if k not in ("stderr_tail",)}, indent=2))
        lines.append("")

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "assignment": "CS432 Assignment 3 Module B",
        "python": PYTHON,
        "all_experiments_passed": all_passed,
        "experiments": results,
    }

    out_json = ARTIFACTS / "module_b_results.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    log_path = ARTIFACTS / "module_b_stdout.txt"
    log_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {out_json}")
    print(f"Wrote {log_path}")
    print(f"All passed: {all_passed}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
