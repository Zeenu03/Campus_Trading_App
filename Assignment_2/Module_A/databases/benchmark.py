"""
Performance Benchmarking Module
Campus Trading Application - CS432 Database Project

This module provides automated benchmarking capabilities to compare
the performance of B+ Tree against BruteForceDB across various operations.

Features:
- Automated testing across multiple dataset sizes
- Time measurement for insert, search, delete, and range queries
- Matplotlib visualization of results
- Summary statistics generation
"""

import time
import random
import os
from typing import List, Dict, Tuple, Optional, Any

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

from .bplustree import BPlusTree
from .bruteforce import BruteForceDB


class PerformanceAnalyzer:
    """
    Automated performance benchmarking for B+ Tree vs BruteForceDB.

    Measures execution time for various operations across different
    dataset sizes and generates visualizations of the results.
    """

    def __init__(self, sizes: Optional[List[int]] = None, order: int = 50):
        """
        Initialize the performance analyzer.

        Args:
            sizes: List of dataset sizes to test (default: 100 to 10000)
            order: Order parameter for B+ Tree (default: 50)
        """
        self.sizes = sizes or list(range(100, 10001, 500))
        self.order = order
        self.results: Dict[str, Dict[str, List[float]]] = {
            'insert': {'bptree': [], 'brute': []},
            'search': {'bptree': [], 'brute': []},
            'range_query': {'bptree': [], 'brute': []},
            'delete': {'bptree': [], 'brute': []}
        }
        self.memory_results: Dict[str, Dict[str, List[int]]] = {
            'insert': {'bptree': [], 'brute': []}
        }

    def generate_random_keys(self, n: int, seed: int = 42) -> List[int]:
        """
        Generate n random unique keys.

        Args:
            n: Number of keys to generate
            seed: Random seed for reproducibility

        Returns:
            List of unique random integers
        """
        random.seed(seed)
        return random.sample(range(n * 10), n)

    def generate_random_data(self, n: int, seed: int = 42) -> List[Tuple[int, str]]:
        """
        Generate n random key-value pairs.

        Args:
            n: Number of pairs to generate
            seed: Random seed for reproducibility

        Returns:
            List of (key, value) tuples
        """
        keys = self.generate_random_keys(n, seed)
        return [(k, f"value_{k}") for k in keys]

    def benchmark_insert(self, data: List[Tuple[int, str]]) -> Tuple[float, float, BPlusTree, BruteForceDB]:
        """
        Benchmark insertion operation for both data structures.

        Args:
            data: List of (key, value) pairs to insert

        Returns:
            Tuple of (bptree_time, brute_time, bptree_instance, brute_instance)
        """
        # B+ Tree insertion
        bptree = BPlusTree(order=self.order)
        start = time.perf_counter()
        for key, value in data:
            bptree.insert(key, value)
        bptree_time = time.perf_counter() - start

        # BruteForceDB insertion
        brute = BruteForceDB()
        start = time.perf_counter()
        for key, value in data:
            brute.insert(key, value)
        brute_time = time.perf_counter() - start

        return bptree_time, brute_time, bptree, brute

    def benchmark_search(self, bptree: BPlusTree, brute: BruteForceDB,
                        search_keys: List[int]) -> Tuple[float, float]:
        """
        Benchmark search operation for both data structures.

        Args:
            bptree: B+ Tree instance
            brute: BruteForceDB instance
            search_keys: List of keys to search for

        Returns:
            Tuple of (bptree_time, brute_time)
        """
        # B+ Tree search
        start = time.perf_counter()
        for key in search_keys:
            bptree.search(key)
        bptree_time = time.perf_counter() - start

        # BruteForceDB search
        start = time.perf_counter()
        for key in search_keys:
            brute.search(key)
        brute_time = time.perf_counter() - start

        return bptree_time, brute_time

    def benchmark_range_query(self, bptree: BPlusTree, brute: BruteForceDB,
                             ranges: List[Tuple[int, int]]) -> Tuple[float, float]:
        """
        Benchmark range query operation for both data structures.

        Args:
            bptree: B+ Tree instance
            brute: BruteForceDB instance
            ranges: List of (start, end) range tuples

        Returns:
            Tuple of (bptree_time, brute_time)
        """
        # B+ Tree range query
        start = time.perf_counter()
        for start_key, end_key in ranges:
            bptree.range_query(start_key, end_key)
        bptree_time = time.perf_counter() - start

        # BruteForceDB range query
        start = time.perf_counter()
        for start_key, end_key in ranges:
            brute.range_query(start_key, end_key)
        brute_time = time.perf_counter() - start

        return bptree_time, brute_time

    def benchmark_delete(self, data: List[Tuple[int, str]],
                        delete_ratio: float = 0.5) -> Tuple[float, float]:
        """
        Benchmark deletion operation for both data structures.

        Args:
            data: Original data that was inserted
            delete_ratio: Fraction of keys to delete (default: 0.5)

        Returns:
            Tuple of (bptree_time, brute_time)
        """
        keys = [k for k, v in data]
        delete_keys = random.sample(keys, int(len(keys) * delete_ratio))

        # Setup B+ Tree
        bptree = BPlusTree(order=self.order)
        for key, value in data:
            bptree.insert(key, value)

        # B+ Tree deletion
        start = time.perf_counter()
        for key in delete_keys:
            bptree.delete(key)
        bptree_time = time.perf_counter() - start

        # Setup BruteForceDB
        brute = BruteForceDB()
        for key, value in data:
            brute.insert(key, value)

        # BruteForceDB deletion
        start = time.perf_counter()
        for key in delete_keys:
            brute.delete(key)
        brute_time = time.perf_counter() - start

        return bptree_time, brute_time

    def run_all_benchmarks(self, verbose: bool = True) -> Dict[str, Dict[str, List[float]]]:
        """
        Run complete benchmark suite across all dataset sizes.

        Args:
            verbose: Whether to print progress information

        Returns:
            Dictionary containing all benchmark results
        """
        if verbose:
            print("=" * 60)
            print("Running Performance Benchmarks: B+ Tree vs BruteForceDB")
            print("=" * 60)
            print(f"B+ Tree Order: {self.order}")
            print(f"Dataset Sizes: {self.sizes[0]} to {self.sizes[-1]}")
            print("=" * 60)

        # Use tqdm if available, otherwise simple loop
        if TQDM_AVAILABLE and verbose:
            iterator = tqdm(self.sizes, desc="Testing sizes")
        else:
            iterator = self.sizes

        for size in iterator:
            data = self.generate_random_data(size)
            keys = [k for k, v in data]

            # Insert benchmark
            bp_ins, br_ins, bptree, brute = self.benchmark_insert(data)
            self.results['insert']['bptree'].append(bp_ins)
            self.results['insert']['brute'].append(br_ins)

            # Search benchmark (search 10% of keys)
            search_count = max(1, size // 10)
            search_keys = random.sample(keys, search_count)
            bp_src, br_src = self.benchmark_search(bptree, brute, search_keys)
            self.results['search']['bptree'].append(bp_src)
            self.results['search']['brute'].append(br_src)

            # Range query benchmark (10 random ranges)
            ranges = []
            for _ in range(10):
                a = random.randint(0, size * 5)
                b = random.randint(size * 5, size * 10)
                ranges.append((min(a, b), max(a, b)))
            bp_rng, br_rng = self.benchmark_range_query(bptree, brute, ranges)
            self.results['range_query']['bptree'].append(bp_rng)
            self.results['range_query']['brute'].append(br_rng)

            # Delete benchmark
            bp_del, br_del = self.benchmark_delete(data)
            self.results['delete']['bptree'].append(bp_del)
            self.results['delete']['brute'].append(br_del)

            if verbose and not TQDM_AVAILABLE:
                print(f"Size {size}: Insert({bp_ins:.4f}s vs {br_ins:.4f}s), "
                      f"Search({bp_src:.4f}s vs {br_src:.4f}s)")

        if verbose:
            print("\nBenchmark complete!")

        return self.results

    def plot_results(self, save_path: str = 'visualizations/benchmark_plots/',
                    show: bool = True) -> None:
        """
        Generate matplotlib plots for all operations.

        Args:
            save_path: Directory to save plot images
            show: Whether to display plots interactively
        """
        if not MATPLOTLIB_AVAILABLE:
            print("Matplotlib not available. Install with: pip install matplotlib")
            return

        os.makedirs(save_path, exist_ok=True)

        # Combined 2x2 plot
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        operations = ['insert', 'search', 'range_query', 'delete']
        titles = ['Insertion', 'Search', 'Range Query', 'Deletion']
        colors = {'bptree': '#2E86AB', 'brute': '#E94F37'}

        for ax, op, title in zip(axes.flat, operations, titles):
            ax.plot(self.sizes, self.results[op]['bptree'],
                   'o-', color=colors['bptree'], label='B+ Tree',
                   markersize=4, linewidth=2)
            ax.plot(self.sizes, self.results[op]['brute'],
                   's-', color=colors['brute'], label='BruteForceDB',
                   markersize=4, linewidth=2)
            ax.set_xlabel('Number of Keys', fontsize=11)
            ax.set_ylabel('Time (seconds)', fontsize=11)
            ax.set_title(f'{title} Performance', fontsize=12, fontweight='bold')
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3)
            ax.set_xlim(left=0)
            ax.set_ylim(bottom=0)

        plt.tight_layout()
        plt.savefig(f'{save_path}performance_comparison.png', dpi=300, bbox_inches='tight')
        if show:
            plt.show()
        plt.close()

        # Individual plots for each operation
        for op, title in zip(operations, titles):
            plt.figure(figsize=(10, 6))
            plt.plot(self.sizes, self.results[op]['bptree'],
                    'o-', color=colors['bptree'], label='B+ Tree',
                    markersize=5, linewidth=2)
            plt.plot(self.sizes, self.results[op]['brute'],
                    's-', color=colors['brute'], label='BruteForceDB',
                    markersize=5, linewidth=2)
            plt.xlabel('Number of Keys', fontsize=12)
            plt.ylabel('Time (seconds)', fontsize=12)
            plt.title(f'{title} Performance: B+ Tree vs BruteForceDB',
                     fontsize=14, fontweight='bold')
            plt.legend(fontsize=11)
            plt.grid(True, alpha=0.3)
            plt.xlim(left=0)
            plt.ylim(bottom=0)
            plt.savefig(f'{save_path}{op}_benchmark.png', dpi=300, bbox_inches='tight')
            if show:
                plt.show()
            plt.close()

        # Speedup plot
        self._plot_speedup(save_path, show)

        print(f"Plots saved to: {save_path}")

    def _plot_speedup(self, save_path: str, show: bool) -> None:
        """Generate speedup comparison plot."""
        if not NUMPY_AVAILABLE:
            return

        fig, ax = plt.subplots(figsize=(12, 6))

        operations = ['insert', 'search', 'range_query', 'delete']
        titles = ['Insert', 'Search', 'Range Query', 'Delete']
        colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']

        for op, title, color in zip(operations, titles, colors):
            speedups = []
            for bp, br in zip(self.results[op]['bptree'], self.results[op]['brute']):
                if bp > 0:
                    speedups.append(br / bp)
                else:
                    speedups.append(1)
            ax.plot(self.sizes, speedups, 'o-', label=title, color=color,
                   markersize=4, linewidth=2)

        ax.axhline(y=1, color='gray', linestyle='--', alpha=0.7, label='Equal Performance')
        ax.set_xlabel('Number of Keys', fontsize=12)
        ax.set_ylabel('Speedup Factor (BruteForce Time / B+ Tree Time)', fontsize=12)
        ax.set_title('B+ Tree Speedup Over BruteForceDB', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=0)

        plt.tight_layout()
        plt.savefig(f'{save_path}speedup_comparison.png', dpi=300, bbox_inches='tight')
        if show:
            plt.show()
        plt.close()

    def generate_summary_table(self) -> Any:
        """
        Generate summary statistics as a pandas DataFrame.

        Returns:
            pandas DataFrame with summary statistics, or dict if pandas not available
        """
        if not NUMPY_AVAILABLE:
            print("NumPy not available for statistics calculation")
            return None

        summary_data = []

        for op in ['insert', 'search', 'range_query', 'delete']:
            bp_times = np.array(self.results[op]['bptree'])
            br_times = np.array(self.results[op]['brute'])

            # Avoid division by zero
            avg_speedup = np.mean(br_times) / np.mean(bp_times) if np.mean(bp_times) > 0 else float('inf')

            summary_data.append({
                'Operation': op.replace('_', ' ').title(),
                'B+ Tree Avg (ms)': np.mean(bp_times) * 1000,
                'B+ Tree Std (ms)': np.std(bp_times) * 1000,
                'BruteForce Avg (ms)': np.mean(br_times) * 1000,
                'BruteForce Std (ms)': np.std(br_times) * 1000,
                'Avg Speedup': avg_speedup
            })

        if PANDAS_AVAILABLE:
            return pd.DataFrame(summary_data)
        else:
            return summary_data

    def print_summary(self) -> None:
        """Print a formatted summary of benchmark results."""
        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)

        if not NUMPY_AVAILABLE:
            print("NumPy not available for detailed statistics")
            return

        headers = ['Operation', 'B+ Tree (ms)', 'BruteForce (ms)', 'Speedup']
        print(f"{headers[0]:<15} {headers[1]:<15} {headers[2]:<15} {headers[3]:<10}")
        print("-" * 55)

        for op in ['insert', 'search', 'range_query', 'delete']:
            bp_avg = np.mean(self.results[op]['bptree']) * 1000
            br_avg = np.mean(self.results[op]['brute']) * 1000
            speedup = br_avg / bp_avg if bp_avg > 0 else float('inf')

            op_name = op.replace('_', ' ').title()
            print(f"{op_name:<15} {bp_avg:<15.4f} {br_avg:<15.4f} {speedup:<10.2f}x")

        print("=" * 70)


def run_quick_benchmark(sizes: Optional[List[int]] = None) -> PerformanceAnalyzer:
    """
    Run a quick benchmark with sensible defaults.

    Args:
        sizes: Optional list of dataset sizes

    Returns:
        PerformanceAnalyzer instance with completed results
    """
    if sizes is None:
        sizes = list(range(100, 5001, 200))

    analyzer = PerformanceAnalyzer(sizes=sizes)
    analyzer.run_all_benchmarks()
    analyzer.print_summary()

    return analyzer


if __name__ == "__main__":
    # Run benchmark when executed directly
    analyzer = run_quick_benchmark()
    analyzer.plot_results(show=True)
