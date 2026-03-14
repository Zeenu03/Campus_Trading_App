"""
B+ Tree Implementation
Campus Trading Application - CS432 Database Project

A self-balancing tree data structure that maintains sorted data and allows
efficient insertion, deletion, search, and range queries in O(log n) time.

Key Properties:
- All data is stored in leaf nodes
- Leaf nodes are connected in a doubly-linked list
- Internal nodes only store keys for navigation
- Tree is always balanced (all leaves at same level)
"""

from typing import Any, Optional, List, Tuple
from .node import Node, LeafNode, InternalNode

try:
    from graphviz import Digraph
    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False


class BPlusTree:
    """
    B+ Tree implementation supporting CRUD operations and range queries.

    Attributes:
        order: Maximum number of children per internal node
        root: Root node of the tree
    """

    def __init__(self, order: int = 4):
        """
        Initialize an empty B+ Tree.

        Args:
            order: Maximum children per internal node (default: 4)
                   Must be >= 3 for proper B+ Tree behavior
        """
        if order < 3:
            raise ValueError("Order must be at least 3")

        self.order = order
        self.root: Node = LeafNode(order)
        self._size = 0

    # ==================== SEARCH OPERATIONS ====================

    def search(self, key: Any) -> Optional[Any]:
        """
        Search for a key in the B+ Tree.

        Time Complexity: O(log_m n) where m = order, n = number of keys

        Args:
            key: The key to search for

        Returns:
            Associated value if found, None otherwise
        """
        leaf = self._find_leaf(key)
        return leaf.get_value(key)

    def _find_leaf(self, key: Any) -> LeafNode:
        """
        Traverse from root to the appropriate leaf node for a key.

        Args:
            key: The key to search for

        Returns:
            The leaf node that should contain this key
        """
        node = self.root
        while not node.is_leaf():
            node = node.get_child_for_key(key)
        return node

    def _find_position(self, keys: List[Any], key: Any) -> int:
        """
        Binary search to find insertion position in sorted key list.

        Args:
            keys: Sorted list of keys
            key: Key to find position for

        Returns:
            Index where key should be inserted
        """
        left, right = 0, len(keys)
        while left < right:
            mid = (left + right) // 2
            if keys[mid] < key:
                left = mid + 1
            else:
                right = mid
        return left
        
    # ==================== INSERT OPERATIONS ====================

    def insert(self, key: Any, value: Any) -> None:
        """
        Insert a key-value pair into the B+ Tree.

        If the key already exists, its value is updated.

        Time Complexity: O(log_m n)

        Args:
            key: The key to insert
            value: The associated value
        """
        leaf = self._find_leaf(key)

        # Check for duplicate key - update if exists
        for i, k in enumerate(leaf.keys):
            if k == key:
                leaf.values[i] = value
                return

        # Find insertion position
        pos = self._find_position(leaf.keys, key)

        # Insert key-value pair
        leaf.insert_at(pos, key, value)
        self._size += 1

        # Handle overflow if necessary
        if leaf.is_full():
            self._split_leaf(leaf)

    def _insert_non_full(self, node: Node, key: Any, value: Any) -> None:
        """
        Recursive helper to insert into a non-full node.

        Args:
            node: Current node
            key: Key to insert
            value: Associated value
        """
        if node.is_leaf():
            pos = self._find_position(node.keys, key)
            node.insert_at(pos, key, value)
        else:
            # Find appropriate child
            child_idx = node.find_child_index(key)
            child = node.children[child_idx]

            # Recursively insert
            self._insert_non_full(child, key, value)

            # Split child if it became full
            if child.is_full():
                self._split_child(node, child_idx)

    def _split_child(self, parent: InternalNode, index: int) -> None:
        """
        Split the child at given index.

        Args:
            parent: Parent node containing the child
            index: Index of the child to split
        """
        child = parent.children[index]

        if child.is_leaf():
            self._split_leaf_at_parent(parent, index, child)
        else:
            self._split_internal_at_parent(parent, index, child)

    def _split_leaf(self, leaf: LeafNode) -> None:
        """
        Split a full leaf node.

        Creates a new leaf node with the upper half of keys,
        copies the middle key to the parent, and maintains
        the leaf linked list.

        Args:
            leaf: The leaf node to split
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

    def _split_leaf_at_parent(self, parent: InternalNode, index: int, leaf: LeafNode) -> None:
        """Split a leaf node that has a known parent."""
        new_leaf = LeafNode(self.order)
        mid = len(leaf.keys) // 2

        # Move upper half to new leaf
        new_leaf.keys = leaf.keys[mid:]
        new_leaf.values = leaf.values[mid:]
        leaf.keys = leaf.keys[:mid]
        leaf.values = leaf.values[:mid]

        # Update linked list
        new_leaf.next = leaf.next
        new_leaf.prev = leaf
        if leaf.next:
            leaf.next.prev = new_leaf
        leaf.next = new_leaf

        # Insert into parent
        promote_key = new_leaf.keys[0]
        parent.keys.insert(index, promote_key)
        parent.children.insert(index + 1, new_leaf)
        new_leaf.parent = parent

    def _split_internal(self, node: InternalNode) -> None:
        """
        Split a full internal node.

        Creates a new internal node with the upper half,
        promotes the middle key to the parent (not copied),
        and redistributes children.

        Args:
            node: The internal node to split
        """
        new_node = InternalNode(self.order)
        mid = len(node.keys) // 2

        # The middle key is promoted, not copied
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

    def _split_internal_at_parent(self, parent: InternalNode, index: int, node: InternalNode) -> None:
        """Split an internal node that has a known parent."""
        new_node = InternalNode(self.order)
        mid = len(node.keys) // 2

        promote_key = node.keys[mid]

        # Move upper half to new node
        new_node.keys = node.keys[mid + 1:]
        new_node.children = node.children[mid + 1:]

        # Update children's parent pointers
        for child in new_node.children:
            child.parent = new_node

        # Keep lower half
        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]

        # Insert into parent
        parent.keys.insert(index, promote_key)
        parent.children.insert(index + 1, new_node)
        new_node.parent = parent

    def _insert_into_parent(self, left_child: Node, key: Any, right_child: Node) -> None:
        """
        Insert a key and right child pointer into the parent node.

        If there's no parent (left_child is root), create a new root.

        Args:
            left_child: Existing child (becomes left of new key)
            key: Key to insert in parent
            right_child: New child (becomes right of new key)
        """
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

            # Find position for new key
            pos = self._find_position(parent.keys, key)

            # Insert key and child
            parent.keys.insert(pos, key)
            parent.children.insert(pos + 1, right_child)
            right_child.parent = parent

            # Split parent if necessary
            if parent.is_full():
                self._split_internal(parent)
