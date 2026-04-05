# Module A: ACID Transactions, WAL, and Recovery

## Campus Trading Application - CS432 Database Project

This module contains the Assignment 3 Module A engine built on top of the B+ Tree work from Assignment 2. It focuses on:

- ACID transaction lifecycle (`BEGIN`/`COMMIT`/`ROLLBACK`)
- Write-Ahead Logging (WAL) with append-only JSONL records
- Crash recovery using REDO/UNDO replay
- Serializable isolation via a global transaction lock
- Concurrent stress scenarios used by Module B experiments

## Current Project Structure

```text
Module_A/
|- acid_properties_demo.ipynb      # Main notebook demo for ACID + WAL + recovery
|- MODULE_A_REPORT.md              # Detailed technical report
|- README.md
|- requirements.txt
|- artifacts/
|  |- atomic_failure_wal.log
|  |- atomic_success_wal.log
|  |- recovery_redo_wal.log
|  |- recovery_undo_wal.log
|  \- notebook_demo/
|     |- wal_demo.log
|     \- wal_module_a_51_demo.log
|- database/
|  |- __init__.py
|  |- bplustree.py
|  |- node.py
|  |- table.py
|  |- table_api.py
|  |- table_display.py
|  |- db_manager.py                # Schema-neutral DB manager + tx APIs
|  |- transaction.py               # Transaction manager and change tracking
|  |- wal.py                       # WAL append/read/fsync behavior
|  |- recovery.py                  # REDO/UNDO crash recovery
|  |- campus_schema.py             # Campus table schemas + deterministic seed profile
|  \- campus_workflow.py           # accept_offer_atomic multi-table workflow
|- scripts/
|  |- stress_engine.py             # StressEngine + metrics/invariant helpers
|  \- stress_driver.py             # CLI scenarios (used by Module B)
\- tests/                          # Currently placeholder/empty in this snapshot
```

## Setup

### 1. Install dependencies

```bash
cd Assignment_3/Module_A
python -m pip install -r requirements.txt
```

### 2. Install Graphviz (recommended for notebook visual outputs)

Windows:

```bash
choco install graphviz
```

macOS:

```bash
brew install graphviz
```

Linux:

```bash
sudo apt-get install graphviz
```

## Quick Start

### Notebook demo

Run the main notebook from this folder:

```bash
jupyter notebook acid_properties_demo.ipynb
```

### Minimal engine usage

```python
from database.db_manager import DatabaseManager
from database.campus_schema import SeedProfile, install_campus_schema, seed_campus_tables
from database.campus_workflow import accept_offer_atomic

dbm = DatabaseManager()
profile = SeedProfile()

install_campus_schema(dbm, profile)
seed_campus_tables(dbm, profile)

ok, msg = accept_offer_atomic(
	dbm=dbm,
	db_name=profile.db_name,
	offer_id=profile.offer_base_id,
	acting_seller_id=profile.seller_id,
)

print(ok, msg)
```

## Stress Driver (CLI)

`scripts/stress_driver.py` runs concurrent scenarios and prints a JSON summary.

```bash
# Competing offers on same listing: exactly one should win
python scripts/stress_driver.py --scenario accept_race --threads 20 --iterations 5

# No contention load test: each thread works on separate listing/offer
python scripts/stress_driver.py --scenario accept_load --threads 10 --iterations 3

# Inject random failures and verify rollback cleanliness
python scripts/stress_driver.py --scenario failure_injection --threads 8 --iterations 5

# Commit, simulate crash, recover, verify durability
python scripts/stress_driver.py --scenario crash_recovery

# High-volume run: total operations = waves x threads
python scripts/stress_driver.py --scenario stress_bulk --waves 50 --threads 20

# Referential consistency checks across Offer/Listing/Transaction tables
python scripts/stress_driver.py --scenario consistency_check --threads 10

# Mixed concurrent success + injected failures
python scripts/stress_driver.py --scenario mixed_concurrent_failure --threads 10 --iterations 5
```

Exit code behavior:

- `0` -> all invariants passed
- `1` -> one or more invariant checks failed

## Core Behavior Summary

- **Atomicity**: multi-step workflows rollback completely on failure.
- **Consistency**: workflow and stress invariants check cross-table correctness.
- **Isolation**: `DatabaseManager` enforces serializable execution using a global lock.
- **Durability**: committed WAL records are fsynced and recoverable after restart.

## Authors

Team 8 - CS432 Databases

- Bhavik Patel
- Hitesh Kumar
- Jinil Patel
- Pranav Patil
- Sibtain

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
