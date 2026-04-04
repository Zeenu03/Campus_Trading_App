# Module B — Stress Test Results Guide

This guide explains how to run the stress experiments, what every field in
the JSON output means, and how to diagnose failures.

---

## Running the experiments

```bash
# From the repo root — runs all 8 experiments and writes two artifact files
python3 Assignment_3/Module_B/B+tree/run_experiments.py

# Artifacts produced
Assignment_3/Module_B/B+tree/artifacts/module_b_results.json   # machine-readable full results
Assignment_3/Module_B/B+tree/artifacts/module_b_stdout.txt     # human-readable log
```

To run a single scenario directly:

```bash
# From Assignment_3/Module_A/
python3 scripts/stress_driver.py --scenario <name> [--threads N] [--iterations N] [--waves N]
```

Exit code `0` = all invariants passed. `1` = at least one failure.

---

## Experiment catalogue

| Experiment name | Scenario flag | Spec requirement covered |
|---|---|---|
| `concurrent_race_same_listing` | `accept_race` | Concurrent usage, Race conditions, Isolation |
| `concurrent_load_separate_listings` | `accept_load` | Throughput under serialization |
| `failure_injection_rollback` | `failure_injection` | Failure simulation, Atomicity |
| `crash_recovery_durability` | `crash_recovery` | Durability |
| `stress_bulk_1000_ops` | `stress_bulk` | Stress (1 000 ops), response time |
| `stress_bulk_2500_ops` | `stress_bulk` | Stress (2 500 ops), response time |
| `consistency_check` | `consistency_check` | Consistency, referential integrity |
| `mixed_concurrent_failure` | `mixed_concurrent_failure` | Failures under live concurrency |

---

## Top-level result envelope

Every scenario produces a JSON object with this structure:

```json
{
  "scenario":   "accept_race",
  "threads":    25,
  "iterations": 10,
  "waves":      50,
  "elapsed_ms": 1234.5,
  "invariants": { ... },
  "passed":     true
}
```

| Field | Type | Meaning |
|---|---|---|
| `scenario` | string | The `--scenario` flag value used |
| `threads` | int | `--threads` value (concurrent thread count) |
| `iterations` | int | `--iterations` value (independent repetitions) |
| `waves` | int | `--waves` value (only for `stress_bulk`) |
| `elapsed_ms` | float | Wall-clock time for the whole scenario in milliseconds |
| `invariants` | object | Scenario-specific result fields (see below) |
| `passed` | bool | `true` iff all boolean invariants inside `invariants` are true |

---

## Scenario-by-scenario field reference

### `accept_race` — Isolation / Race Conditions

```json
{
  "single_winner_per_run": true,
  "winners_per_run": [1, 1, 1, 1, 1],
  "deep_state_all_iterations": true,
  "per_iteration_deep": [
    {
      "accepted_offer_count": 1,
      "declined_offer_count": 24,
      "sold_listing_count": 1,
      "completed_transaction_count": 1,
      "offer_txn_referential_match": true,
      "exactly_one_accepted": true,
      "exactly_one_sold_listing": true,
      "exactly_one_completed_txn": true,
      "declined_count_correct": true,
      "all_invariants_pass": true
    }
  ]
}
```

| Field | Expected healthy value | What it proves |
|---|---|---|
| `single_winner_per_run` | `true` | No two threads simultaneously committed on the same listing |
| `winners_per_run` | All `1` | Per-iteration breakdown — any value ≠ 1 shows the exact failing run |
| `deep_state_all_iterations` | `true` | All four-table deep checks passed across every iteration |
| `accepted_offer_count` | `1` | Exactly one offer won |
| `declined_offer_count` | `threads - 1` | Winner correctly marked all other offers Declined |
| `sold_listing_count` | `1` | Listing status updated atomically |
| `completed_transaction_count` | `1` | Exactly one committed Transaction row |
| `offer_txn_referential_match` | `true` | The OfferID on the Completed Transaction matches the Accepted Offer's key |

**Diagnosing failures:**
- `single_winner_per_run: false` — the serial lock was bypassed; two threads committed simultaneously.
- `declined_count_correct: false` — Step 2 of `accept_offer_atomic` (decline competing offers) ran partially and was not rolled back.
- `offer_txn_referential_match: false` — the Transaction row was inserted with a wrong OfferID; data integrity bug in `campus_workflow.py`.

---

### `accept_load` — Throughput

```json
{
  "all_succeeded": true,
  "total_ops_ok": 75,
  "total_ops": 75,
  "per_iteration": [
    {
      "ops_total": 15,
      "ops_ok": 15,
      "ops_fail": 0,
      "success_rate": 1.0,
      "latency_avg_ms": 0.842,
      "latency_p99_ms": 1.204,
      "latency_max_ms": 1.411,
      "all_succeeded": true
    }
  ]
}
```

| Field | Expected | What it proves |
|---|---|---|
| `all_succeeded` | `true` | All independent offers committed — no false rejections |
| `total_ops_ok` | `threads × iterations` | Every operation committed |
| `success_rate` | `1.0` | No spurious failures |
| `latency_avg_ms` | — | Average per-operation commit time |
| `latency_p99_ms` | — | 99th percentile — high values indicate lock contention or slow B+ Tree paths |

**Diagnosing failures:**
- `all_succeeded: false` — a thread failed even though it had no competition; look at `per_iteration` to find which run and check the engine logs.
- High `latency_p99_ms` (e.g. >100 ms per op) — the WAL write or B+ Tree rebalance is a bottleneck.

---

### `failure_injection` — Atomicity / Rollback

```json
{
  "all_rollbacks_clean": true,
  "offer_statuses_always_ok": true,
  "listing_statuses_always_ok": true,
  "txn_counts_always_ok": true,
  "notif_counts_always_ok": true,
  "per_iteration_clean": [
    {
      "stuck_offers": [],
      "stuck_listings": [],
      "offer_statuses_clean": true,
      "listing_statuses_clean": true,
      "transaction_count_ok": true,
      "notification_count_ok": true,
      "clean": true
    }
  ]
}
```

| Field | Expected | What it proves |
|---|---|---|
| `all_rollbacks_clean` | `true` | Every iteration left all four tables in their pre-transaction state |
| `offer_statuses_always_ok` | `true` | No Offer row stuck in "Accepted" or "Declined" after a failed transaction |
| `listing_statuses_always_ok` | `true` | No Listing stuck in "Sold" after a failed transaction |
| `txn_counts_always_ok` | `true` | No Transaction rows were left by a rolled-back transaction |
| `notif_counts_always_ok` | `true` | No Notification rows were left by a rolled-back transaction |
| `stuck_offers` | `[]` | Non-empty means specific offer rows are corrupted; includes `offer_id` and wrong `status` |
| `stuck_listings` | `[]` | Non-empty means specific listing rows are corrupted; includes `listing_id` and wrong `status` |

**Diagnosing failures:**
- `offer_statuses_always_ok: false` — rollback did not undo the Offer update (Step 1). Check `_undo_change` in `db_manager.py` for UPDATE undo logic.
- `listing_statuses_always_ok: false` — rollback did not undo the Listing update (Step 3). Same undo path.
- `txn_counts_always_ok: false` — rollback did not undo a Transaction INSERT. Check INSERT undo in `_undo_change`.
- Look at `stuck_offers` / `stuck_listings` arrays to see exactly which row IDs are wrong and what status they are stuck in.

---

### `crash_recovery` — Durability

```json
{
  "committed": true,
  "redo_applied": 7,
  "listing_sold_after_recovery": true,
  "passed": true
}
```

| Field | Expected | What it proves |
|---|---|---|
| `committed` | `true` | The original transaction committed before the simulated crash |
| `redo_applied` | `> 0` | WAL replay applied at least one REDO operation |
| `listing_sold_after_recovery` | `true` | The Listing's "Sold" status persisted across the crash via WAL replay |
| `passed` | `true` | Durability confirmed |

**Diagnosing failures:**
- `redo_applied: 0` — the WAL was not written before the crash or `RecoveryManager` did not read it correctly.
- `listing_sold_after_recovery: false` — the WAL REDO did not replay the Listing update; check `recover_into` in `recovery.py`.

---

### `stress_bulk` — High-Volume Stress + Response Time

```json
{
  "waves": 50,
  "threads_per_wave": 20,
  "total_operations": 1000,
  "total_successful_commits": 50,
  "elapsed_ms": 3412.7,
  "ops_per_second": 293.0,
  "latency_avg_ms": 3.124,
  "latency_p99_ms": 8.902,
  "latency_max_ms": 14.331,
  "winners_per_wave": [1, 1, 1, ...],
  "invariants": {
    "exactly_one_winner_each_wave": true,
    "total_winners_equals_waves": true
  }
}
```

| Field | Expected | What it proves |
|---|---|---|
| `total_successful_commits` | `== waves` | Every race had exactly one winner across all waves |
| `exactly_one_winner_each_wave` | `true` | No wave had 0 or 2+ winners |
| `ops_per_second` | — | System throughput; useful for report performance section |
| `latency_avg_ms` | — | Mean time for one `accept_offer_atomic` call under load |
| `latency_p99_ms` | — | 99th percentile latency; indicates worst-case user experience |
| `latency_max_ms` | — | Slowest single operation across the entire run |
| `winners_per_wave` | All `1` | Per-wave breakdown; scan for any value ≠ 1 |

**Diagnosing failures:**
- `total_winners_equals_waves: false` — a wave had 0 winners (listing already Sold before any thread ran, likely a bootstrap bug) or 2+ winners (lock broken).
- High `latency_p99_ms` relative to `latency_avg_ms` — tail latency spikes; can indicate GIL contention or slow disk for WAL writes.

---

### `consistency_check` — Data Consistency / Referential Integrity

```json
{
  "winners": 1,
  "race_invariants": {
    "accepted_offer_count": 1,
    "declined_offer_count": 9,
    "sold_listing_count": 1,
    "completed_transaction_count": 1,
    "offer_txn_referential_match": true,
    "all_invariants_pass": true
  },
  "referential_integrity": {
    "violations": [],
    "violation_count": 0,
    "referential_integrity_ok": true
  },
  "passed": true
}
```

| Field | Expected | What it proves |
|---|---|---|
| `race_invariants.all_invariants_pass` | `true` | Four-table state is correct (see `accept_race` section) |
| `referential_integrity_ok` | `true` | No cross-table inconsistencies |
| `violations` | `[]` | Empty = all checks pass |
| `violation_count` | `0` | Number of integrity violations found |

**What violations look like:**

```json
"violations": [
  "Transaction 3: OfferID 2005 not found in Offer table",
  "Transaction 1: AgreedPrice 90.0 != Offer 2000 AgreedPrice 92.5"
]
```

Each violation string names the Transaction row, the check that failed, and the values involved.

**Diagnosing failures:**
- `OfferID not found` — a Transaction was inserted with a key that doesn't exist in the Offer table; WAL replay or the insert step used the wrong ID.
- `AgreedPrice mismatch` — the Transaction was committed with a different price than the Offer; check Step 4 in `campus_workflow.py` (`_build_transaction_record`).
- `Multiple Completed transactions share the same OfferID` — the isolation lock was bypassed and two transactions both accepted the same offer.

---

### `mixed_concurrent_failure` — Failures Under Live Concurrency

```json
{
  "threads": 10,
  "iterations": 8,
  "all_exactly_one_winner": true,
  "all_deep_state_pass": true,
  "all_referential_integrity": true,
  "per_iteration": [
    {
      "winners": 1,
      "n_normal_threads": 5,
      "n_failing_threads": 5,
      "exactly_one_winner": true,
      "deep_state": { "all_invariants_pass": true, ... },
      "referential_integrity": { "referential_integrity_ok": true, ... },
      "iteration_passed": true
    }
  ],
  "passed": true
}
```

| Field | Expected | What it proves |
|---|---|---|
| `all_exactly_one_winner` | `true` | Even with half the threads injecting failures, isolation holds |
| `all_deep_state_pass` | `true` | Failing threads left no stuck Offers or Listings |
| `all_referential_integrity` | `true` | Cross-table integrity holds when both committed and rolled-back transactions mix |
| `n_normal_threads` | `threads // 2` | Non-failing competitors per iteration |
| `n_failing_threads` | `threads - threads // 2` | Threads guaranteed to fail mid-transaction |
| `iteration_passed` | `true` | All three checks passed for this iteration |

**Diagnosing failures:**
- `all_exactly_one_winner: false` — either 0 winners (all non-failing threads were rejected before they could commit — impossible if locking works) or 2+ winners (lock broken).
- `all_deep_state_pass: false` — a failing thread's partial writes (e.g. Offer status → "Accepted") were not rolled back. Inspect `deep_state.stuck_offers` in the failing iteration.
- `all_referential_integrity: false` — a partial insert from a failing thread leaked into the committed state. Check WAL rollback marker handling in `RecoveryManager`.

---

## Reading `module_b_results.json`

The full output file has this shape:

```json
{
  "generated_at_utc": "2026-04-04T10:00:00+00:00",
  "assignment": "CS432 Assignment 3 Module B",
  "python": "/usr/bin/python3",
  "all_experiments_passed": true,
  "experiments": [
    {
      "experiment_name": "concurrent_race_same_listing",
      "scenario": "accept_race",
      "passed": true,
      "exit_code": 0,
      "invariants": { ... }
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `all_experiments_passed` | `true` only if every experiment's `passed` and `exit_code == 0` |
| `exit_code` | Process exit code from the driver: `0` = passed, `1` = failed |
| `stderr_tail` | Present only if the scenario printed to stderr (errors, tracebacks) |

---

## Quick diagnostic checklist

When `all_experiments_passed` is `false`:

1. Find the first experiment where `"passed": false` or `"exit_code": 1`.
2. Check `stderr_tail` for Python tracebacks — these indicate a code error, not a logic failure.
3. Inspect `invariants` for the first `false` boolean value.
4. Use the per-scenario tables above to identify the exact check that failed.
5. Look at `stuck_offers` / `stuck_listings` / `violations` arrays for the specific row IDs involved.
6. Cross-reference the failing row ID against the WAL log file in `Assignment_3/Module_A/artifacts/acid_demo/` to see the sequence of operations that produced it.
