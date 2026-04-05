"""
Database package: B+ Tree engine (Assignment 2) + transactions, WAL, and
recovery (Assignment 3).

Core engine (schema-neutral):
    from database import BPlusTree, Table, DatabaseManager
    from database import WriteAheadLog, TransactionManager, RecoveryManager

Campus-specific domain helpers (not part of the engine):
    from database.campus_schema import SeedProfile, install_campus_schema, seed_campus_tables
    from database.campus_workflow import accept_offer_atomic

Ergonomic API wrappers:
    from database.table_api import TransactionalTable, DatabaseAPI

Display helpers for notebooks and terminals:
    from database.table_display import format_table, format_database_tables, snapshot_for_ipython
"""

from .node import Node, LeafNode, InternalNode
from .bplustree import BPlusTree
from .table import Table
from .db_manager import DatabaseManager
from .wal import WriteAheadLog
from .transaction import ChangeRecord, TransactionManager, TransactionState
from .recovery import RecoveryManager

__all__ = [
    "Node",
    "LeafNode",
    "InternalNode",
    "BPlusTree",
    "BruteForceDB",
    "Table",
    "DatabaseManager",
    "WriteAheadLog",
    "ChangeRecord",
    "TransactionManager",
    "TransactionState",
    "RecoveryManager",
]

__version__ = "2.0.0"
__author__ = "Team 8 - CS432"
