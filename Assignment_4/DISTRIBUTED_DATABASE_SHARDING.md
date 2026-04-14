# Distributed Database Sharding — Assignment 4

This document describes how the **Campus Trading App (Assignment 4)** satisfies the course requirements for **data sharding and query routing** across **three shards**. It aligns the published lab infrastructure with the code and scripts in this repository.

---

## 1. Lab infrastructure (reference)

| Role | Host | Port / URL |
|------|------|----------------|
| **Shard 1 (MySQL)** | `10.0.116.184` | `3307` |
| **Shard 2 (MySQL)** | `10.0.116.184` | `3308` |
| **Shard 3 (MySQL)** | `10.0.116.184` | `3309` |
| **phpMyAdmin (shard 1)** | `10.0.116.184` | `http://10.0.116.184:8080/` |
| **phpMyAdmin (shard 2)** | `10.0.116.184` | `http://10.0.116.184:8081/` |
| **phpMyAdmin (shard 3)** | `10.0.116.184` | `http://10.0.116.184:8082/` |

**Credentials (pattern):**

| Setting | Value |
|---------|--------|
| Username | Your assigned **team name** (see course list) |
| Password | `password@123` |
| Database | Same as username (e.g. `Data_Squad` → database `Data_Squad`) |

**Important rules (course):**

- Use **only** your team’s database; do not read or write other teams’ schemas.
- Do **not** create new MySQL users.
- Do **not** use system schemas such as `mysql` or `sys` for application data.
- Use **all three** shards in the implementation.
- Prefer **no unintended duplication** of partitioned rows across shards (replicated reference data is intentional).

**phpMyAdmin login tip:** use **User** and **Password** as given; if the UI asks for **Server**, leave it empty per lab instructions.

**Network:** shard access is typically available only from the **IITGN** network.

---

## 2. Task checklist (mapped to this project)

| # | Requirement | How it is addressed here |
|---|-------------|---------------------------|
| 1 | **Shard key** | Integer **primary key** of each partitioned table (e.g. `ListingID`, `MemberID`). Routing: `shard_id = record_id % 3`. |
| 2 | **Partitioning strategy** | **Hash-style** placement via **modulo 3** (equivalent to hash bucket count 3 without a separate hash function). |
| 3 | **Distribute data** | SQL DDL creates `<BaseDB>_shard_0..2`; **Python** `scripts/migrate_shards.py` copies rows from the source DB into the correct shard. |
| 4 | **Route inserts** | **Go** backend picks shard from new or parent ID (`nextRecordID`, `ShardConnectionForRecordID`, table-specific helpers). |
| 5 | **Route lookups** | Point reads use the **owning shard**; replicated tables read from a **canonical shard** (shard 0 in helpers). |
| 6 | **Range / global queries** | **Fan-out** to all shard connections, merge in application code (e.g. listing browse, `nextRecordID` MAX across shards). |

---

## 3. Shard key — choice and rationale

**Shard key:** the **surrogate primary key** of each sharded entity (numeric auto-increment style IDs in the schema).

**Routing function:**

\[
\text{shard\_id} = \text{record\_id} \bmod 3
\]

with the convention that remainders `0`, `1`, `2` map to **Shard 1 / 2 / 3** respectively in a **0-based** index in code (`shard_0` … `shard_2`).

**Why this works well for this app:**

- **Stable:** IDs do not change after insert, so rows never “move” shards unless you explicitly migrate.
- **O(1) routing:** no lookup table is required at runtime for partitioned tables.
- **Even spread:** consecutive IDs land on different shards, reducing hot spots compared to naive range partitioning on monotonic IDs.

**Central implementation:** `Assignment_4/backend/sharding/router.go` (`ShardIDFor`, `TargetFor`, `RouteTableRow`).

---

## 4. Partitioning strategy — hash (modulo)

The project uses **hash-style modulo partitioning**, not range or directory routing.

| Strategy | Used here? | Notes |
|----------|------------|--------|
| **Range** | No | Would group contiguous IDs on one shard; risk of skew with time-ordered inserts. |
| **Hash (modulo)** | **Yes** | Deterministic, simple, and matches “three shards” without a directory service. |
| **Directory** | No | Would map keys → shard via a catalog table; more flexible but extra read on every route. |

**Replicated vs partitioned tables** (hybrid within “hash overall”):

- **Partitioned:** `Member`, `WishRequest`, `Listing`, `ListingImage`, `Offer`, `Transaction`, `MessageThread`, `Message`, `Notification`, `Watchlist`, `Report`, `Rating` — each row lives on **exactly one** shard chosen by its PK modulo 3.
- **Replicated (reference):** `Administrator`, `Category` — full copy on **each** shard to support local joins without cross-shard joins for common reads.

**Configuration map:** `tableRoutes` in `Assignment_4/backend/sharding/router.go` (mirrored for tooling in `Assignment_4/implementation/shard_router.py`).

---

## 5. Physical layout — database names

On a **single MySQL host** (local or one port), the repo uses **three databases** as logical shards:

- `<BaseDB>_shard_0`
- `<BaseDB>_shard_1`
- `<BaseDB>_shard_2`

Default local base name in code: **`CampusTradingB`**. On the lab cluster, replace `<BaseDB>` with your **assigned database name** consistently in DDL, DSN, and scripts.

**DDL entry point:** `Assignment_4/sql/create_shards.sql`  
(Creates shard DBs and `CREATE TABLE … LIKE` from the monolithic base schema.)

---

## 6. Data distribution and migration

**Steps:**

1. Ensure the **source** application database exists and is populated (monolithic copy).
2. Run `create_shards.sql` against a connection that can see the source DB (creates shard DBs and empty tables).
3. Run:

   ```bash
   cd Assignment_4
   python scripts/migrate_shards.py \
     --host <HOST> --port <PORT> \
     --user <team_name> --password 'password@123' \
     --source <your_database_name>
   ```

4. Validate with:

   ```bash
   python scripts/verify_shards.py \
     --host <HOST> --port <PORT> \
     --user <team_name> --password 'password@123' \
     --source <your_database_name>
   ```

The migration script applies the **same modulo rule** as the Go router, writes a JSON summary (`scripts/shard_migration_summary.json`), and replicated tables are **inserted on every shard**.

---

## 7. Application routing (Go backend)

### 7.1 Connection model

- **`DB`:** base (central) connection — sessions, roles, audit, and other **central** tables (`Assignment_4/backend/sharding/router.go` → `centralTables`).
- **`Shards[]`:** one `*sql.DB` per shard index — **partitioned** business data and **replicas** of reference tables.

Initialization: `Assignment_4/backend/db/db.go` (`Init`, `openShardConnections`).

### 7.2 Insert routing

- New IDs: `nextRecordID` in `Assignment_4/backend/handlers/shard_helpers.go` scans **`MAX(pk)` across all shards** so the next ID is globally unique, then `record_id % 3` selects the target shard.
- Child rows (e.g. offers, images) use the **parent’s** shard when the domain rule ties them to a listing or other anchored ID (`listingShardDB`, `listingTx`, etc.).

### 7.3 Lookup routing

- **By ID:** handlers resolve `*sql.DB` via `shardDBForTableRow`, `listingShardDB`, `memberShardDB`, … (`shard_helpers.go`) using `sharding.RouteTableRow`.
- **Replicated tables:** routed to **shard 0** for writes/reads that use `PlacementReplicate` (see `replicatedShardDB`).

### 7.4 Range queries and “browse” APIs

When a predicate does not fix a single shard (filters, sorts, listings feed):

- The backend runs the **same SQL** against **`AllShardConnections()`** and **merges** rows in Go (see `fetchListingRowsAcrossShards` in `Assignment_4/backend/handlers/listings.go` and similar patterns in other handlers).

**Implications:**

- **Correctness:** you see the **union** of all shards; deduplication is unnecessary for partitioned PKs if routing is correct.
- **Ordering / limits:** global `ORDER BY` + `LIMIT` may require **fetch-sort-truncate** in application code if not already implemented for every endpoint; fan-out is the required cross-shard primitive.

---

## 8. Debugging on MySQL

To confirm which **server instance** you hit:

```sql
SELECT @@hostname;
```

Compare with shard ports / phpMyAdmin instance you used.

---

## 9. Mapping this repo to three **different MySQL ports** (IITGN)

This repository’s **default** `openShardConnections` builds shard DSNs by changing **only the database name** on the **same** host and port as the base DSN. That matches **three logical databases on one server**.

If the lab gives **one port per shard** (`3307` / `3308` / `3309`), each shard database may live on **its own port**. In that case you should:

- Create `<BaseDB>_shard_0` on port **3307**, `_shard_1` on **3308**, `_shard_2` on **3309** (or follow TA-provided naming), and  
- Extend configuration so **each index in `Shards[]` uses the correct port** (e.g. separate DSNs or env vars per shard), **or** run migration with three connections by varying `--port` per shard in a customized script.

The **routing math** (`% 3`) and **handler fan-out** patterns remain the same; only the **connection factory** changes.

---

## 10. Key files (quick index)

| Path | Purpose |
|------|---------|
| `Assignment_4/backend/sharding/router.go` | Modulo routing, table placement, `RouteTableRow` |
| `Assignment_4/backend/db/db.go` | Pools: base DB + shard DBs |
| `Assignment_4/backend/handlers/shard_helpers.go` | Per-entity shard DB helpers, `nextRecordID`, fan-out primitives |
| `Assignment_4/backend/handlers/listings.go` | Example: cross-shard listing browse |
| `Assignment_4/sql/create_shards.sql` | Shard database + table DDL |
| `Assignment_4/implementation/shard_router.py` | Shared routing for Python tools |
| `Assignment_4/scripts/migrate_shards.py` | Data copy into shards |
| `Assignment_4/scripts/verify_shards.py` | Post-migration checks |
| `Assignment_4/Report.md` | Extended narrative, trade-offs, and citations |

---

## 11. CLI examples (replace placeholders)

**Shard 1:**

```bash
mysql -h 10.0.116.184 -P 3307 -u <team_name> -p'<team_database>'
```

**Shard 2:**

```bash
mysql -h 10.0.116.184 -P 3308 -u <team_name> -p'<team_database>'
```

**Shard 3:**

```bash
mysql -h 10.0.116.184 -P 3309 -u <team_name> -p'<team_database>'
```

Inside the session:

```sql
SHOW DATABASES;
USE `<team_database>`;
SHOW TABLES;
SELECT * FROM `<table_name>` LIMIT 20;
```

---

## 12. Summary

The implementation uses a **modulo-3 hash** on **primary keys** to partition high-volume tables across **three shard databases**, keeps **small reference tables replicated**, keeps **auth/audit/session** on the **central** database, **routes writes and single-row reads** to the owning shard, and handles **global and range-style queries** by **querying every shard and merging** in the application layer—matching the assignment’s functional requirements while staying within course data-isolation rules.
