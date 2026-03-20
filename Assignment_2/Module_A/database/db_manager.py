"""
Database manager for organizing multiple logical databases and tables.

This mirrors the instructor template workflow while using this module's Table
and B+ Tree implementations.
"""

from typing import Dict, List, Tuple

from .table import Table


class DatabaseManager:
    """Manage logical databases where each database contains named tables."""

    def __init__(self):
        self.databases: Dict[str, Dict[str, Table]] = {}

    def create_database(self, db_name: str) -> Tuple[bool, str]:
        """Create an empty logical database."""
        if not db_name:
            return False, "Database name cannot be empty"

        if db_name in self.databases:
            return False, f"Database '{db_name}' already exists"

        self.databases[db_name] = {}
        return True, f"Database '{db_name}' created"

    def delete_database(self, db_name: str) -> Tuple[bool, str]:
        """Delete a database and all its tables."""
        if db_name not in self.databases:
            return False, f"Database '{db_name}' does not exist"

        del self.databases[db_name]
        return True, f"Database '{db_name}' deleted"

    def list_databases(self) -> List[str]:
        """Return all managed database names."""
        return list(self.databases.keys())

    def create_table(
        self,
        db_name: str,
        table_name: str,
        schema: Dict[str, type],
        order: int = 8,
        search_key: str | None = None,
    ) -> Tuple[bool, str]:
        """Create a table inside an existing database."""
        if db_name not in self.databases:
            return False, f"Database '{db_name}' does not exist"

        if not table_name:
            return False, "Table name cannot be empty"

        if table_name in self.databases[db_name]:
            return False, f"Table '{table_name}' already exists in '{db_name}'"

        try:
            table = Table(table_name, schema, order=order, search_key=search_key)
        except ValueError as exc:
            return False, str(exc)

        self.databases[db_name][table_name] = table
        return True, f"Table '{table_name}' created in database '{db_name}'"

    def delete_table(self, db_name: str, table_name: str) -> Tuple[bool, str]:
        """Delete a table from a database."""
        if db_name not in self.databases:
            return False, f"Database '{db_name}' does not exist"

        if table_name not in self.databases[db_name]:
            return False, f"Table '{table_name}' does not exist in '{db_name}'"

        del self.databases[db_name][table_name]
        return True, f"Table '{table_name}' deleted from '{db_name}'"

    def list_tables(self, db_name: str) -> Tuple[List[str], str]:
        """List table names in a database."""
        if db_name not in self.databases:
            return [], f"Database '{db_name}' does not exist"

        return list(self.databases[db_name].keys()), "OK"

    def get_table(self, db_name: str, table_name: str) -> Tuple[Table | None, str]:
        """Return a table handle for CRUD operations."""
        if db_name not in self.databases:
            return None, f"Database '{db_name}' does not exist"

        table = self.databases[db_name].get(table_name)
        if table is None:
            return None, f"Table '{table_name}' does not exist in '{db_name}'"

        return table, "OK"
