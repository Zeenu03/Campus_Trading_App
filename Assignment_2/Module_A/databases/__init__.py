"""
Database Module for B+ Tree Implementation
Campus Trading Application - CS432 Database Project

This module provides a B+ Tree data structure implementation and
comparison with a brute-force baseline for performance analysis.

Classes:
    BPlusTree: Self-balancing B+ Tree implementation
    BruteForceDB: Simple list-based database for comparison
    PerformanceAnalyzer: Automated benchmarking tool

Usage:
    from database import BPlusTree, BruteForceDB, PerformanceAnalyzer

    # Create a B+ Tree
    tree = BPlusTree(order=4)
    tree.insert(1, "value1")
    tree.insert(2, "value2")

    # Search
    result = tree.search(1)  # Returns "value1"

    # Range query
    results = tree.range_query(1, 10)  # Returns all keys between 1 and 10

    # Run benchmarks
    analyzer = PerformanceAnalyzer()
    analyzer.run_all_benchmarks()
    analyzer.plot_results()
"""