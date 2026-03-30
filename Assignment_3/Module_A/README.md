# Module A: B+ Tree Implementation

## Campus Trading Application - CS432 Database Project

This module implements a B+ Tree data structure for efficient database indexing, along with performance benchmarking against a brute-force baseline.

## Project Structure

```text
Module_A/
├── database/
│   ├── __init__.py      # Package initialization
│   ├── node.py          # LeafNode & InternalNode classes
│   ├── bplustree.py     # B+ Tree implementation
│   ├── bruteforce.py    # Baseline comparison (BruteForceDB)
│   └── benchmark.py     # Performance testing utilities
├── visualizations/
│   ├── tree_outputs/    # Graphviz tree visualizations
│   └── benchmark_plots/ # Performance comparison graphs
├── report.ipynb         # Jupyter notebook report
├── requirements.txt     # Python dependencies
└── README.md            # This file
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

This Module A folder now includes Assignment 3 transaction and recovery work.

### Run All Tests (Phases 1-5)

```bash
python -m unittest tests/test_phase1_transactions.py tests/test_phase2_accept_offer.py tests/test_phase3_wal_recovery.py tests/test_phase4_recovery_replay.py tests/test_phase5_concurrency.py
```

### Generate Phase 6 Report Artifacts

```bash
python scripts/generate_phase6_artifacts.py
```

Generated files:

- `artifacts/phase6_summary.json`
- `artifacts/phase6_summary.md`
- `artifacts/unittest_output.txt`

## Authors

Team 8 - CS432 Databases

- Bhavik Patel
- Hitesh Kumar
- Jinil Patel
- Pranav Patil
- Sibtain

## License

This project is part of the CS432 Database course assignment.
