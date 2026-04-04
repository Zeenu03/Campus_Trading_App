# Module A: B+ Tree Implementation

## Campus Trading Application - CS432 Database Project

This module implements a B+ Tree data structure for efficient database indexing, along with performance benchmarking against a brute-force baseline.

## Project Structure

```text
Module_A/
├── database/
│   ├── __init__.py          # Package initialization and exports
│   ├── node.py              # LeafNode & InternalNode classes
│   ├── bplustree.py         # B+ Tree implementation (primary storage)
│   ├── bruteforce.py        # Baseline comparison (BruteForceDB)
│   ├── benchmark.py         # Performance testing utilities
│   ├── table.py             # Table abstraction over B+ Tree
│   ├── db_manager.py        # DatabaseManager — transactions, global serial lock, run_transaction
│   ├── transaction.py       # TransactionManager, ChangeRecord, TransactionContext
│   ├── wal.py               # Write-ahead log (append-only JSONL)
│   ├── recovery.py          # RecoveryManager — REDO/UNDO replay
│   └── engine_facade.py     # EngineFacade + SeedProfile — Module B stress interface
├── tests/
│   ├── test_phase1_transactions.py   # Atomicity basics
│   ├── test_phase2_accept_offer.py   # Multi-table atomic flow
│   ├── test_phase3_wal_recovery.py   # WAL ordering and durability
│   ├── test_phase4_recovery_replay.py # Crash recovery correctness
│   └── test_phase5_concurrency.py   # Isolation and serialization
├── scripts/
│   ├── generate_phase6_artifacts.py # Report artifact generator
│   └── stress_driver.py             # Module B CLI stress runner
├── artifacts/
│   ├── phase6_summary.json
│   ├── phase6_summary.md
│   ├── unittest_output.txt
│   └── *.log                        # WAL scenario traces
├── data/
│   └── wal.log                      # Live WAL file
├── bplus_tree_wal_recovery_walkthrough.ipynb  # Notebook demo
├── requirements.txt
└── README.md
```

## Setup

### 1. Install Dependencies

```bash
cd Module_A
pip install -r requirements.txt
```

### 2. Install Graphviz (for tree visualization)

**Windows:**

```bash
choco install graphviz
# OR download from https://graphviz.org/download/
```

**macOS:**

```bash
brew install graphviz
```

**Linux:**

```bash
sudo apt-get install graphviz
```

## Quick Start

### Basic Usage

```python
from database import BPlusTree

# Create a B+ Tree with order 4
tree = BPlusTree(order=4)

# Insert key-value pairs
tree.insert(1, "Engineering Mechanics Textbook")
tree.insert(2, "Dell Laptop 15.6 inch")
tree.insert(3, "Wooden Study Desk")

# Search for a key
result = tree.search(2)  # Returns "Dell Laptop 15.6 inch"

# Range query
results = tree.range_query(1, 3)  # Returns all items with keys 1-3

# Delete a key
tree.delete(2)

# Visualize the tree
dot = tree.visualize_tree()
dot.render('my_tree', format='png')
```

### Run Benchmarks

```python
from database import PerformanceAnalyzer

# Create analyzer
analyzer = PerformanceAnalyzer(sizes=list(range(100, 5001, 200)))

# Run benchmarks
analyzer.run_all_benchmarks()

# Generate plots
analyzer.plot_results()

# Print summary
analyzer.print_summary()
```

### Run the Report Notebook

```bash
jupyter notebook report.ipynb
```

## Assignment 3 Workflow

This folder contains the full Assignment 3 Module A implementation: transaction lifecycle (`BEGIN`/`COMMIT`/`ROLLBACK`), WAL-based crash recovery, serializable isolation via a global mutex, and a stress-testing façade for Module B.

### Isolation level

Isolation is **serializable** — `DatabaseManager` holds a single global lock (`_serial_lock`) for the entire duration of every transaction, guaranteeing a strict serial execution order with no interleaving across threads.

### Run All Tests (Phases 1–5)

```bash
python3 -m unittest tests/test_phase1_transactions.py tests/test_phase2_accept_offer.py tests/test_phase3_wal_recovery.py tests/test_phase4_recovery_replay.py tests/test_phase5_concurrency.py -v
```

### Generate Phase 6 Report Artifacts

```bash
python3 scripts/generate_phase6_artifacts.py
```

Generated files:

- `artifacts/phase6_summary.json`
- `artifacts/phase6_summary.md`
- `artifacts/unittest_output.txt`

### Module B Stress Driver

`scripts/stress_driver.py` is a CLI entry point for Module B. It exercises the engine under concurrent load and prints a JSON result summary.

```bash
# N threads race to accept competing offers on the same listing
python3 scripts/stress_driver.py --scenario accept_race --threads 20 --iterations 5

# N threads each accept a unique offer (no contention) — throughput test
python3 scripts/stress_driver.py --scenario accept_load --threads 10 --iterations 3

# Random failure injection — verify all rollbacks are clean
python3 scripts/stress_driver.py --scenario failure_injection --threads 8 --iterations 5

# Commit one transaction, simulate crash, recover, verify durability
python3 scripts/stress_driver.py --scenario crash_recovery

# High volume: total operations = waves × threads (e.g. 1000 = 50 × 20)
python3 scripts/stress_driver.py --scenario stress_bulk --waves 50 --threads 20
```

Exit code is 0 when all invariants pass and 1 on any violation.

### Full Assignment 3 evidence (Module A + Module B + combined report)

From the parent `Assignment_3` directory:

```bash
python3 scripts/build_assignment3_evidence.py
```

Writes [`../ASSIGNMENT_3_COMBINED_REPORT.md`](../ASSIGNMENT_3_COMBINED_REPORT.md) and [`../artifacts/module_b_results.json`](../artifacts/module_b_results.json).

### Using EngineFacade directly from Module B

```python
from database.engine_facade import EngineFacade, SeedProfile

engine = EngineFacade()
engine.bootstrap()                             # create schema + seed rows

ok, msg = engine.accept_offer(offer_id=2000, seller_id=10)
print(engine.metrics_snapshot())               # latency histogram, success rate
print(engine.table_row_counts())               # Offer/Listing/Transaction/Notification

recovery_summary = engine.recover_and_reopen() # crash + WAL replay simulation
```

## Authors

Team 8 - CS432 Databases

- Bhavik Patel
- Hitesh Kumar
- Jinil Patel
- Pranav Patil
- Sibtain

## License

This project is part of the CS432 Database course assignment.
