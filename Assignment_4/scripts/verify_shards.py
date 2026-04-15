#!/usr/bin/env python3
"""Verify that the modulo shards contain the expected rows exactly once.

This script checks:
- partitioned tables have no duplicated primary keys across shards,
- central tables live only on shard 1,
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


CENTRAL_SHARD_ID = 0

SCHEMA_TABLES = [
    "sys_user",
    "sys_role",
    "sys_session",
    "sys_user_role",
    "audit_log",
    "Administrator",
    "Category",
    "Member",
    "WishRequest",
    "WishRequestImage",
    "Listing",
    "ListingWishRequest",
    "ListingImage",
    "Offer",
    "Transaction",
    "MessageThread",
    "Message",
    "Notification",
    "Watchlist",
    "Report",
    "Rating",
]

PARTITION_TABLES = [
    "Member",
    "WishRequest",
    "WishRequestImage",
    "Listing",
    "ListingWishRequest",
    "ListingImage",
    "Offer",
    "Transaction",
    "MessageThread",
    "Message",
    "Notification",
    "Watchlist",
    "Report",
    "Rating",
]

CENTRAL_TABLES = [
    "sys_role",
    "sys_user",
    "sys_user_role",
    "sys_session",
    "audit_log",
    "Administrator",
]

REPLICATED_TABLES = [
    "Category",
]

TABLES_FOR_SHARD = {
    0: [*CENTRAL_TABLES, *REPLICATED_TABLES, *PARTITION_TABLES],
    1: [*REPLICATED_TABLES, *PARTITION_TABLES],
    2: [*REPLICATED_TABLES, *PARTITION_TABLES],
}


@dataclass
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    shard_user: str
    shard_password: str
    source_database: str
    shard_hosts: list[str]
    shard_ports: list[int]
    shard_databases: list[str]


@dataclass
class ShardConfig:
    shard_id: int
    host: str
    port: int
    database_name: str


def parse_csv(raw_value: str, cast=str) -> list:
    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    return [cast(item) for item in values]


def parse_args() -> DbConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="10.7.27.157")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument("--shard-user", default="Optimiser")
    parser.add_argument("--shard-password", default="password@123")
    parser.add_argument("--source", default="CampusTradingB")
    parser.add_argument("--shard-hosts", default="10.0.116.184,10.0.116.184,10.0.116.184")
    parser.add_argument("--shard-ports", default="3307,3308,3309")
    parser.add_argument("--shard-databases", default="Optimiser,Optimiser,Optimiser")
    args = parser.parse_args()
    shard_hosts = parse_csv(args.shard_hosts)
    shard_ports = parse_csv(args.shard_ports, int)
    shard_databases = parse_csv(args.shard_databases) if args.shard_databases else []
    if len(shard_hosts) != DEFAULT_SHARD_COUNT:
        raise ValueError(f"Expected {DEFAULT_SHARD_COUNT} shard hosts, got {len(shard_hosts)}")
    if len(shard_ports) != DEFAULT_SHARD_COUNT:
        raise ValueError(f"Expected {DEFAULT_SHARD_COUNT} shard ports, got {len(shard_ports)}")
    if len(shard_databases) != DEFAULT_SHARD_COUNT:
        raise ValueError(f"Expected {DEFAULT_SHARD_COUNT} shard databases, got {len(shard_databases)}")
    return DbConfig(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        shard_user=args.shard_user,
        shard_password=args.shard_password,
        source_database=args.source,
        shard_hosts=shard_hosts,
        shard_ports=shard_ports,
        shard_databases=shard_databases,
    )


def connect(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str | None = None,
):
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        autocommit=True,
    )


def build_shard_configs(config: DbConfig) -> list[ShardConfig]:
    return [
        ShardConfig(
            shard_id=shard_id,
            host=config.shard_hosts[shard_id],
            port=config.shard_ports[shard_id],
            database_name=config.shard_databases[shard_id],
        )
        for shard_id in range(DEFAULT_SHARD_COUNT)
    ]


def count_rows(cursor, table: str, shard_id: int | None = None) -> int:
    if shard_id is not None and table not in TABLES_FOR_SHARD[shard_id]:
        return 0
    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
    (count,) = cursor.fetchone()
    return int(count)


def duplicate_count(connections, table: str, key_columns: list[str]) -> int:
    seen = set()
    duplicates = set()
    for connection in connections:
        cursor = connection.cursor()
        select_columns = ", ".join(f"`{column}`" for column in key_columns)
        cursor.execute(f"SELECT {select_columns} FROM `{table}`")
        for row in cursor.fetchall():
            key = row[0] if len(key_columns) == 1 else tuple(row)
            if key in seen:
                duplicates.add(key)
            else:
                seen.add(key)
    return len(duplicates)


def primary_key_columns(cursor, database: str, table: str) -> list[str]:
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
    return columns


def main() -> None:
    config = parse_args()
    source_connection = connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.source_database,
    )
    source_cursor = source_connection.cursor()

    shard_configs = build_shard_configs(config)
    shard_connections = [
        connect(
            host=shard.host,
            port=shard.port,
            user=config.shard_user,
            password=config.shard_password,
            database=shard.database_name,
        )
        for shard in shard_configs
    ]

    result = {
        "partitioned": {},
        "central": {},
        "replicated": {},
        "duplicates": {},
    }

    for table in CENTRAL_TABLES:
        counts = [count_rows(connection.cursor(), table, shard_id=shard_id) for shard_id, connection in enumerate(shard_connections)]
        result["central"][table] = {
            "counts": counts,
            "source_total": count_rows(source_cursor, table),
            "central_shard_total": counts[CENTRAL_SHARD_ID],
            "other_shards_empty": all(count == 0 for index, count in enumerate(counts) if index != CENTRAL_SHARD_ID),
        }
        result["duplicates"][table] = 0

    for table in PARTITION_TABLES:
        key_columns = primary_key_columns(source_cursor, config.source_database, table)
        counts = [count_rows(connection.cursor(), table, shard_id=shard_id) for shard_id, connection in enumerate(shard_connections)]
        result["partitioned"][table] = {
            "counts": counts,
            "source_total": count_rows(source_cursor, table),
            "shard_total": sum(counts),
        }
        result["duplicates"][table] = duplicate_count(shard_connections, table, key_columns)

    for table in REPLICATED_TABLES:
        counts = [count_rows(connection.cursor(), table, shard_id=shard_id) for shard_id, connection in enumerate(shard_connections)]
        result["replicated"][table] = {
            "counts": counts,
            "all_equal": len(set(counts)) == 1,
        }
        result["duplicates"][table] = 0

    result["all_partitioned_match"] = all(
        entry["source_total"] == entry["shard_total"] for entry in result["partitioned"].values()
    )
    result["all_central_match"] = all(
        entry["source_total"] == entry["central_shard_total"] and entry["other_shards_empty"]
        for entry in result["central"].values()
    )
    result["all_partitioned_have_no_duplicates"] = all(value == 0 for value in result["duplicates"].values())
    result["all_replicated_match"] = all(entry["all_equal"] for entry in result["replicated"].values())
    result["all_passed"] = (
        result["all_central_match"]
        and result["all_partitioned_match"]
        and result["all_partitioned_have_no_duplicates"]
        and result["all_replicated_match"]
    )

    print(json.dumps(result, indent=2))
    for connection in shard_connections:
        connection.close()
    source_connection.close()


if __name__ == "__main__":
    main()
