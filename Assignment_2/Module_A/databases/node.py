"""
Node Classes for B+ Tree Implementation
Campus Trading Application - CS432 Database Project

This module defines the node structures used in the B+ Tree:
- Node: Abstract base class
- LeafNode: Stores actual key-value pairs with linked list pointers
- InternalNode: Stores keys and child pointers for navigation
"""

from typing import Any, Optional, List

class Node:
    """
    Abstract base class for B+ Tree nodes.

    Attributes:
        order: Maximum number of children for internal nodes (max keys = order - 1)
        keys: List of keys stored in this node
        parent: Reference to parent node (None for root)
    """

    def __init__(self, order: int):
        """
        Initialize a node with given order.

        Args:
            order: The order of the B+ Tree (max children per internal node)
        """
        self.order = order
        self.keys: List[Any] = []
        self.parent: Optional['Node'] = None

    def is_leaf(self) -> bool:
        """Check if this node is a leaf node."""
        raise NotImplementedError("Subclasses must implement is_leaf()")

    def is_full(self) -> bool:
        """Check if the node has reached maximum capacity."""
        return len(self.keys) >= self.order - 1

    def is_underflow(self) -> bool:
        """Check if the node has fewer than minimum required keys."""
        min_keys = (self.order + 1) // 2 - 1
        return len(self.keys) < min_keys

    def min_keys(self) -> int:
        """Return minimum number of keys required."""
        return (self.order + 1) // 2 - 1

    def max_keys(self) -> int:
        """Return maximum number of keys allowed."""
        return self.order - 1

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(keys={self.keys})"
