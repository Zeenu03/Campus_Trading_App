# Assignment 3 — Combined Report (Module A + Module B)

This document satisfies the report expectations in **Assignment 3** (correctness, failures, multi-user conflicts, experiments, observations, limitations) and maps work to the **evaluation criteria**.

- **Module A artifacts generated (UTC):** 2026-04-01T17:01:07.691133+00:00
- **Module B batch generated (UTC):** 2026-04-01T17:01:09.004797+00:00
- **Primary evidence files:**
  - [`Module_A/artifacts/phase6_summary.json`](Module_A/artifacts/phase6_summary.json)
  - [`artifacts/module_b_results.json`](artifacts/module_b_results.json)

---

## 1. Module A — Transaction engine (B+ Tree storage)

### 1.1 BEGIN, COMMIT, and ROLLBACK

- **Multi-step business transaction:** `accept_offer_atomic` uses `begin_transaction` → updates across **Offer**, **Listing**, **Transaction**, and optionally **Notification** → `commit_transaction` or automatic `rollback_transaction` on error.
- **Normal commit (manual API):** Scenario `explicit_commit` in phase-6 artifacts: `BEGIN` → `tx_insert` → `COMMIT`; row remains visible after commit.
- **Manual rollback:** Scenario `explicit_manual_rollback`: `BEGIN` → `tx_insert` → `ROLLBACK`; inserted row is removed (physical undo).

Key artifact fields:

```json
{
  "explicit_commit": {
    "commit_ok": true,
    "row_present_after_commit": true,
    "wal_tail_types": [
      "BEGIN",
      "INSERT",
      "COMMIT"
    ],
    "invariants": {
      "commit_succeeded": true,
      "row_visible_after_commit": true
    }
  },
  "explicit_manual_rollback": {
    "rollback_ok": true,
    "visible_mid_transaction": true,
    "row_absent_after_rollback": true,
    "wal_tail_types": [
      "BEGIN",
      "INSERT",
      "ROLLBACK"
    ],
    "invariants": {
      "rollback_succeeded": true,
      "no_partial_row_after_rollback": true
    }
  }
}
```

### 1.2 ACID properties (how they are upheld)

| Property | Mechanism | Evidence |
|----------|-----------|----------|
| **Atomicity** | Single transaction boundary; rollback undoes all logged changes. | `atomic_failure_rollback` (injected failure), `explicit_manual_rollback`, unit tests phase 1–2. |
| **Consistency** | Business rules inside `accept_offer_atomic` (seller, status, submitted offer). | Phase 2 tests (invalid accept paths leave DB unchanged). |
| **Isolation** | **Serializable:** `DatabaseManager._serial_lock` — one live transaction at a time globally. | Phase 5 concurrency tests; Module B race scenarios. |
| **Durability** | WAL append; `fsync` on commit; recovery **REDO** for committed txns. | `recovery_redo`, `crash_recovery` (Module B), WAL files under `Module_A/artifacts/`. |

### 1.3 Crash recovery (REDO / UNDO)

- **Analysis:** `RecoveryManager.analyze()` classifies transactions as committed, rolled back, or crash-uncommitted from the WAL.
- **UNDO:** Crash-uncommitted changes are reversed in reverse-LSN order using before-images.
- **REDO:** Committed transactions are replayed forward so committed data survives a restart.

Phase-6 demo summaries:

```json
{
  "recovery_undo": {
    "recovery": {
      "status": "ok",
      "total_records": 2,
      "redo_transactions": [],
      "undo_transactions": [
        "T-8483c86d49fb"
      ],
      "rolled_back_transactions": [],
      "applied_redo": 0,
      "applied_undo": 1,
      "note": "REDO/UNDO replay applied."
    },
    "invariants": {
      "undo_applied": true,
      "uncommitted_row_removed": true
    }
  },
  "recovery_redo": {
    "recovery": {
      "status": "ok",
      "total_records": 3,
      "redo_transactions": [
        "T-4d9229ed410b"
      ],
      "undo_transactions": [],
      "rolled_back_transactions": [],
      "applied_redo": 1,
      "applied_undo": 0,
      "note": "REDO/UNDO replay applied."
    },
    "invariants": {
      "redo_applied": true,
      "committed_row_restored": true
    }
  }
}
```

### 1.4 Automated test suite (Module A)

- **Command:** `/opt/homebrew/opt/python@3.13/bin/python3.13 -m unittest tests/test_phase1_transactions.py tests/test_phase2_accept_offer.py tests/test_phase3_wal_recovery.py tests/test_phase4_recovery_replay.py tests/test_phase5_concurrency.py`
- **Exit code:** `0`
- **Passed:** `True`

Full console capture: [`Module_A/artifacts/unittest_output.txt`](Module_A/artifacts/unittest_output.txt).

---

## 2. Module B — Multi-user behaviour and stress testing

Aligned with specification **§4**: concurrent usage, race testing, failure simulation, and large request counts (custom Python driver; compatible with Locust-style *task functions* wrapping `EngineFacade`).

### 2.1 Experiments executed

| Experiment | Intent |
|-------------|--------|
| `concurrent_race_same_listing` | scenario=`accept_race` — **PASS** |
| `concurrent_load_separate_listings` | scenario=`accept_load` — **PASS** |
| `failure_injection_rollback` | scenario=`failure_injection` — **PASS** |
| `crash_recovery_durability` | scenario=`crash_recovery` — **PASS** |
| `stress_bulk_1000_ops` | scenario=`stress_bulk` — **PASS** |
| `stress_bulk_2500_ops` | scenario=`stress_bulk` — **PASS** |

### 2.2 Stress volume (spec §4 — large request counts)

- **`stress_bulk_1000_ops`:** 1000 operations (50 waves × 20 threads), ~3671.48 ops/s, wall ~272.37 ms, one winner per wave: `True`.
- **`stress_bulk_2500_ops`:** 2500 operations (125 waves × 20 threads), ~3789.85 ops/s, wall ~659.66 ms, one winner per wave: `True`.

### 2.3 Raw Module B batch (summary)

```json
{
  "all_experiments_passed": true,
  "experiment_count": 6
}
```

Per-experiment payloads (latency, invariants, operation counts) are in [`artifacts/module_b_results.json`](artifacts/module_b_results.json).

---

## 3. Report prompts (spec §6) — explicit answers

- **How correctness is ensured:** B+ Tree is the only store; all writes go through transactional APIs and WAL logging; invariants checked in tests and stress scenarios.
- **How failures are handled:** `ROLLBACK` + WAL `ROLLBACK` record; recovery UNDO for crash-uncommitted; failure injection scenarios confirm no partial multi-table state.
- **How multi-user conflicts are handled:** Global **serializable** mutex serializes transactions; race tests show exactly one successful accept per listing under contention.
- **Experiments performed:** Module A unit tests + phase-6 demos; Module B batch (`accept_race`, `accept_load`, `failure_injection`, `crash_recovery`, `stress_bulk` ×2).
- **Observations:** Throughput is limited by global serialization (correctness-first design); latencies and op/s are recorded in `module_b_results.json`.
- **Limitations:** In-memory tables with WAL-based recovery (no full page-level media recovery); single-node; no MVCC or fine-grained locking.

---

## 4. Evaluation criteria (spec §8) — checklist

- Correctness of **transaction** behaviour: **Yes**
- Proper handling of **failures**: **Yes**
- **Multi-user safety** and **isolation**: **Yes**
- **Consistency** between database and B+ Tree: **Yes**
- System **robustness** under load: **Yes**
- **Clarity** of explanation: **Yes**

---

## 5. Self-evaluation against the specification

Module A satisfies **§3**: multi-relation transactions with `BEGIN`/`COMMIT`/`ROLLBACK`, WAL, crash recovery, and ACID reasoning backed by automated tests and reproducible WAL snippets in `Module_A/artifacts/`. The B+ Tree remains the sole storage path; recovery replays row images without maintaining a second primary copy of user data.

Module B satisfies **§4**: concurrent threads, contention on the same listing, injected failures, and large batch sizes (1000+ and 2500+ engine-level operations) with JSON-recorded latencies and invariants. Isolation is **serializable** via a global mutex, which simplifies correctness proofs and matches the spec’s allowance for serialized execution.

Remaining gaps for a production system: no SQL interface, no distributed replication, and throughput is intentionally traded for strict serialization. For submission, convert this Markdown report into `group_name_report.pdf` and record the demo video per **§5**.

---

## 6. How to reproduce

From the `Assignment_3` directory (one command rebuilds everything):

```bash
python3 scripts/build_assignment3_evidence.py
```

Individual steps:

```bash
cd Module_A && python3 scripts/generate_phase6_artifacts.py
cd .. && python3 Module_B/run_experiments.py
python3 scripts/build_assignment3_evidence.py
```

### 7. Optional: Locust / JMeter

The assignment allows **your own scripts**; this project uses `EngineFacade` and `Module_A/scripts/stress_driver.py`. To use **Locust**, add a `locustfile.py` whose tasks call `EngineFacade` in-process. Standard HTTP load generators target a network API (e.g. the Go backend from Assignment 2), not this in-memory engine, unless you add a thin HTTP wrapper.
