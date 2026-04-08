#!/usr/bin/env python3
"""Verify that the modulo shards contain the expected rows exactly once.

This script checks:
- partitioned tables have no duplicated primary keys across shards,
- replicated tables contain the same row count on all shards,
- totals across shards match the source database for partitioned tables.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import mysql.connector

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from implementation.shard_router import DEFAULT_SHARD_COUNT, TABLE_ROUTING


PARTITION_TABLES = [
    "Member",
    "WishRequest",
    "Listing",
    "ListingImage",
    "Offer",
    "Transaction",
    "MessageThread",
    "Message",
    "Watchlist",
    "Report",
    "Rating",
    "Notification",
]

REPLICATED_TABLES = ["Administrator", "Category"]


@dataclass
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    source_database: str


def parse_args() -> DbConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument("--source", default="CampusTradingB")
    args = parser.parse_args()
    return DbConfig(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        source_database=args.source,
    )


def connect(config: DbConfig, database: str | None = None):
    return mysql.connector.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=database,
        autocommit=True,
    )


def count_rows(cursor, database: str, table: str) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM `{database}`.`{table}`")
    (count,) = cursor.fetchone()
    return int(count)


def duplicate_count(cursor, databases: list[str], table: str, key_name: str) -> int:
    union_query = " UNION ALL ".join(
        f"SELECT `{key_name}` AS key_value FROM `{database}`.`{table}`"
        for database in databases
    )
    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT key_value, COUNT(*) AS occurrences
            FROM ({union_query}) AS shard_rows
            GROUP BY key_value
            HAVING occurrences > 1
        ) AS duplicates
        """
    )
    (count,) = cursor.fetchone()
    return int(count)


def primary_key_column(cursor, database: str, table: str) -> str:
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
          AND CONSTRAINT_NAME = 'PRIMARY'
        ORDER BY ORDINAL_POSITION
        """,
        (database, table),
    )
    columns = [row[0] for row in cursor.fetchall()]
    if not columns:
        raise ValueError(f"No primary key found for {database}.{table}")
    if len(columns) != 1:
        raise ValueError(f"Composite primary keys are not supported for {database}.{table}")
    return columns[0]


def main() -> None:
    config = parse_args()
    connection = connect(config, database=config.source_database)
    cursor = connection.cursor()

    databases = [f"{config.source_database}_shard_{shard_id}" for shard_id in range(DEFAULT_SHARD_COUNT)]
    result = {
        "partitioned": {},
        "replicated": {},
        "duplicates": {},
    }

    for table in PARTITION_TABLES:
        key_name = primary_key_column(cursor, config.source_database, table)
        counts = [count_rows(cursor, database, table) for database in databases]
        result["partitioned"][table] = {
            "counts": counts,
            "source_total": count_rows(cursor, config.source_database, table),
            "shard_total": sum(counts),
        }
        result["duplicates"][table] = duplicate_count(cursor, databases, table, key_name)

    for table in REPLICATED_TABLES:
        counts = [count_rows(cursor, database, table) for database in databases]
        result["replicated"][table] = {
            "counts": counts,
            "all_equal": len(set(counts)) == 1,
        }
        result["duplicates"][table] = 0

    result["all_partitioned_match"] = all(
        entry["source_total"] == entry["shard_total"] for entry in result["partitioned"].values()
    )
    result["all_partitioned_have_no_duplicates"] = all(value == 0 for value in result["duplicates"].values())
    result["all_replicated_match"] = all(entry["all_equal"] for entry in result["replicated"].values())
    result["all_passed"] = (
        result["all_partitioned_match"]
        and result["all_partitioned_have_no_duplicates"]
        and result["all_replicated_match"]
    )

    print(json.dumps(result, indent=2))
    connection.close()


if __name__ == "__main__":
    main()
