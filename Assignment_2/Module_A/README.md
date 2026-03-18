# Module A: B+ Tree Implementation

## Campus Trading Application - CS432 Database Project

This module implements a B+ Tree data structure for efficient database indexing, along with performance benchmarking against a brute-force baseline.

## Project Structure

```
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

## Features

### B+ Tree Operations

| Operation | Time Complexity | Description |
|-----------|-----------------|-------------|
| `search(key)` | O(log n) | Find value by key |
| `insert(key, value)` | O(log n) | Insert/update key-value |
| `delete(key)` | O(log n) | Remove key |
| `range_query(start, end)` | O(log n + k) | Find all keys in range |
| `update(key, value)` | O(log n) | Update existing key |
| `get_all()` | O(n) | Get all key-value pairs |
| `visualize_tree()` | O(n) | Generate Graphviz diagram |

### Benchmarking

The `PerformanceAnalyzer` class automatically benchmarks:
- Insert operations
- Search operations
- Range queries
- Delete operations

Generates:
- Combined performance comparison plot
- Individual operation plots
- Speedup comparison chart
- Summary statistics table

## B+ Tree Properties

- **Order**: Configurable (default: 4)
- **Balance**: All leaves at same level
- **Leaf Links**: Doubly-linked list for range queries
- **Data Storage**: All data in leaf nodes

## Authors

Team 8 - CS432 Databases
- Bhavik Patel
- Hitesh Kumar
- Jinil Patel
- Pranav Patil
- Sibtain

## License

This project is part of the CS432 Database course assignment.
