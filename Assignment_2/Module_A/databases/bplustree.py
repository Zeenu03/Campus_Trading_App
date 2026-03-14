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