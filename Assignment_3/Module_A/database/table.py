"""
Table abstraction built on top of B+ Tree.

Provides schema validation and record-level CRUD operations so higher-level
components (like DatabaseManager) can manage multiple logical tables.
"""

from copy import deepcopy
from typing import Any, Dict, List, Tuple

from .bplustree import BPlusTree


class Table:
    """Simple in-memory table backed by a B+ Tree index."""

    def __init__(self, name: str, schema: Dict[str, type], order: int = 8, search_key: str | None = None):
        if not schema:
            raise ValueError("Schema cannot be empty")

        if search_key is None:
            # If no explicit key is provided, use the first schema field.
            search_key = next(iter(schema.keys()))

        if search_key not in schema:
            raise ValueError(f"search_key '{search_key}' must exist in schema")

        self.name = name
        self.schema = dict(schema)
        self.order = order
        self.search_key = search_key
        self.data = BPlusTree(order=order)

    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate schema completeness and field types for a record."""
        if not isinstance(record, dict):
            return False, "Record must be a dictionary"

        missing_columns = [col for col in self.schema if col not in record]
        extra_columns = [col for col in record if col not in self.schema]

        if missing_columns:
            return False, f"Missing required columns: {missing_columns}"
        if extra_columns:
            return False, f"Unknown columns provided: {extra_columns}"

        for field, expected_type in self.schema.items():
            value = record[field]
            if value is None:
                continue
            if not isinstance(value, expected_type):
                return (
                    False,
                    f"Invalid type for '{field}': expected {expected_type.__name__}, got {type(value).__name__}",
                )

        return True, "Record is valid"

    def insert(self, record: Dict[str, Any]) -> Tuple[bool, str]:
        """Insert a record after validation using the configured search key."""
        is_valid, message = self.validate_record(record)
        if not is_valid:
            return False, message

        key = record[self.search_key]
        self.data.insert(key, deepcopy(record))
        return True, f"Record inserted in table '{self.name}'"

    def get(self, record_id: Any) -> Dict[str, Any] | None:
        """Retrieve a single record by search key."""
        value = self.data.search(record_id)
        return deepcopy(value) if value is not None else None

    def get_all(self) -> List[Tuple[Any, Dict[str, Any]]]:
        """Retrieve all records sorted by search key."""
        rows = self.data.get_all()
        return [(k, deepcopy(v)) for k, v in rows]

    def update(self, record_id: Any, new_record: Dict[str, Any]) -> Tuple[bool, str]:
        """Update record identified by record_id."""
        if self.data.search(record_id) is None:
            return False, f"Record with key '{record_id}' not found"

        is_valid, message = self.validate_record(new_record)
        if not is_valid:
            return False, message

        new_key = new_record[self.search_key]

        # If key changes, delete old key and re-insert under new key.
        if new_key != record_id:
            self.data.delete(record_id)
            self.data.insert(new_key, deepcopy(new_record))
            return True, f"Record key changed from '{record_id}' to '{new_key}'"

        updated = self.data.update(record_id, deepcopy(new_record))
        if not updated:
            return False, f"Failed to update record with key '{record_id}'"

        return True, f"Record '{record_id}' updated"

    def delete(self, record_id: Any) -> Tuple[bool, str]:
        """Delete a record by search key."""
        deleted = self.data.delete(record_id)
        if not deleted:
            return False, f"Record with key '{record_id}' not found"
        return True, f"Record '{record_id}' deleted"

    def range_query(self, start_value: Any, end_value: Any) -> List[Tuple[Any, Dict[str, Any]]]:
        """Return records in [start_value, end_value] by search key."""
        rows = self.data.range_query(start_value, end_value)
        return [(k, deepcopy(v)) for k, v in rows]

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        return (
            f"Table(name='{self.name}', key='{self.search_key}', "
            f"columns={list(self.schema.keys())}, size={len(self)})"
        )
