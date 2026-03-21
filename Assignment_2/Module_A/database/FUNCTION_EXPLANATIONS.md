# Module_A Database Folder: Function Reference

This document explains all implemented functions in [database/__init__.py](__init__.py), [database/node.py](node.py), [database/bplustree.py](bplustree.py), [database/bruteforce.py](bruteforce.py), [database/table.py](table.py), [database/db_manager.py](db_manager.py), and [database/benchmark.py](benchmark.py).

## 1) Functions Not Used Anywhere in Module_A Implementation

Method-level usage was checked across all Python files under Assignment_2/Module_A using name-reference search.

High-confidence zero-reference functions:

- BPlusTree.get_rightmost_leaf in [database/bplustree.py](bplustree.py#L718)
- BPlusTree.print_tree in [database/bplustree.py](bplustree.py#L839)
- BruteForceDB.get_sorted in [database/bruteforce.py](bruteforce.py#L133)
- BruteForceDB.__iter__ in [database/bruteforce.py](bruteforce.py#L159)
- DatabaseManager.delete_database in [database/db_manager.py](db_manager.py#L30)
- DatabaseManager.list_databases in [database/db_manager.py](db_manager.py#L38)
- DatabaseManager.delete_table in [database/db_manager.py](db_manager.py#L68)
- DatabaseManager.list_tables in [database/db_manager.py](db_manager.py#L79)
- PerformanceAnalyzer.generate_summary_table in [database/benchmark.py](benchmark.py#L391)
- InternalNode.insert_child in [database/node.py](node.py#L177)
- InternalNode.remove_key in [database/node.py](node.py#L190)
- InternalNode.remove_child in [database/node.py](node.py#L202)

Likely unused helper-path functions in B+ Tree logic (reachable only through currently unused recursive helpers):

- BPlusTree._insert_non_full in [database/bplustree.py](bplustree.py#L134)
- BPlusTree._split_child in [database/bplustree.py](bplustree.py#L158)
- BPlusTree._split_leaf_at_parent in [database/bplustree.py](bplustree.py#L204)
- BPlusTree._split_internal_at_parent in [database/bplustree.py](bplustree.py#L259)
- BPlusTree._delete in [database/bplustree.py](bplustree.py#L353)
- BPlusTree._fill_child in [database/bplustree.py](bplustree.py#L453)

Note:
- Dunder methods like __len__, __contains__, __repr__ can be used implicitly by Python, so they are not treated as dead code only based on direct name references.

## 2) File-by-File Function Explanations

## __init__.py

### run_quick_benchmark (re-export)
- Source is [database/benchmark.py](benchmark.py#L450).
- Exposed for convenient package-level import. Runs a default benchmark flow.

## node.py

### Node class

- __init__(order)
- Initializes base node metadata: tree order, key list, and parent pointer.

- is_leaf()
- Abstract method contract; subclasses must say whether they are leaves.

- is_full()
- Returns True when key count reaches maximum capacity (order - 1).

- is_underflow()
- Returns True when key count drops below minimum allowed keys.

- min_keys()
- Computes minimum keys allowed for non-root nodes: ceil(order/2)-1.

- max_keys()
- Computes maximum keys allowed: order-1.

- __repr__()
- Debug string describing node type and current keys.

### LeafNode class

- __init__(order)
- Initializes leaf storage for keys/values and doubly-linked leaf pointers (next, prev).

- is_leaf()
- Returns True for leaf nodes.

- insert_at(index, key, value)
- Inserts key and value at aligned positions in sorted arrays.

- remove_at(index)
- Removes key/value at index and returns the removed pair.

- get_value(key)
- Returns value for exact key match, otherwise None.

- set_value(key, value)
- Updates value for an existing key and returns success status.

- __repr__()
- Debug string that prints key/value pairs in the leaf.

### InternalNode class

- __init__(order)
- Initializes internal node child pointer array.

- is_leaf()
- Returns False for internal nodes.

- insert_child(index, key, child)
- Inserts separator key and right child into an internal node at position.

- remove_key(index)
- Removes and returns separator key at index.

- remove_child(index)
- Removes and returns child pointer at index; clears its parent pointer.

- find_child_index(key)
- Binary-search style child routing index selection for a search key.

- get_child_for_key(key)
- Returns actual child pointer to descend into.

- __repr__()
- Debug string showing keys and number of children.

## bplustree.py

### Construction and Search

- __init__(order=4)
- Creates an empty B+ tree with one root leaf and validates order >= 3.

- search(key)
- Public point lookup. Finds target leaf, then fetches value in that leaf.

- _find_leaf(key)
- Traverses internal nodes from root to leaf using separator routing.

- _find_position(keys, key)
- Binary search insertion position in sorted key list.

### Insert Path

- insert(key, value)
- Public insert/upsert. Updates value on duplicate key, else inserts in leaf and splits on overflow.

- _insert_non_full(node, key, value)
- Recursive insertion helper for non-full nodes (legacy/alternate path).

- _split_child(parent, index)
- Chooses whether to split child as leaf or internal node.

- _split_leaf(leaf)
- Splits full leaf into two leaves, relinks leaf chain, promotes first key of new leaf.

- _split_leaf_at_parent(parent, index, leaf)
- Variant split when parent and child index are already known.

- _split_internal(node)
- Splits full internal node, promotes middle separator key, reassigns moved children.

- _split_internal_at_parent(parent, index, node)
- Variant split for internal node when parent/index are known.

- _insert_into_parent(left_child, key, right_child)
- Inserts promoted separator into parent, creating new root if needed.

### Delete Path and Rebalancing

- delete(key)
- Public delete. Removes key from leaf, handles underflow by borrowing or merging.

- _delete(node, key)
- Recursive delete helper (legacy/alternate path).

- _handle_leaf_underflow(leaf)
- Restores leaf occupancy by borrowing from siblings or merging leaves.

- _handle_internal_underflow(node)
- Restores internal-node occupancy similarly; can shrink height when root becomes empty.

- _fill_child(node, index)
- Child-fix helper used by recursive delete path.

- _borrow_from_prev(parent, index)
- Leaf rebalance: borrow largest key/value from left sibling.

- _borrow_from_next(parent, index)
- Leaf rebalance: borrow smallest key/value from right sibling.

- _borrow_from_prev_internal(parent, index)
- Internal rebalance from left sibling via parent separator rotation.

- _borrow_from_next_internal(parent, index)
- Internal rebalance from right sibling via parent separator rotation.

- _merge(parent, index)
- Merges two adjacent leaves and removes parent separator.

- _merge_internal(parent, index)
- Merges two adjacent internal nodes and pulls down parent separator key.

### Updates, Range, Utility

- update(key, new_value)
- Point update for existing key; returns False when key not found.

- range_query(start_key, end_key)
- Efficient ordered scan in [start_key, end_key] using leaf linked-list traversal.

- get_all()
- Returns all key/value pairs in sorted key order by walking leaf chain from leftmost leaf.

- get_height()
- Returns number of levels in the tree.

- get_leftmost_leaf()
- Returns first leaf in sorted order.

- get_rightmost_leaf()
- Returns last leaf in sorted order.

- __len__()
- Returns number of stored records.

- __contains__(key)
- Membership check using search.

- __repr__()
- Debug summary with order, size, and height.

### Visualization and Debug Printing

- visualize_tree(filename='bptree')
- Builds Graphviz Digraph of tree topology and leaf links.

- _add_nodes(dot, node)
- Recursively adds visual node labels/shapes.

- _add_edges(dot, node)
- Recursively adds parent-to-child edges.

- _add_leaf_links(dot)
- Adds dashed links between leaves to show linked-list chain.

- print_tree()
- Console print entry point for tree structure.

- _print_node(node, level)
- Recursive indented print of internal and leaf content.

## bruteforce.py

- __init__()
- Initializes list-backed key/value storage.

- insert(key, value=None)
- Upserts by linear scan; append if key not found.

- search(key)
- Linear lookup by key.

- delete(key)
- Linear find and remove.

- update(key, new_value)
- Linear find and replace value.

- range_query(start, end)
- Full scan, filtering keys within inclusive range.

- get_all()
- Returns shallow copy of internal list.

- get_sorted()
- Returns data sorted by key.

- clear()
- Removes all records.

- __len__()
- Number of entries.

- __contains__(key)
- Membership test via generator expression.

- __repr__()
- Debug summary string with size.

- __iter__()
- Iterator over stored (key, value) pairs.

## table.py (Detailed)

Purpose:
- Wraps B+ tree storage into table semantics with schema/type validation.
- Uses one configured field as primary search key.

Functions:

- __init__(name, schema, order=8, search_key=None)
- Validates schema and search key, stores metadata, creates BPlusTree index.
- If search_key is omitted, first schema field is used.

- validate_record(record)
- Enforces structural correctness:
- record must be dict
- no missing schema columns
- no unknown extra columns
- non-None values must match expected Python type
- Returns (is_valid, message).

- insert(record)
- Validates record and inserts deep-copied row under search-key value.
- Returns success tuple.

- get(record_id)
- Fetches record by key and returns deep copy so callers cannot mutate internal state accidentally.

- get_all()
- Fetches sorted rows from B+ tree and deep-copies all rows.

- update(record_id, new_record)
- Validates target existence and new record schema/type.
- If key changes: delete old key and reinsert under new key.
- If key same: in-place value update via B+ tree update.

- delete(record_id)
- Deletes one record by key and returns operation status message.

- range_query(start_value, end_value)
- Returns deep-copied rows whose key lies in inclusive range.

- __len__()
- Number of records in table.

- __repr__()
- Debug summary containing name, key column, schema columns, and row count.

## db_manager.py (Detailed)

Purpose:
- Manages multiple logical databases in-memory.
- Each database is a dict of table_name -> Table object.

Functions:

- __init__()
- Initializes top-level database registry.

- create_database(db_name)
- Creates an empty logical database if name is non-empty and unique.

- delete_database(db_name)
- Deletes entire logical database and all tables inside.

- list_databases()
- Returns all database names.

- create_table(db_name, table_name, schema, order=8, search_key=None)
- Creates a table in an existing database, with validation and Table constructor error handling.

- delete_table(db_name, table_name)
- Deletes a table from a given database.

- list_tables(db_name)
- Returns all table names inside target database.

- get_table(db_name, table_name)
- Returns direct table handle for performing CRUD operations.

## benchmark.py (Detailed)

Purpose:
- Automated experiment harness to compare B+ Tree vs BruteForceDB runtime.
- Supports insert/search/range/delete benchmarks across varying dataset sizes.
- Produces plots and summary stats when optional dependencies are available.

Functions:

- __init__(sizes=None, order=50)
- Sets benchmark dataset sizes, B+ tree order, and result containers.

- generate_random_keys(n, seed=42)
- Produces n unique random integer keys.

- generate_random_data(n, seed=42)
- Produces random (key, value_string) pairs.

- benchmark_insert(data)
- Measures total insertion time for both structures; returns timings and populated instances.

- benchmark_search(bptree, brute, search_keys)
- Measures point-search workload for both structures.

- benchmark_range_query(bptree, brute, ranges)
- Measures multiple range queries for both structures.

- benchmark_delete(data, delete_ratio=0.5)
- Rebuilds fresh structures, then measures deletion workload over sampled keys.

- run_all_benchmarks(verbose=True)
- Full benchmark driver over all configured sizes:
- generates data
- runs insert/search/range/delete experiments
- stores per-size timings in self.results
- optional tqdm progress and console logs

- plot_results(save_path='visualizations/benchmark_plots/', show=True)
- Generates combined and per-operation plots with matplotlib and saves image files.
- Also calls speedup plotting helper.

- _plot_speedup(save_path, show)
- Plots speedup factor for each operation: brute_time / bptree_time.

- generate_summary_table()
- Computes mean/std timing and speedups across sizes.
- Returns pandas DataFrame if available, else list-of-dicts summary.

- print_summary()
- Prints formatted average timing and speedup table in console.

- run_quick_benchmark(sizes=None)
- Convenience runner with default sizes; executes full benchmark and summary print.

## Quick Presentation Notes

For your viva/report explanation, this is a good flow:

1. node.py defines low-level storage contracts.
2. bplustree.py implements indexed operations and balancing.
3. table.py adds schema-aware row semantics on top of B+ tree.
4. db_manager.py adds multi-database/table orchestration.
5. bruteforce.py is the baseline model.
6. benchmark.py demonstrates performance difference empirically.
