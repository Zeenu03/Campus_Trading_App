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
        return len(self.keys) >= self.max_keys()

    def is_underflow(self) -> bool:
        """Check if the node has fewer than minimum required keys."""
        return len(self.keys) < self.min_keys()

    def min_keys(self) -> int:
        """Return minimum number of keys required."""
        return (self.order + 1) // 2 - 1

    def max_keys(self) -> int:
        """Return maximum number of keys allowed."""
        return self.order - 1

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(keys={self.keys})"

class LeafNode(Node):
    """
    Leaf node in B+ Tree storing actual key-value pairs.

    Leaf nodes are connected in a doubly-linked list to support
    efficient range queries and sequential access.

    Attributes:
        values: List of values corresponding to keys
        next: Pointer to the next leaf node (right sibling)
        prev: Pointer to the previous leaf node (left sibling)
    """

    def __init__(self, order: int):
        """
        Initialize a leaf node.

        Args:
            order: The order of the B+ Tree
        """
        super().__init__(order)
        self.values: List[Any] = []
        self.next: Optional['LeafNode'] = None
        self.prev: Optional['LeafNode'] = None

    def is_leaf(self) -> bool:
        """Leaf nodes return True."""
        return True

    def insert_at(self, index: int, key: Any, value: Any) -> None:
        """
        Insert a key-value pair at the specified index.

        Args:
            index: Position to insert at
            key: The key to insert
            value: The associated value
        """
        self.keys.insert(index, key)
        self.values.insert(index, value)

    def remove_at(self, index: int) -> tuple:
        """
        Remove and return the key-value pair at the specified index.

        Args:
            index: Position to remove from

        Returns:
            Tuple of (key, value) that was removed
        """
        key = self.keys.pop(index)
        value = self.values.pop(index)
        return key, value

    def get_value(self, key: Any) -> Optional[Any]:
        """
        Get the value associated with a key.

        Args:
            key: The key to look up

        Returns:
            The associated value, or None if not found
        """
        try:
            index = self.keys.index(key)
            return self.values[index]
        except ValueError:
            return None

    def set_value(self, key: Any, value: Any) -> bool:
        """
        Update the value for an existing key.

        Args:
            key: The key to update
            value: The new value

        Returns:
            True if updated, False if key not found
        """
        try:
            index = self.keys.index(key)
            self.values[index] = value
            return True
        except ValueError:
            return False

    def __repr__(self) -> str:
        pairs = list(zip(self.keys, self.values))
        return f"LeafNode(pairs={pairs})"


class InternalNode(Node):
    """
    Internal node in B+ Tree storing keys and child pointers.

    For an internal node with n keys, there are n+1 children.
    Keys act as separators: all keys in children[i] are < keys[i],
    and all keys in children[i+1] are >= keys[i].

    Attributes:
        children: List of child node pointers
    """

    def __init__(self, order: int):
        """
        Initialize an internal node.

        Args:
            order: The order of the B+ Tree
        """
        super().__init__(order)
        self.children: List[Node] = []

    def is_leaf(self) -> bool:
        """Internal nodes return False."""
        return False

    def insert_child(self, index: int, key: Any, child: Node) -> None:
        """
        Insert a key and corresponding child at the specified position.

        Args:
            index: Position to insert the key
            key: The separator key
            child: The child node to insert (goes to the right of the key)
        """
        self.keys.insert(index, key)
        self.children.insert(index + 1, child)
        child.parent = self

    def remove_key(self, index: int) -> Any:
        """
        Remove and return the key at the specified index.

        Args:
            index: Position of the key to remove

        Returns:
            The removed key
        """
        return self.keys.pop(index)

    def remove_child(self, index: int) -> Node:
        """
        Remove and return the child at the specified index.

        Args:
            index: Position of the child to remove

        Returns:
            The removed child node
        """
        child = self.children.pop(index)
        child.parent = None
        return child

    def find_child_index(self, key: Any) -> int:
        """
        Find the index of the child that should contain the given key.

        Uses binary search for efficiency.

        Args:
            key: The key to search for

        Returns:
            Index of the appropriate child
        """
        left, right = 0, len(self.keys)
        while left < right:
            mid = (left + right) // 2
            if self.keys[mid] <= key:
                left = mid + 1
            else:
                right = mid
        return left

    def get_child_for_key(self, key: Any) -> Node:
        """
        Get the child node that should contain the given key.

        Args:
            key: The key to search for

        Returns:
            The appropriate child node
        """
        index = self.find_child_index(key)
        return self.children[index]

    def __repr__(self) -> str:
        return f"InternalNode(keys={self.keys}, num_children={len(self.children)})"
