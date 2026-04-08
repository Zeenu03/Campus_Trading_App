#!/usr/bin/env python3
"""Migrate the monolithic CampusTradingB data set into 3 modulo shards.

The script is intentionally conservative:
- it uses a deterministic % 3 rule,
- it preserves primary keys while copying,
- it replicates Category to every shard,
- it writes a summary of row counts and duplicate checks.

Usage example:
    python scripts/migrate_shards.py \
        --host 127.0.0.1 --port 3306 --user root --password root \
        --source CampusTradingB
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

from implementation.shard_router import DEFAULT_SHARD_COUNT, ShardRouter, TABLE_ROUTING


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
    connection = mysql.connector.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=database,
        autocommit=False,
    )
    return connection


def fetch_primary_rows(cursor, database: str, table: str):
    cursor.execute(f"SELECT * FROM `{database}`.`{table}`")
    columns = [column[0] for column in cursor.description]
    return columns, cursor.fetchall()


def table_primary_key(table: str) -> str:
    return TABLE_ROUTING[table][0]


def require_shard_databases(cursor, base_database: str, shard_count: int = DEFAULT_SHARD_COUNT) -> None:
    expected_databases = [f"{base_database}_shard_{shard_id}" for shard_id in range(shard_count)]
    placeholders = ", ".join(["%s"] * len(expected_databases))
    cursor.execute(
        f"SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME IN ({placeholders})",
        expected_databases,
    )
    found_databases = {row[0] for row in cursor.fetchall()}
    missing_databases = [database for database in expected_databases if database not in found_databases]
    if missing_databases:
        raise RuntimeError(
            "Missing shard database(s): " + ", ".join(missing_databases)
        )


def build_insert_statement(database: str, table: str, columns: list[str]) -> str:
    column_list = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    return f"INSERT INTO `{database}`.`{table}` ({column_list}) VALUES ({placeholders})"


def value_for_routing(table: str, row: tuple, columns: list[str]) -> int:
    key_name, strategy = TABLE_ROUTING[table]
    if strategy == "replicate":
        return 0
    key_index = columns.index(key_name)
    return int(row[key_index])


def copy_partitioned_table(source_cursor, shard_connections, router: ShardRouter, base_database: str, table: str) -> dict[int, int]:
    columns, rows = fetch_primary_rows(source_cursor, base_database, table)
    insert_sql_cache: dict[int, str] = {}
    row_count_by_shard = {shard_id: 0 for shard_id in range(DEFAULT_SHARD_COUNT)}

    for row in rows:
        routing_value = value_for_routing(table, row, columns)
        shard_id = router.shard_id_for(routing_value)
        shard_connection = shard_connections[shard_id]
        shard_cursor = shard_connection.cursor()

        insert_sql = insert_sql_cache.get(shard_id)
        if insert_sql is None:
            insert_sql = build_insert_statement(f"{base_database}_shard_{shard_id}", table, columns)
            insert_sql_cache[shard_id] = insert_sql

        shard_cursor.execute(insert_sql, row)
        row_count_by_shard[shard_id] += 1

    for shard_connection in shard_connections:
        shard_connection.commit()

    return row_count_by_shard


def copy_replicated_table(source_cursor, shard_connections, base_database: str, table: str) -> dict[int, int]:
    columns, rows = fetch_primary_rows(source_cursor, base_database, table)
    insert_sql_by_shard = {
        shard_id: build_insert_statement(f"{base_database}_shard_{shard_id}", table, columns)
        for shard_id in range(DEFAULT_SHARD_COUNT)
    }

    counts = {}
    for shard_id, shard_connection in enumerate(shard_connections):
        shard_cursor = shard_connection.cursor()
        for row in rows:
            shard_cursor.execute(insert_sql_by_shard[shard_id], row)
        shard_connection.commit()
        counts[shard_id] = len(rows)

    return counts


def summarise_counts(source_cursor, base_database: str, table: str, shard_count: int = DEFAULT_SHARD_COUNT) -> dict[str, int]:
    source_cursor.execute(f"SELECT COUNT(*) FROM `{base_database}`.`{table}`")
    (source_count,) = source_cursor.fetchone()

    shard_counts = []
    for shard_id in range(shard_count):
        source_cursor.execute(f"SELECT COUNT(*) FROM `{base_database}_shard_{shard_id}`.`{table}`")
        (count,) = source_cursor.fetchone()
        shard_counts.append(count)

    return {
        "source": int(source_count),
        "shard_0": int(shard_counts[0]),
        "shard_1": int(shard_counts[1]),
        "shard_2": int(shard_counts[2]),
        "total_shards": int(sum(shard_counts)),
    }


def check_duplicates(source_cursor, base_database: str, table: str, key_name: str) -> int:
    union_query = " UNION ALL ".join(
        f"SELECT `{key_name}` AS key_value FROM `{base_database}_shard_{shard_id}`.`{table}`"
        for shard_id in range(DEFAULT_SHARD_COUNT)
    )
    source_cursor.execute(
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
    (duplicate_count,) = source_cursor.fetchone()
    return int(duplicate_count)


def main() -> None:
    config = parse_args()
    router = ShardRouter()
    source_connection = connect(config, database=config.source_database)
    source_cursor = source_connection.cursor()

    require_shard_databases(source_cursor, config.source_database)

    shard_connections = [connect(config, database=f"{config.source_database}_shard_{shard_id}") for shard_id in range(DEFAULT_SHARD_COUNT)]

    summary = {"partitioned": {}, "replicated": {}, "duplicates": {}}

    for table in PARTITION_TABLES:
        summary["partitioned"][table] = copy_partitioned_table(source_cursor, shard_connections, router, config.source_database, table)
        summary["duplicates"][table] = check_duplicates(source_cursor, config.source_database, table, table_primary_key(table))

    for table in REPLICATED_TABLES:
        summary["replicated"][table] = copy_replicated_table(source_cursor, shard_connections, config.source_database, table)
        summary["duplicates"][table] = 0

    source_connection.commit()

    summary["row_counts"] = {
        table: summarise_counts(source_cursor, config.source_database, table)
        for table in PARTITION_TABLES + REPLICATED_TABLES
    }

    output_path = Path(__file__).with_name("shard_migration_summary.json")
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))

    for shard_connection in shard_connections:
        shard_connection.close()
    source_connection.close()


if __name__ == "__main__":
    main()
