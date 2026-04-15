#!/usr/bin/env python3
"""Migrate the monolithic source database into 3 modulo shards.

The script is intentionally conservative:
- it uses a deterministic % 3 rule,
- it preserves primary keys while copying,
- it keeps low-usage control tables on shard 1 only,
- it replicates Category to every shard,
- it writes a summary of row counts and duplicate checks.

Usage example:
    python scripts/migrate_shards.py \
    --host 10.7.27.157 --port 3306 --user root --password root \
    --source CampusTradingB \
    --shard-hosts 10.0.116.184,10.0.116.184,10.0.116.184 \
    --shard-ports 3307,3308,3309 \
    --shard-databases Optimiser,Optimiser,Optimiser
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

PARTITION_ROUTE_COLUMNS = {
    "Member": "MemberID",
    "WishRequest": "WishRequestID",
    "WishRequestImage": "WishRequestID",
    "Listing": "ListingID",
    "ListingWishRequest": "ListingID",
    "ListingImage": "ImageID",
    "Offer": "OfferID",
    "Transaction": "TransactionID",
    "MessageThread": "ThreadID",
    "Message": "MessageID",
    "Notification": "NotificationID",
    "Watchlist": "WatchlistID",
    "Report": "ReportID",
    "Rating": "RatingID",
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
    autocommit: bool = False,
):
    connection = mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        autocommit=autocommit,
    )
    return connection


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


def fetch_primary_rows(cursor, database: str, table: str):
    cursor.execute(f"SELECT * FROM `{database}`.`{table}`")
    columns = [column[0] for column in cursor.description]
    return columns, cursor.fetchall()


def table_primary_key(table: str) -> str:
    return TABLE_ROUTING[table][0]


def build_insert_statement(database: str, table: str, columns: list[str]) -> str:
    column_list = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    return f"INSERT INTO `{database}`.`{table}` ({column_list}) VALUES ({placeholders})"


def show_create_table(source_cursor, database: str, table: str) -> str:
    source_cursor.execute(f"SHOW CREATE TABLE `{database}`.`{table}`")
    row = source_cursor.fetchone()
    if not row:
        raise ValueError(f"Unable to read DDL for {database}.{table}")
    return row[1]


def primary_key_columns(source_cursor, database: str, table: str) -> list[str]:
    source_cursor.execute(
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
    columns = [row[0] for row in source_cursor.fetchall()]
    if not columns:
        raise ValueError(f"No primary key found for {database}.{table}")
    return columns


def create_schema_on_shards(source_cursor, shard_connections, source_database: str) -> None:
    for shard_id, shard_connection in enumerate(shard_connections):
        for table in TABLES_FOR_SHARD[shard_id]:
            create_sql = show_create_table(source_cursor, source_database, table)
            create_sql = create_sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1)
            shard_cursor = shard_connection.cursor()
            shard_cursor.execute(create_sql)
        shard_connection.commit()


def reset_shard_data(shard_connections) -> None:
    for shard_id, shard_connection in enumerate(shard_connections):
        shard_cursor = shard_connection.cursor()
        for table in reversed(TABLES_FOR_SHARD[shard_id]):
            shard_cursor.execute(f"DELETE FROM `{table}`")
        shard_connection.commit()


def route_value_for_table(table: str, row: tuple, columns: list[str]) -> int:
    route_column = PARTITION_ROUTE_COLUMNS[table]
    return int(row[columns.index(route_column)])


def copy_partitioned_table(source_cursor, shard_connections, shard_configs: list[ShardConfig], router: ShardRouter, base_database: str, table: str) -> dict[int, int]:
    columns, rows = fetch_primary_rows(source_cursor, base_database, table)
    insert_sql_cache: dict[int, str] = {}
    row_count_by_shard = {shard_id: 0 for shard_id in range(DEFAULT_SHARD_COUNT)}

    for row in rows:
        routing_value = route_value_for_table(table, row, columns)
        shard_id = router.shard_id_for(routing_value)
        shard_connection = shard_connections[shard_id]
        shard_cursor = shard_connection.cursor()

        insert_sql = insert_sql_cache.get(shard_id)
        if insert_sql is None:
            insert_sql = build_insert_statement(shard_configs[shard_id].database_name, table, columns)
            insert_sql_cache[shard_id] = insert_sql

        shard_cursor.execute(insert_sql, row)
        row_count_by_shard[shard_id] += 1

    for shard_connection in shard_connections:
        shard_connection.commit()

    return row_count_by_shard


def copy_replicated_table(source_cursor, shard_connections, shard_configs: list[ShardConfig], base_database: str, table: str) -> dict[int, int]:
    columns, rows = fetch_primary_rows(source_cursor, base_database, table)
    insert_sql_by_shard = {
        shard_id: build_insert_statement(shard_configs[shard_id].database_name, table, columns)
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


def copy_central_table(source_cursor, shard_connections, shard_configs: list[ShardConfig], base_database: str, table: str) -> dict[int, int]:
    columns, rows = fetch_primary_rows(source_cursor, base_database, table)
    insert_sql = build_insert_statement(shard_configs[CENTRAL_SHARD_ID].database_name, table, columns)

    counts = {shard_id: 0 for shard_id in range(DEFAULT_SHARD_COUNT)}
    shard_connection = shard_connections[CENTRAL_SHARD_ID]
    shard_cursor = shard_connection.cursor()
    for row in rows:
        shard_cursor.execute(insert_sql, row)
    shard_connection.commit()
    counts[CENTRAL_SHARD_ID] = len(rows)

    return counts


def summarise_counts(source_cursor, shard_connections, table: str, source_database: str) -> dict[str, int]:
    source_cursor.execute(f"SELECT COUNT(*) FROM `{source_database}`.`{table}`")
    (source_count,) = source_cursor.fetchone()

    shard_counts = []
    for shard_id, shard_connection in enumerate(shard_connections):
        if table not in TABLES_FOR_SHARD[shard_id]:
            shard_counts.append(0)
            continue
        shard_cursor = shard_connection.cursor()
        shard_cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
        (count,) = shard_cursor.fetchone()
        shard_counts.append(count)

    return {
        "source": int(source_count),
        "shard_0": int(shard_counts[0]),
        "shard_1": int(shard_counts[1]),
        "shard_2": int(shard_counts[2]),
        "total_shards": int(sum(shard_counts)),
    }


def check_duplicates(shard_connections, table: str, key_columns: list[str]) -> int:
    seen = set()
    duplicates = set()
    for shard_connection in shard_connections:
        shard_cursor = shard_connection.cursor()
        select_columns = ", ".join(f"`{column}`" for column in key_columns)
        shard_cursor.execute(f"SELECT {select_columns} FROM `{table}`")
        for row in shard_cursor.fetchall():
            key = row[0] if len(key_columns) == 1 else tuple(row)
            if key in seen:
                duplicates.add(key)
            else:
                seen.add(key)
    return len(duplicates)


def main() -> None:
    config = parse_args()
    router = ShardRouter()
    source_connection = connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.source_database,
        autocommit=False,
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
            autocommit=False,
        )
        for shard in shard_configs
    ]

    for shard_connection in shard_connections:
        shard_connection.cursor().execute("SET FOREIGN_KEY_CHECKS = 0")

    summary = {"partitioned": {}, "central": {}, "replicated": {}, "duplicates": {}}

    create_schema_on_shards(source_cursor, shard_connections, config.source_database)
    reset_shard_data(shard_connections)

    for table in CENTRAL_TABLES:
        summary["central"][table] = copy_central_table(source_cursor, shard_connections, shard_configs, config.source_database, table)
        summary["duplicates"][table] = 0

    for table in REPLICATED_TABLES:
        summary["replicated"][table] = copy_replicated_table(source_cursor, shard_connections, shard_configs, config.source_database, table)
        summary["duplicates"][table] = 0

    for table in PARTITION_TABLES:
        summary["partitioned"][table] = copy_partitioned_table(source_cursor, shard_connections, shard_configs, router, config.source_database, table)
        summary["duplicates"][table] = check_duplicates(shard_connections, table, primary_key_columns(source_cursor, config.source_database, table))

    source_connection.commit()

    summary["row_counts"] = {
        table: summarise_counts(source_cursor, shard_connections, table, config.source_database)
        for table in PARTITION_TABLES + CENTRAL_TABLES + REPLICATED_TABLES
    }

    output_path = Path(__file__).with_name("shard_migration_summary.json")
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))

    for shard_connection in shard_connections:
        shard_connection.cursor().execute("SET FOREIGN_KEY_CHECKS = 1")

    for shard_connection in shard_connections:
        shard_connection.close()
    source_connection.close()


if __name__ == "__main__":
    main()
