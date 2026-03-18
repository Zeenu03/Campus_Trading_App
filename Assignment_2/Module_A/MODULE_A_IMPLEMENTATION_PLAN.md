# Module A: B+ Tree Implementation Plan

## Campus Trading Application - Assignment 2

**Team 8** | CS 432 Databases | March 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [Project Structure](#2-project-structure)
3. [B+ Tree Implementation](#3-b-tree-implementation)
4. [BruteForceDB Baseline](#4-bruteforcedb-baseline)
5. [Performance Benchmarking](#5-performance-benchmarking)
6. [Visualization Strategy](#6-visualization-strategy)
7. [Report Structure](#7-report-structure)
8. [Implementation Timeline](#8-implementation-timeline)

---

## 1. Overview

### 1.1 Problem Statement

Implement a B+ Tree-based database index structure and compare its performance against a brute-force linear search approach. This demonstrates understanding of:
- B+ Tree data structure properties
- Index-based query optimization
- Performance analysis and benchmarking

### 1.2 Deliverables

| Deliverable | Description |
|-------------|-------------|
| `bplustree.py` | Complete B+ Tree implementation |
| `bruteforce.py` | Baseline comparison class |
| `benchmark.py` | Performance testing module |
| `visualizer.py` | Graphviz tree visualization |
| `report.ipynb` | Jupyter notebook with analysis |
| Video (3-5 min) | Screen recording with audio |

### 1.3 Evaluation Criteria

| Criteria | Marks |
|----------|-------|
| B+ Tree Implementation (insert, delete, search, range queries) | 20 |
| Automated benchmarking and performance analysis | 10 |
| Visualization using Graphviz + Report + Video | 10 |
| **Total** | **40** |

---

## 2. Project Structure

```
Module_A/
├── database/
│   ├── __init__.py
│   ├── bplustree.py          # B+ Tree implementation
│   ├── node.py               # Node classes (LeafNode, InternalNode)
│   ├── bruteforce.py         # BruteForceDB baseline
│   └── benchmark.py          # Performance testing utilities
├── visualizations/
│   ├── tree_outputs/         # Generated Graphviz images
│   └── benchmark_plots/      # Matplotlib performance graphs
├── report.ipynb              # Main Jupyter notebook report
├── requirements.txt          # Python dependencies
└── README.md                 # Setup instructions
```

### 2.1 Dependencies (requirements.txt)

```
graphviz>=0.20
matplotlib>=3.7.0
numpy>=1.24.0
jupyter>=1.0.0
pandas>=2.0.0
tqdm>=4.65.0
memory-profiler>=0.61.0
```

---

## 3. B+ Tree Implementation

### 3.1 Core Properties

| Property | Value | Rationale |
|----------|-------|-----------|
| Order (m) | Configurable (default: 4) | Allows testing different branching factors |
| Min keys (leaf) | ⌈m/2⌉ | Maintains balance |
| Max keys (leaf) | m - 1 | Triggers split when exceeded |
| Leaf linkage | Doubly-linked list | Efficient range queries |

### 3.2 Node Classes

```python
# node.py

class Node:
    """Base class for B+ Tree nodes."""
    def __init__(self, order):
        self.order = order
        self.keys = []
        self.parent = None

    def is_leaf(self):
        raise NotImplementedError

    def is_full(self):
        return len(self.keys) >= self.order - 1

    def is_underflow(self):
        return len(self.keys) < (self.order + 1) // 2 - 1


class LeafNode(Node):
    """Leaf node storing actual key-value pairs."""
    def __init__(self, order):
        super().__init__(order)
        self.values = []      # Corresponding values for keys
        self.next = None      # Pointer to next leaf (right sibling)
        self.prev = None      # Pointer to previous leaf (left sibling)

    def is_leaf(self):
        return True


class InternalNode(Node):
    """Internal node storing keys and child pointers."""
    def __init__(self, order):
        super().__init__(order)
        self.children = []    # Child node pointers

    def is_leaf(self):
        return False
```

### 3.3 B+ Tree Class Structure

```python
# bplustree.py

from .node import LeafNode, InternalNode

class BPlusTree:
    def __init__(self, order=4):
        """
        Initialize B+ Tree with given order.

        Args:
            order: Maximum number of children per internal node
        """
        self.order = order
        self.root = LeafNode(order)  # Start with empty leaf as root

    # ==================== SEARCH OPERATIONS ====================

    def search(self, key):
        """
        Search for a key in the B+ Tree.

        Time Complexity: O(log_m n) where m = order, n = number of keys

        Returns:
            Value if found, None otherwise
        """
        leaf = self._find_leaf(key)
        for i, k in enumerate(leaf.keys):
            if k == key:
                return leaf.values[i]
        return None

    def _find_leaf(self, key):
        """Traverse from root to appropriate leaf node."""
        node = self.root
        while not node.is_leaf():
            # Binary search for correct child
            i = self._find_position(node.keys, key)
            node = node.children[i]
        return node

    def _find_position(self, keys, key):
        """Binary search for position in sorted key list."""
        left, right = 0, len(keys)
        while left < right:
            mid = (left + right) // 2
            if keys[mid] <= key:
                left = mid + 1
            else:
                right = mid
        return left

    # ==================== INSERT OPERATIONS ====================

    def insert(self, key, value):
        """
        Insert key-value pair into B+ Tree.

        Time Complexity: O(log_m n)

        Steps:
        1. Find appropriate leaf node
        2. Insert key-value in sorted order
        3. If overflow, split node and propagate up
        """
        leaf = self._find_leaf(key)

        # Check for duplicate key (update if exists)
        for i, k in enumerate(leaf.keys):
            if k == key:
                leaf.values[i] = value  # Update existing
                return

        # Insert in sorted position
        pos = self._find_position(leaf.keys, key)
        leaf.keys.insert(pos, key)
        leaf.values.insert(pos, value)

        # Handle overflow
        if leaf.is_full():
            self._split_leaf(leaf)

    def _split_leaf(self, leaf):
        """
        Split a full leaf node.

        - Create new leaf with upper half of keys
        - Copy middle key up to parent
        - Maintain leaf linked list
        """
        new_leaf = LeafNode(self.order)
        mid = len(leaf.keys) // 2

        # Move upper half to new leaf
        new_leaf.keys = leaf.keys[mid:]
        new_leaf.values = leaf.values[mid:]
        leaf.keys = leaf.keys[:mid]
        leaf.values = leaf.values[:mid]

        # Update linked list pointers
        new_leaf.next = leaf.next
        new_leaf.prev = leaf
        if leaf.next:
            leaf.next.prev = new_leaf
        leaf.next = new_leaf

        # Promote first key of new leaf to parent
        promote_key = new_leaf.keys[0]
        self._insert_into_parent(leaf, promote_key, new_leaf)

    def _split_internal(self, node):
        """
        Split a full internal node.

        - Create new internal node with upper half
        - Promote middle key to parent (not copied)
        - Redistribute children
        """
        new_node = InternalNode(self.order)
        mid = len(node.keys) // 2

        promote_key = node.keys[mid]

        # Move upper half to new node
        new_node.keys = node.keys[mid + 1:]
        new_node.children = node.children[mid + 1:]

        # Update children's parent pointers
        for child in new_node.children:
            child.parent = new_node

        # Keep lower half in original node
        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]

        self._insert_into_parent(node, promote_key, new_node)

    def _insert_into_parent(self, left_child, key, right_child):
        """Insert key and right child pointer into parent node."""
        if left_child.parent is None:
            # Create new root
            new_root = InternalNode(self.order)
            new_root.keys = [key]
            new_root.children = [left_child, right_child]
            left_child.parent = new_root
            right_child.parent = new_root
            self.root = new_root
        else:
            parent = left_child.parent
            pos = self._find_position(parent.keys, key)
            parent.keys.insert(pos, key)
            parent.children.insert(pos + 1, right_child)
            right_child.parent = parent

            if parent.is_full():
                self._split_internal(parent)

    # ==================== DELETE OPERATIONS ====================

    def delete(self, key):
        """
        Delete key from B+ Tree.

        Time Complexity: O(log_m n)

        Returns:
            True if deletion succeeded, False if key not found
        """
        leaf = self._find_leaf(key)

        # Find key in leaf
        try:
            idx = leaf.keys.index(key)
        except ValueError:
            return False  # Key not found

        # Remove key-value pair
        leaf.keys.pop(idx)
        leaf.values.pop(idx)

        # Handle underflow (except for root)
        if leaf != self.root and leaf.is_underflow():
            self._handle_underflow(leaf)

        # Handle empty root
        if not self.root.keys and not self.root.is_leaf():
            self.root = self.root.children[0]
            self.root.parent = None

        return True

    def _handle_underflow(self, node):
        """
        Handle underflow by borrowing from siblings or merging.

        Strategy:
        1. Try to borrow from left sibling
        2. Try to borrow from right sibling
        3. Merge with a sibling
        """
        parent = node.parent
        idx = parent.children.index(node)

        # Try borrowing from left sibling
        if idx > 0:
            left_sibling = parent.children[idx - 1]
            if len(left_sibling.keys) > (self.order + 1) // 2 - 1:
                self._borrow_from_left(node, left_sibling, parent, idx)
                return

        # Try borrowing from right sibling
        if idx < len(parent.children) - 1:
            right_sibling = parent.children[idx + 1]
            if len(right_sibling.keys) > (self.order + 1) // 2 - 1:
                self._borrow_from_right(node, right_sibling, parent, idx)
                return

        # Merge with sibling
        if idx > 0:
            self._merge_with_left(node, parent.children[idx - 1], parent, idx)
        else:
            self._merge_with_right(node, parent.children[idx + 1], parent, idx)

    def _borrow_from_left(self, node, left_sibling, parent, idx):
        """Borrow rightmost key from left sibling."""
        if node.is_leaf():
            # Move last key-value from left sibling
            node.keys.insert(0, left_sibling.keys.pop())
            node.values.insert(0, left_sibling.values.pop())
            parent.keys[idx - 1] = node.keys[0]
        else:
            # Move key from parent down, last key from sibling up
            node.keys.insert(0, parent.keys[idx - 1])
            parent.keys[idx - 1] = left_sibling.keys.pop()
            child = left_sibling.children.pop()
            node.children.insert(0, child)
            child.parent = node

    def _borrow_from_right(self, node, right_sibling, parent, idx):
        """Borrow leftmost key from right sibling."""
        if node.is_leaf():
            # Move first key-value from right sibling
            node.keys.append(right_sibling.keys.pop(0))
            node.values.append(right_sibling.values.pop(0))
            parent.keys[idx] = right_sibling.keys[0]
        else:
            # Move key from parent down, first key from sibling up
            node.keys.append(parent.keys[idx])
            parent.keys[idx] = right_sibling.keys.pop(0)
            child = right_sibling.children.pop(0)
            node.children.append(child)
            child.parent = node

    def _merge_with_left(self, node, left_sibling, parent, idx):
        """Merge node into left sibling."""
        if node.is_leaf():
            left_sibling.keys.extend(node.keys)
            left_sibling.values.extend(node.values)
            left_sibling.next = node.next
            if node.next:
                node.next.prev = left_sibling
        else:
            left_sibling.keys.append(parent.keys[idx - 1])
            left_sibling.keys.extend(node.keys)
            left_sibling.children.extend(node.children)
            for child in node.children:
                child.parent = left_sibling

        # Remove from parent
        parent.keys.pop(idx - 1)
        parent.children.pop(idx)

        if parent != self.root and parent.is_underflow():
            self._handle_underflow(parent)

    def _merge_with_right(self, node, right_sibling, parent, idx):
        """Merge right sibling into node."""
        if node.is_leaf():
            node.keys.extend(right_sibling.keys)
            node.values.extend(right_sibling.values)
            node.next = right_sibling.next
            if right_sibling.next:
                right_sibling.next.prev = node
        else:
            node.keys.append(parent.keys[idx])
            node.keys.extend(right_sibling.keys)
            node.children.extend(right_sibling.children)
            for child in right_sibling.children:
                child.parent = node

        # Remove from parent
        parent.keys.pop(idx)
        parent.children.pop(idx + 1)

        if parent != self.root and parent.is_underflow():
            self._handle_underflow(parent)

    # ==================== UPDATE OPERATION ====================

    def update(self, key, new_value):
        """
        Update value for existing key.

        Returns:
            True if updated, False if key not found
        """
        leaf = self._find_leaf(key)
        for i, k in enumerate(leaf.keys):
            if k == key:
                leaf.values[i] = new_value
                return True
        return False

    # ==================== RANGE QUERY ====================

    def range_query(self, start_key, end_key):
        """
        Return all key-value pairs where start_key <= key <= end_key.

        Time Complexity: O(log_m n + k) where k = number of results

        Leverages leaf linked list for efficient scanning.
        """
        results = []

        # Find starting leaf
        leaf = self._find_leaf(start_key)

        # Scan through leaves using next pointers
        while leaf:
            for i, key in enumerate(leaf.keys):
                if key > end_key:
                    return results
                if key >= start_key:
                    results.append((key, leaf.values[i]))
            leaf = leaf.next

        return results

    # ==================== UTILITY METHODS ====================

    def get_all(self):
        """Return all key-value pairs via in-order traversal."""
        results = []
        # Find leftmost leaf
        node = self.root
        while not node.is_leaf():
            node = node.children[0]

        # Traverse linked list
        while node:
            for i, key in enumerate(node.keys):
                results.append((key, node.values[i]))
            node = node.next

        return results

    def __len__(self):
        """Return total number of key-value pairs."""
        return len(self.get_all())

    def __contains__(self, key):
        """Check if key exists in tree."""
        return self.search(key) is not None
```

### 3.4 Key Operations Summary

| Operation | Time Complexity | Description |
|-----------|-----------------|-------------|
| `search(key)` | O(log n) | Find value by key |
| `insert(key, value)` | O(log n) | Insert/update key-value |
| `delete(key)` | O(log n) | Remove key |
| `range_query(start, end)` | O(log n + k) | Find all keys in range |
| `update(key, value)` | O(log n) | Update existing key |
| `get_all()` | O(n) | Return all entries |

---

## 4. BruteForceDB Baseline

```python
# bruteforce.py

class BruteForceDB:
    """
    Simple list-based database for baseline comparison.
    All operations are O(n) due to linear search.
    """

    def __init__(self):
        self.data = []  # List of (key, value) tuples

    def insert(self, key, value=None):
        """O(n) - Check for duplicates, then append."""
        for i, (k, v) in enumerate(self.data):
            if k == key:
                self.data[i] = (key, value)
                return
        self.data.append((key, value))

    def search(self, key):
        """O(n) - Linear scan through list."""
        for k, v in self.data:
            if k == key:
                return v
        return None

    def delete(self, key):
        """O(n) - Find and remove."""
        for i, (k, v) in enumerate(self.data):
            if k == key:
                self.data.pop(i)
                return True
        return False

    def range_query(self, start, end):
        """O(n) - Scan entire list and filter."""
        return [(k, v) for k, v in self.data if start <= k <= end]

    def update(self, key, new_value):
        """O(n) - Find and update."""
        for i, (k, v) in enumerate(self.data):
            if k == key:
                self.data[i] = (key, new_value)
                return True
        return False

    def get_all(self):
        """O(n) - Return all entries."""
        return self.data.copy()

    def __len__(self):
        return len(self.data)

    def __contains__(self, key):
        return any(k == key for k, _ in self.data)
```

---

## 5. Performance Benchmarking

### 5.1 Benchmark Module

```python
# benchmark.py

import time
import random
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm
from memory_profiler import memory_usage

from .bplustree import BPlusTree
from .bruteforce import BruteForceDB


class PerformanceAnalyzer:
    """Automated benchmarking for B+ Tree vs BruteForceDB."""

    def __init__(self, sizes=None):
        """
        Args:
            sizes: List of dataset sizes to test
        """
        self.sizes = sizes or list(range(100, 10001, 500))
        self.results = {
            'insert': {'bptree': [], 'brute': []},
            'search': {'bptree': [], 'brute': []},
            'range_query': {'bptree': [], 'brute': []},
            'delete': {'bptree': [], 'brute': []}
        }

    def generate_random_keys(self, n, seed=42):
        """Generate n random unique keys."""
        random.seed(seed)
        return random.sample(range(n * 10), n)

    def benchmark_insert(self, keys):
        """Benchmark insertion for both structures."""
        # B+ Tree
        bptree = BPlusTree(order=50)
        start = time.perf_counter()
        for key in keys:
            bptree.insert(key, f"value_{key}")
        bptree_time = time.perf_counter() - start

        # BruteForce
        brute = BruteForceDB()
        start = time.perf_counter()
        for key in keys:
            brute.insert(key, f"value_{key}")
        brute_time = time.perf_counter() - start

        return bptree_time, brute_time, bptree, brute

    def benchmark_search(self, bptree, brute, search_keys):
        """Benchmark search for both structures."""
        # B+ Tree
        start = time.perf_counter()
        for key in search_keys:
            bptree.search(key)
        bptree_time = time.perf_counter() - start

        # BruteForce
        start = time.perf_counter()
        for key in search_keys:
            brute.search(key)
        brute_time = time.perf_counter() - start

        return bptree_time, brute_time

    def benchmark_range_query(self, bptree, brute, ranges):
        """Benchmark range queries."""
        # B+ Tree
        start = time.perf_counter()
        for start_key, end_key in ranges:
            bptree.range_query(start_key, end_key)
        bptree_time = time.perf_counter() - start

        # BruteForce
        start = time.perf_counter()
        for start_key, end_key in ranges:
            brute.range_query(start_key, end_key)
        brute_time = time.perf_counter() - start

        return bptree_time, brute_time

    def benchmark_delete(self, keys):
        """Benchmark deletion."""
        # Setup both structures
        bptree = BPlusTree(order=50)
        brute = BruteForceDB()
        for key in keys:
            bptree.insert(key, f"value_{key}")
            brute.insert(key, f"value_{key}")

        delete_keys = random.sample(keys, len(keys) // 2)

        # B+ Tree
        start = time.perf_counter()
        for key in delete_keys:
            bptree.delete(key)
        bptree_time = time.perf_counter() - start

        # Recreate brute for fresh delete
        brute = BruteForceDB()
        for key in keys:
            brute.insert(key, f"value_{key}")

        # BruteForce
        start = time.perf_counter()
        for key in delete_keys:
            brute.delete(key)
        brute_time = time.perf_counter() - start

        return bptree_time, brute_time

    def run_all_benchmarks(self):
        """Run complete benchmark suite."""
        print("Running Performance Benchmarks...")
        print("=" * 50)

        for size in tqdm(self.sizes, desc="Testing sizes"):
            keys = self.generate_random_keys(size)

            # Insert benchmark
            bp_ins, br_ins, bptree, brute = self.benchmark_insert(keys)
            self.results['insert']['bptree'].append(bp_ins)
            self.results['insert']['brute'].append(br_ins)

            # Search benchmark (search 10% of keys)
            search_keys = random.sample(keys, max(1, size // 10))
            bp_src, br_src = self.benchmark_search(bptree, brute, search_keys)
            self.results['search']['bptree'].append(bp_src)
            self.results['search']['brute'].append(br_src)

            # Range query benchmark
            ranges = [(random.randint(0, size * 5),
                       random.randint(size * 5, size * 10))
                      for _ in range(10)]
            bp_rng, br_rng = self.benchmark_range_query(bptree, brute, ranges)
            self.results['range_query']['bptree'].append(bp_rng)
            self.results['range_query']['brute'].append(br_rng)

            # Delete benchmark
            bp_del, br_del = self.benchmark_delete(keys)
            self.results['delete']['bptree'].append(bp_del)
            self.results['delete']['brute'].append(br_del)

        return self.results

    def plot_results(self, save_path='visualizations/benchmark_plots/'):
        """Generate matplotlib plots for all operations."""
        import os
        os.makedirs(save_path, exist_ok=True)

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        operations = ['insert', 'search', 'range_query', 'delete']
        titles = ['Insertion', 'Search', 'Range Query', 'Deletion']

        for ax, op, title in zip(axes.flat, operations, titles):
            ax.plot(self.sizes, self.results[op]['bptree'],
                   'b-o', label='B+ Tree', markersize=3)
            ax.plot(self.sizes, self.results[op]['brute'],
                   'r-s', label='BruteForceDB', markersize=3)
            ax.set_xlabel('Number of Keys')
            ax.set_ylabel('Time (seconds)')
            ax.set_title(f'{title} Performance')
            ax.legend()
            ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(f'{save_path}performance_comparison.png', dpi=300)
        plt.show()

        # Individual plots
        for op, title in zip(operations, titles):
            plt.figure(figsize=(10, 6))
            plt.plot(self.sizes, self.results[op]['bptree'],
                    'b-o', label='B+ Tree', linewidth=2)
            plt.plot(self.sizes, self.results[op]['brute'],
                    'r-s', label='BruteForceDB', linewidth=2)
            plt.xlabel('Number of Keys', fontsize=12)
            plt.ylabel('Time (seconds)', fontsize=12)
            plt.title(f'{title} Performance: B+ Tree vs BruteForceDB', fontsize=14)
            plt.legend(fontsize=11)
            plt.grid(True, alpha=0.3)
            plt.savefig(f'{save_path}{op}_benchmark.png', dpi=300)
            plt.close()

    def generate_summary_table(self):
        """Generate summary statistics as DataFrame."""
        import pandas as pd

        summary = []
        for op in ['insert', 'search', 'range_query', 'delete']:
            bp_times = self.results[op]['bptree']
            br_times = self.results[op]['brute']

            summary.append({
                'Operation': op.replace('_', ' ').title(),
                'B+ Tree Avg (ms)': np.mean(bp_times) * 1000,
                'BruteForce Avg (ms)': np.mean(br_times) * 1000,
                'Speedup Factor': np.mean(br_times) / np.mean(bp_times) if np.mean(bp_times) > 0 else float('inf')
            })

        return pd.DataFrame(summary)
```

### 5.2 Expected Results Analysis

| Operation | B+ Tree | BruteForceDB | Why B+ Tree Wins |
|-----------|---------|--------------|------------------|
| Insert | O(log n) | O(n) | Tree traversal vs linear duplicate check |
| Search | O(log n) | O(n) | Binary search in nodes vs linear scan |
| Range Query | O(log n + k) | O(n) | Leaf linked list vs full scan + filter |
| Delete | O(log n) | O(n) | Tree traversal vs linear search |

---

## 6. Visualization Strategy

### 6.1 Graphviz Visualization

```python
# Add to bplustree.py

from graphviz import Digraph

class BPlusTree:
    # ... (previous methods)

    def visualize_tree(self, filename='bptree'):
        """
        Generate Graphviz visualization of B+ Tree.

        Returns:
            Digraph object (can be rendered to PNG/PDF)
        """
        dot = Digraph(comment='B+ Tree')
        dot.attr(rankdir='TB')  # Top to bottom layout
        dot.attr('node', shape='record')

        if self.root:
            self._add_nodes(dot, self.root, 0)
            self._add_leaf_links(dot)

        return dot

    def _add_nodes(self, dot, node, node_id):
        """Recursively add nodes to Graphviz diagram."""
        # Create node label
        if node.is_leaf():
            # Leaf: show keys and values
            label = '|'.join([f'<f{i}>{k}:{v}'
                             for i, (k, v) in enumerate(zip(node.keys, node.values))])
            dot.node(f'node{node_id}', label, color='green', style='filled', fillcolor='lightgreen')
        else:
            # Internal: show keys with child pointers
            parts = [f'<c{i}>' for i in range(len(node.children))]
            for i, key in enumerate(node.keys):
                parts.insert(2*i + 1, str(key))
            label = '|'.join(parts)
            dot.node(f'node{node_id}', label, color='blue', style='filled', fillcolor='lightblue')

        # Add edges to children
        if not node.is_leaf():
            current_id = node_id
            for i, child in enumerate(node.children):
                child_id = id(child)
                self._add_nodes(dot, child, child_id)
                dot.edge(f'node{node_id}:c{i}', f'node{child_id}')

        return node_id

    def _add_leaf_links(self, dot):
        """Add dashed lines showing leaf linked list."""
        # Find leftmost leaf
        node = self.root
        while not node.is_leaf():
            node = node.children[0]

        # Draw links between leaves
        dot.attr('edge', style='dashed', color='red')
        while node.next:
            dot.edge(f'node{id(node)}', f'node{id(node.next)}',
                    constraint='false')
            node = node.next
```

### 6.2 Visualization Output Examples

Generate visualizations showing:

1. **Empty tree** - Initial state
2. **After insertions** - Show nodes and structure
3. **After split** - Highlight how nodes split when full
4. **After deletions** - Show rebalancing/merging
5. **Leaf linkage** - Red dashed lines connecting leaves

---

## 7. Report Structure (report.ipynb)

### 7.1 Notebook Outline

```markdown
# B+ Tree Implementation Report
## Campus Trading Application - Module A

### 1. Introduction
- Problem statement: Need for efficient indexing in databases
- Solution overview: B+ Tree implementation
- Connection to Campus Trading (indexing ListingID, MemberID, etc.)

### 2. Implementation Details
- B+ Tree properties (order, balance, leaf linkage)
- Node structure (LeafNode, InternalNode)
- Core operations with code snippets
- Design decisions and trade-offs

### 3. Demonstration
- Insert operations with visualizations
- Search operations
- Range queries (essential for Campus Trading queries like "listings between $10-$50")
- Delete operations with rebalancing

### 4. Performance Analysis
- Benchmarking methodology
- Results tables
- Matplotlib graphs
- Analysis of time complexity differences

### 5. Visualizations
- Graphviz tree outputs at different stages
- Annotated screenshots

### 6. Campus Trading Application Context
- How B+ Tree would index Listing table
- Example queries that benefit from B+ Tree indexing

### 7. Conclusion
- Summary of findings
- Challenges faced
- Potential improvements (caching, bulk loading, etc.)

### 8. Video Link
[Link to demonstration video]
```

### 7.2 Sample Code Cells

```python
# Cell 1: Setup
import sys
sys.path.append('..')
from database.bplustree import BPlusTree
from database.bruteforce import BruteForceDB
from database.benchmark import PerformanceAnalyzer

# Cell 2: Basic Operations Demo
tree = BPlusTree(order=4)

# Insert sample Campus Trading data
listings = [
    (1, "Engineering Mechanics Textbook"),
    (2, "Dell Laptop 15.6 inch"),
    (3, "Wooden Study Desk"),
    (4, "TI-84 Calculator"),
    (5, "Physics Textbook"),
]

for listing_id, title in listings:
    tree.insert(listing_id, title)
    print(f"Inserted: {listing_id} -> {title}")

# Cell 3: Visualize
dot = tree.visualize_tree()
dot.render('visualizations/tree_outputs/after_insert', format='png')
display(dot)

# Cell 4: Search
result = tree.search(3)
print(f"Search for ListingID=3: {result}")

# Cell 5: Range Query (all listings with ID 2-4)
results = tree.range_query(2, 4)
print("Range Query [2, 4]:", results)

# Cell 6: Run Benchmarks
analyzer = PerformanceAnalyzer(sizes=list(range(100, 5001, 200)))
results = analyzer.run_all_benchmarks()
analyzer.plot_results()

# Cell 7: Summary Table
summary = analyzer.generate_summary_table()
display(summary)
```

---

## 8. Implementation Timeline

| Phase | Tasks | Priority |
|-------|-------|----------|
| **Phase 1** | Node classes + basic insert/search | High |
| **Phase 2** | Split operations + tree balancing | High |
| **Phase 3** | Delete operations + underflow handling | High |
| **Phase 4** | Range query + get_all | Medium |
| **Phase 5** | Graphviz visualization | Medium |
| **Phase 6** | Benchmarking module | Medium |
| **Phase 7** | Jupyter notebook report | Medium |
| **Phase 8** | Video recording | Low |

---

## 9. Video Script Outline (3-5 minutes)

```
[0:00 - 0:30] Introduction
- "Welcome to our B+ Tree implementation demo"
- Brief overview of what B+ Tree is

[0:30 - 1:30] Code Walkthrough
- Show node.py structure
- Show bplustree.py key methods
- Explain order parameter

[1:30 - 2:30] Live Demo
- Run insertions in Jupyter
- Show Graphviz output
- Demonstrate search and range query

[2:30 - 4:00] Performance Analysis
- Show benchmark running
- Display Matplotlib graphs
- Explain why B+ Tree outperforms BruteForceDB
  - "As you can see, for range queries with 10,000 keys,
     B+ Tree takes X ms while BruteForceDB takes Y ms"

[4:00 - 4:30] Conclusion
- Summary of findings
- Connection to Campus Trading indexing
```

---

## 10. Quick Reference: B+ Tree vs BruteForceDB

| Aspect | B+ Tree | BruteForceDB |
|--------|---------|--------------|
| Structure | Balanced tree with leaf links | Unsorted list |
| Insert | O(log n) | O(n) for duplicate check |
| Search | O(log n) | O(n) |
| Range Query | O(log n + k) | O(n) |
| Delete | O(log n) | O(n) |
| Memory | Higher (node overhead) | Lower (just list) |
| Best Use Case | Large datasets, frequent queries | Small datasets, rare queries |

---

**Document prepared for Team 8 - CS432 Databases**
