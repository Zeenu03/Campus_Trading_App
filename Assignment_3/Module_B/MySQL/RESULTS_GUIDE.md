# Module B — MySQL Stress Test Suite: Results Guide

This document explains how to run the stress suite and interpret every
piece of output it produces.

---

## Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Docker Desktop | running | `docker info` |
| Go | 1.21+ | `go version` |
| Python | 3.10+ | `python3 --version` |
| pip packages | see below | `pip install -r requirements.txt` |

```bash
cd Assignment_3/Module_B/MySQL
pip install -r requirements.txt
```

No port conflicts on **3306** (MySQL) or **8080** (Go backend).

---

## Running the Suite

### Full automatic run (recommended)
```bash
python3 Assignment_3/Module_B/MySQL/run_stress.py
```
This starts MySQL, compiles and starts the Go backend, seeds test data,
runs all 4 scenarios, then generates charts and a JSON report.

### Backend already running
```bash
python3 run_stress.py --no-start-backend
```

### MySQL container already running
```bash
python3 run_stress.py --no-start-docker
```

### Faster run (fewer operations)
```bash
python3 run_stress.py --target-ops 200 --skip-failure-sim
```

### All flags
| Flag | Default | Description |
|------|---------|-------------|
| `--backend-url` | `http://localhost:8080/api/v1` | REST API base URL |
| `--backend-dir` | `Assignment_2/Module_B/backend` | Go backend source root |
| `--compose-file` | `docker-compose.yml` (in this dir) | MySQL compose file |
| `--no-start-docker` | off | Skip `docker compose up` |
| `--no-start-backend` | off | Skip `go run ./...` |
| `--skip-failure-sim` | off | Skip the container-kill scenario |
| `--target-ops` | 1000 | Ops for the stress_bulk scenario |

---

## Output Artifacts

All output lands in `Assignment_3/Module_B/MySQL/artifacts/`.

```
artifacts/
├── results.json            ← machine-readable full report
├── stdout.txt              ← per-scenario JSON blobs
└── charts/
    ├── latency_by_scenario.png
    ├── error_rate.png
    ├── throughput_by_scenario.png
    └── container_cpu_memory.png
```

---

## Scenarios & What They Test

### 1 — `concurrent_users` (Spec: Concurrent Usage)

**What it does:** 20 user threads are released simultaneously via a
`threading.Barrier`. Each thread is assigned a role by its index:

| Role | Operation | Expected |
|------|-----------|---------|
| Reader   (idx%4==0) | 5× GET /listings | 200 OK |
| Lister   (idx%4==1) | POST /listings | 201 Created |
| Offerer  (idx%4==2) | POST /offers | 201 / 409 Conflict |
| Notifier (idx%4==3) | 3× GET /notifications | 200 OK |

**Pass criteria:**
- `success_rate ≥ 90 %`
- `server_errors_5xx == 0`

**Key invariants in JSON:**
```json
"invariants": {
  "n_threads": 20,
  "threads_completed": 20,
  "success_rate": 0.9500,
  "server_errors_5xx": 0,
  "no_server_errors": true,
  "high_success_rate": true
}
```

---

### 2 — `offer_race` (Spec: Race Condition Testing)

**What it does:** Exposes the TOCTOU (Time-Of-Check / Time-Of-Use) race
window in the `AcceptOffer` Go handler.

Setup: 1 listing owned by Seller A; 10 buyers each have a `Submitted`
offer. The seller opens 10 browser tabs simultaneously — each tab calls
`PUT /offers/{id}/accept` for a *different* offer.

Because the status check (`if offerStatus != 'Submitted'`) happens
**before** the MySQL transaction begins, two threads can both read
`Submitted` and both enter the transaction. InnoDB then either:

- **Detects a deadlock** (both threads hold row-locks on each other's
  offer row) → rolls back one → 1 winner ✅
- **Allows both** to update separate rows before the batch-decline runs
  → 2 Accepted offers → race condition detected ⚠

The DB verifier (direct MySQL query) provides the ground truth.

**Key invariants:**
```json
"db_ground_truth": {
  "accepted_offers": 1,
  "declined_offers": 9,
  "submitted_offers": 0,
  "total_transactions": 1,
  "listing_status": "Sold",
  "exactly_one_accepted": true,
  "race_condition_detected": false,
  "all_invariants_pass": true
}
```

If `race_condition_detected: true`, the scenario is marked **FAIL** and
the notes field describes the observed violation. The recommended fix is
a `SELECT ... FOR UPDATE` on the offer row inside the transaction, or a
`SELECT Status FROM Listing ... FOR UPDATE` on the listing row.

---

### 3 — `failure_simulation` (Spec: Failure Simulation)

**What it does:** Demonstrates InnoDB atomicity on abrupt container failure.

| Phase | Action |
|-------|--------|
| Phase 1 | 10 buyer threads submit offers with staggered start times |
| Phase 2 | `docker stop campus_a3_mysql` fired mid-way through |
| Phase 3 | `docker start campus_a3_mysql` + DB verifier reconnects |
| Phase 4 | `full_integrity_check()` validates no orphaned rows |

Any transaction that was in-flight at kill time is automatically rolled
back by InnoDB during crash recovery — this is the durability guarantee.

**Pass criteria:**
- Container stops and restarts successfully
- MySQL reconnects within 70 s
- `full_integrity_check.all_clean == true`

**Key invariants:**
```json
"invariants": {
  "container_stopped": true,
  "container_restarted": true,
  "mysql_recovered": true,
  "requests_committed_before_kill": 4,
  "requests_failed_during_kill": 6,
  "integrity_check": {
    "orphan_transactions": {"clean": true},
    "accepted_without_transaction": {"clean": true},
    "sold_without_transaction": {"clean": true},
    "all_clean": true
  },
  "no_orphan_data": true
}
```

---

### 4 — `stress_bulk` (Spec: Stress Testing)

**What it does:** Fires 1 000+ mixed API calls with 20 concurrent workers.
Operation mix: ~60 % reads, ~40 % writes. A `DockerMonitor` background
thread polls `docker stats campus_a3_mysql --no-stream` every second and
records CPU % and memory MB throughout.

**Pass criteria:**
- `ops_attempted ≥ target_ops × 90 %`
- `success_rate ≥ 85 %`
- `full_integrity_check.all_clean == true` after load

**Key metrics:**
```json
"metrics": {
  "ops_total": 1000,
  "ops_ok": 912,
  "ops_fail": 88,
  "success_rate": 0.9120,
  "avg_ms": 18.4,
  "p99_ms": 65.2,
  "max_ms": 201.0,
  "ops_per_second": 47.3,
  "target_ops": 1000,
  "concurrency": 20
}
```

**Docker stats peak** (from container_cpu_memory.png):
```json
"docker_stats_peak": {
  "cpu_pct": 14.3,
  "mem_mb": 215.8,
  "avg_cpu_pct": 8.1,
  "avg_mem_mb": 198.4,
  "samples": 42
}
```

---

## Charts

### `latency_by_scenario.png`
Grouped bar chart with **Avg / p99 / Max** latency (ms) per scenario.
Look for high max values — they indicate lock-wait or GC pauses.

### `error_rate.png`
Stacked bar: **green = success**, **red = failure** per scenario.
The offer_race scenario will show mostly failures (only 1 of N accepts
succeeds via HTTP — all others get 409 Conflict).

### `throughput_by_scenario.png`
Bar chart of **ops/sec** per scenario. stress_bulk dominates because it
runs the most operations.

### `container_cpu_memory.png`
Dual-axis time series recorded during **stress_bulk only**.
- Blue line = MySQL container CPU %
- Orange dashed line = container memory MB
Spikes during write-heavy waves show InnoDB buffer pool pressure.

---

## results.json Structure

```json
{
  "generated_at_utc": "2026-04-04T10:00:00+00:00",
  "backend_url":       "http://localhost:8080/api/v1",
  "run_id":            "a3b2c1",
  "all_passed":        true,
  "scenarios": [
    {
      "name":              "offer_race",
      "spec_requirement":  "Race Condition Testing",
      "passed":            true,
      "metrics":           { "ops_total": 10, "success_rate": 0.1, ... },
      "invariants":        { "db_ground_truth": { ... }, ... },
      "docker_stats_peak": { "cpu_pct": 4.2, "mem_mb": 192 },
      "docker_time_series_samples": 0,
      "notes":             "MySQL isolation ... prevented the race."
    }
  ],
  "charts": [ "...latency_by_scenario.png", ... ]
}
```

`all_passed: true` means every scenario met its invariants.

---

## Quick Diagnostic Checklist

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `concurrent_users` FAIL, `server_errors_5xx > 0` | Go panic or DB exhausted | Check backend stderr; lower concurrency |
| `offer_race` FAIL, `race_condition_detected: true` | TOCTOU in AcceptOffer | Add `SELECT ... FOR UPDATE` inside transaction |
| `failure_simulation` FAIL, `mysql_recovered: false` | MySQL slow to restart | Increase `_wait_for_mysql` timeout; check Docker resources |
| `stress_bulk` FAIL, `success_rate < 85 %` | Connection pool exhausted or listing sold mid-run | Increase `DB.SetMaxOpenConns`; add more listings |
| `container_cpu_memory.png` not generated | Docker not running or stats unavailable | Ensure Docker Desktop is running; check container name |
| Charts skipped | matplotlib not installed | `pip install matplotlib` |

---

## Architecture Overview

```
run_stress.py
├── docker compose up -d  (campus_a3_mysql)
├── go run ./...          (Campus Trading backend)
├── seed_data()           (REST API calls)
└── scenarios/
    ├── concurrent_users.py   → helpers/api_client, helpers/metrics
    ├── offer_race.py         → helpers/api_client, helpers/db_verifier
    ├── failure_simulation.py → helpers/api_client, helpers/db_verifier
    └── stress_bulk.py        → helpers/api_client, helpers/db_verifier
                                helpers/docker_monitor
```
