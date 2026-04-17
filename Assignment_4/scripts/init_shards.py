#!/usr/bin/env python3
"""Initialize all three shard databases with the required schema.

This script creates the shard tables on the assigned shard hosts without
copying any data. It uses the source database DDL as the schema definition so
the shard tables stay in sync with the application schema.

By convention, the user-facing shard labels are Shard 1, Shard 2, and Shard 3.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import mysql.connector

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from implementation.shard_router import DEFAULT_SHARD_COUNT


CENTRAL_SHARD_INDEX = 0

PARTITION_TABLES = [
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
    "sys_user",
    "sys_role",
    "sys_session",
    "sys_user_role",
    "audit_log",
    "Administrator",
    "Member",
]

REPLICATED_TABLES = [
    "Category",
]

SCHEMA_TABLES = [
    *CENTRAL_TABLES,
    *REPLICATED_TABLES,
    *PARTITION_TABLES,
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
    source_database: str
    shard_user: str
    shard_password: str
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
    parser.add_argument("--source", default="CampusTradingB")
    parser.add_argument("--shard-user", default="Optimiser")
    parser.add_argument("--shard-password", default="password@123")
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
        source_database=args.source,
        shard_user=args.shard_user,
        shard_password=args.shard_password,
        shard_hosts=shard_hosts,
        shard_ports=shard_ports,
        shard_databases=shard_databases,
    )


def connect(*, host: str, port: int, user: str, password: str, database: str | None = None):
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        autocommit=False,
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


def show_create_table(source_cursor, source_database: str, table: str) -> str:
    source_cursor.execute(f"SHOW CREATE TABLE `{source_database}`.`{table}`")
    row = source_cursor.fetchone()
    if not row:
        raise ValueError(f"Unable to read DDL for {source_database}.{table}")
    return row[1]


def ensure_database(shard_connection, database_name: str) -> None:
    shard_cursor = shard_connection.cursor()
    shard_cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}`")
    shard_connection.commit()


def create_schema_on_shard(source_cursor, shard_connection, shard_config: ShardConfig, source_database: str) -> int:
    ensure_database(shard_connection, shard_config.database_name)

    shard_cursor = shard_connection.cursor()
    shard_cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

    created_tables = 0
    shard_cursor.execute(f"USE `{shard_config.database_name}`")
    for table in reversed(SCHEMA_TABLES):
        shard_cursor.execute(f"DROP TABLE IF EXISTS `{table}`")

    for table in TABLES_FOR_SHARD[shard_config.shard_id]:
        create_sql = show_create_table(source_cursor, source_database, table)
        create_sql = create_sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
        shard_cursor.execute(create_sql)
        created_tables += 1

    shard_connection.commit()
    shard_cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    shard_connection.commit()
    return created_tables


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

    try:
        for shard_config, shard_connection in zip(shard_configs, shard_connections, strict=True):
            count = create_schema_on_shard(source_cursor, shard_connection, shard_config, config.source_database)
            print(f"Shard {shard_config.shard_id + 1}: initialized {count} tables in {shard_config.database_name}")
    finally:
        for shard_connection in shard_connections:
            shard_connection.close()
        source_connection.close()


if __name__ == "__main__":
    main()