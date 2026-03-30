# Assignment 3 Module A - Full Implementation Explanation

This document explains what was implemented in Assignment 3 Module A.

It covers:

1. File-by-file purpose.
2. What each phase achieved.
3. What each test file validates.
4. What the generated log and JSON files mean.

## 1) High-Level Outcome

Assignment 3 Module A now has:

1. Transaction lifecycle support (`BEGIN`, `COMMIT`, `ROLLBACK`).
2. Multi-table atomic business transaction (`accept_offer_atomic`).
3. Concurrency control using lock ownership by transaction.
4. WAL logging with sequence numbers and durable commit flush.
5. Recovery analysis and replay (`REDO` and `UNDO`).
6. Automated tests for phases 1 through 5.
7. Phase 6 artifact generation for report and video evidence.

## 2) File-by-File Explanation

## 2.1) Core package export

### database/__init__.py

What it does:

1. Exposes all important classes under one package import.
2. Keeps old Module A exports and adds Assignment 3 exports.

Assignment 3 exports added:

1. `WriteAheadLog`
2. `LockManager`
3. `TransactionManager`
4. `TransactionState`
5. `RecoveryManager`

## 2.2) Transaction and recovery engine files

### database/wal.py

What it does:

1. Stores append-only WAL entries in JSONL format.
2. Adds `lsn` (log sequence number) and UTC timestamp `ts`.
3. Records transaction lifecycle and data-change events.

Supported record types:

1. `BEGIN`
2. `INSERT`
3. `UPDATE`
4. `DELETE`
5. `COMMIT`
6. `ROLLBACK`

Important durability behavior:

1. `log_commit(...)` can force durable flush (`fsync`) when `sync_on_commit=True`.

Why this matters:

1. Commit point is persisted strongly.
2. Recovery can reconstruct or rollback state from ordered WAL entries.

### database/lock_manager.py

What it does:

1. Provides exclusive locks by resource id.
2. Tracks lock ownership per transaction.
3. Supports lock release per resource and release-all on transaction end.

Resource id pattern used:

1. `db_name:table_name:key`

Why this matters:

1. Prevents conflicting updates to the same logical row during concurrent operations.
2. Supports isolation checks in threaded tests.

### database/transaction.py

What it does:

1. Defines transaction states: `ACTIVE`, `COMMITTED`, `ABORTED`.
2. Tracks per-transaction change history (before/after images).
3. Appends lifecycle and change records to WAL.

Key methods:

1. `begin()`
2. `record_change(...)`
3. `commit(...)`
4. `rollback(...)`

Why this matters:

1. Central transaction state machine.
2. Foundation for rollback and recovery replay.

### database/recovery.py

What it does:

1. Analyzes WAL into committed, uncommitted, and rolled-back transactions.
2. Applies replay through `recover_into(db_manager)`.

Replay model implemented:

1. REDO committed transactions in forward log order.
2. UNDO crash-uncommitted transactions in reverse log order.

Important correction implemented:

1. Rolled-back transactions are not treated as crash-uncommitted.

Why this matters:

1. Crash-before-commit rows are removed.
2. Crash-after-commit rows are restored.
3. Replay behavior is idempotent at row-image level.

### database/db_manager.py

What it does (Assignment 3 additions):

1. Wires WAL and TransactionManager into DatabaseManager constructor.
2. Adds transaction APIs:
   1. `begin_transaction()`
   2. `commit_transaction(...)`
   3. `rollback_transaction(...)`
   4. `get_transaction_state(...)`
3. Adds tx-aware CRUD wrappers:
   1. `tx_get(...)`
   2. `tx_insert(...)`
   3. `tx_update(...)`
   4. `tx_delete(...)`
4. Implements rollback undo via before-images (`_undo_change(...)`).
5. Implements multi-table atomic flow (`accept_offer_atomic(...)`).
6. Adds schema-safe record builders for `Transaction` and `Notification` rows.

`accept_offer_atomic(...)` flow:

1. Validate offer/listing/seller/buyer conditions.
2. Accept selected offer.
3. Decline competing submitted offers.
4. Mark listing `Sold`.
5. Insert accepted and optional declined transaction rows.
6. Insert winner/seller/loser notifications (optional).
7. Commit on success, rollback on failure.
8. Optional failure injection via `fail_after_step` for testing rollback behavior.

Why this matters:

1. Demonstrates true multi-table atomicity.
2. Mirrors real Module B business semantics.
3. Provides deterministic failure simulation for evidence.

## 2.3) Test files

### tests/test_phase1_transactions.py

Validates:

1. Commit persists insert.
2. Rollback removes inserted row.
3. Rollback restores pre-update before-image.

Property focus:

1. Atomicity basics and transaction lifecycle correctness.

### tests/test_phase2_accept_offer.py

Validates:

1. Successful `accept_offer_atomic` commits all side effects.
2. Failure-injection path rolls back all touched tables.

Property focus:

1. Multi-relation atomicity.
2. End-state consistency.

### tests/test_phase3_wal_recovery.py

Validates:

1. WAL order (`BEGIN -> change -> COMMIT`).
2. Monotonic and unique LSN progression.
3. Recovery analysis classification (committed vs rolled-back).

Property focus:

1. Durability metadata correctness.

### tests/test_phase4_recovery_replay.py

Validates:

1. Crash before commit -> UNDO removes uncommitted row.
2. Crash after commit + restart -> REDO restores committed row.

Property focus:

1. Recovery correctness under crash scenarios.

### tests/test_phase5_concurrency.py

Validates:

1. Competing accepts on same listing produce a single winner.
2. High-contention same-offer race allows only one successful commit.

Property focus:

1. Isolation and race-condition safety.

## 2.4) Automation and artifact files

### scripts/generate_phase6_artifacts.py

What it does:

1. Runs all tests (phase 1 to phase 5).
2. Runs deterministic scenarios:
   1. Atomic success.
   2. Atomic failure rollback.
   3. Recovery UNDO.
   4. Recovery REDO.
3. Writes report-ready artifacts under `artifacts/`.

### artifacts/unittest_output.txt

What it means:

1. Raw output of full unittest execution.
2. Current run shows all tests passed.

### artifacts/phase6_summary.json

What it means:

1. Machine-readable result summary for tests and scenarios.
2. Includes invariants and replay statistics.

How to read key fields:

1. `tests.passed`: whether full test suite passed.
2. `demos.atomic_success.invariants`: expected success-state checks.
3. `demos.atomic_failure_rollback.invariants`: rollback guarantees.
4. `demos.recovery_undo.recovery`: undo replay statistics.
5. `demos.recovery_redo.recovery`: redo replay statistics.

### artifacts/phase6_summary.md

What it means:

1. Human-readable summary generated from the JSON data.
2. Suitable for direct use in the report body.

### artifacts/*.log (WAL traces)

Key files:

1. `atomic_success_wal.log`
2. `atomic_failure_wal.log`
3. `recovery_undo_wal.log`
4. `recovery_redo_wal.log`

How to read a WAL line:

1. `tx_id`: transaction identifier.
2. `type`: event type (`BEGIN`, `UPDATE`, etc.).
3. `table`: qualified table name (`campus.Offer`, etc.).
4. `key`: primary key of affected row.
5. `before` and `after`: row images for undo/redo.
6. `lsn`: global log order.
7. `ts`: event timestamp.

Interpretation examples:

1. `atomic_success_wal.log` ends with `COMMIT`, so all preceding changes are durable committed effects.
2. `atomic_failure_wal.log` ends with `ROLLBACK`, meaning all prior modifications of that transaction must be undone.

## 3) What We Achieved vs ACID

1. Atomicity:

- Multi-table flow commits completely or rolls back completely.
- Verified with failure injection.

1. Consistency:

- Business-rule checks enforce valid state transitions.
- Post-conditions validated in tests.

1. Isolation:

- Resource locking plus concurrency tests show single-winner behavior under contention.

1. Durability:

- WAL commit record supports durable flush.
- Recovery replays committed updates and removes uncommitted updates.

## 4) Important Notes and Current Limits

1. Data is in-memory during runtime; persistence is WAL-based replay.
2. Recovery replay assumes required tables/databases are present in the manager before replay.
3. Lock model is simple and sufficient for demonstrated cases, but can be extended to richer lock modes.

## 5) How to Reproduce

Run from `Assignment_3/Module_A`:

1. Full tests:

- `python -m unittest tests/test_phase1_transactions.py tests/test_phase2_accept_offer.py tests/test_phase3_wal_recovery.py tests/test_phase4_recovery_replay.py tests/test_phase5_concurrency.py`

1. Generate report artifacts:

- `python scripts/generate_phase6_artifacts.py`

Outputs:

1. `artifacts/phase6_summary.json`
2. `artifacts/phase6_summary.md`
3. `artifacts/unittest_output.txt`
4. WAL scenario logs inside `artifacts/`
