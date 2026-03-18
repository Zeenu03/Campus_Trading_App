"""
BruteForceDB - Baseline Database Implementation
Campus Trading Application - CS432 Database Project

A simple list-based database implementation that serves as a baseline
for performance comparison against the B+ Tree implementation.

All operations use linear search, resulting in O(n) time complexity.
"""

from typing import Any, Optional, List, Tuple


class BruteForceDB:
    """
    Simple list-based database for baseline performance comparison.

    Uses a list of (key, value) tuples and linear search for all operations.
    This demonstrates why indexed structures like B+ Trees are necessary
    for efficient database operations.

    Time Complexity:
        - Insert: O(n) - must check for duplicates
        - Search: O(n) - linear scan
        - Delete: O(n) - linear scan to find, then O(n) to remove
        - Range Query: O(n) - must scan entire list
        - Update: O(n) - linear scan
    """

    def __init__(self):
        """Initialize an empty database."""
        self.data: List[Tuple[Any, Any]] = []

    def insert(self, key: Any, value: Any = None) -> None:
        """
        Insert a key-value pair into the database.

        If the key already exists, updates the value.

        Time Complexity: O(n)

        Args:
            key: The key to insert
            value: The associated value (default: None)
        """
        # Check for duplicate - O(n)
        for i, (k, v) in enumerate(self.data):
            if k == key:
                self.data[i] = (key, value)
                return

        # Append new entry
        self.data.append((key, value))

    def search(self, key: Any) -> Optional[Any]:
        """
        Search for a key in the database.

        Time Complexity: O(n)

        Args:
            key: The key to search for

        Returns:
            Associated value if found, None otherwise
        """
        for k, v in self.data:
            if k == key:
                return v
        return None

    def delete(self, key: Any) -> bool:
        """
        Delete a key from the database.

        Time Complexity: O(n)

        Args:
            key: The key to delete

        Returns:
            True if deleted, False if key not found
        """
        for i, (k, v) in enumerate(self.data):
            if k == key:
                self.data.pop(i)  # O(n) operation
                return True
        return False

    def update(self, key: Any, new_value: Any) -> bool:
        """
        Update the value for an existing key.

        Time Complexity: O(n)

        Args:
            key: The key to update
            new_value: The new value

        Returns:
            True if updated, False if key not found
        """
        for i, (k, v) in enumerate(self.data):
            if k == key:
                self.data[i] = (key, new_value)
                return True
        return False

    def range_query(self, start: Any, end: Any) -> List[Tuple[Any, Any]]:
        """
        Return all key-value pairs where start <= key <= end.

        Time Complexity: O(n) - must scan entire list

        Args:
            start: Lower bound (inclusive)
            end: Upper bound (inclusive)

        Returns:
            List of (key, value) tuples in the range
        """
        return [(k, v) for k, v in self.data if start <= k <= end]

    def get_all(self) -> List[Tuple[Any, Any]]:
        """
        Return all key-value pairs.

        Returns:
            Copy of all data
        """
        return self.data.copy()

    def get_sorted(self) -> List[Tuple[Any, Any]]:
        """
        Return all key-value pairs sorted by key.

        Time Complexity: O(n log n)

        Returns:
            Sorted list of (key, value) tuples
        """
        return sorted(self.data, key=lambda x: x[0])

    def clear(self) -> None:
        """Clear all data from the database."""
        self.data = []

    def __len__(self) -> int:
        """Return the number of entries in the database."""
        return len(self.data)

    def __contains__(self, key: Any) -> bool:
        """Check if a key exists in the database."""
        return any(k == key for k, _ in self.data)

    def __repr__(self) -> str:
        return f"BruteForceDB(size={len(self.data)})"

    def __iter__(self):
        """Iterate over all key-value pairs."""
        return iter(self.data)
