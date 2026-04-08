# Assignment 4 Sharding

This folder contains the Assignment 4 sharding deliverable for the Campus Trading App.

The design uses three simulated shards and a modulo routing rule:

`shard_id = record_id % 3`

The source database is `CampusTradingB` and the shard databases are:

- `CampusTradingB_shard_0`
- `CampusTradingB_shard_1`
- `CampusTradingB_shard_2`

## Prerequisites

- MySQL 8.0
- Python 3.10+
- Go 1.21+
- Node.js 18+
- npm

## Folder Map

- `backend/` - Go API with shard-aware handlers and routing.
- `frontend/` - React/Vite UI used to test browse, lookup, and insert flows.
- `implementation/` - shared Python shard router used by the migration and verification scripts.
- `scripts/` - migration and verification utilities for the shard databases.
- `sql/` - SQL used to create the shard schema.
- `Report.pdf` - final written report for the assignment.

## Quick Start

1. Make sure MySQL 8 is running and the original `CampusTradingB` database already exists.
2. Create and activate a Python virtual environment if needed. In this workspace, the scripts were run with the venv:

   - `source .venv/bin/activate`

3. Install the Python dependency used by the migration scripts:

   - `pip install -r requirements.txt`

4. Create the three shard databases and shard tables by running [sql/create_shards.sql](sql/create_shards.sql) on the MySQL server.

   ```bash
   cd Assignment_4
   mysql -h {IP or localhost} -P 3306 -u root -p CampusTradingB < sql/create_shards.sql
   ```

   To verify that the shard databases were created, you can run:

   ```bash
   mysql -h {IP or localhost} -P 3306 -u root -p -e "SHOW DATABASES LIKE 'CampusTradingB_shard_%';"
   ```

5. Seed or prepare the source database with the desired sample data.
6. Run the migration script to copy rows into the three shards.
7. Run the verification script to confirm totals and duplicate checks.
8. Start the backend and frontend to test shard-backed browse and insert flows in the browser.

## Migration and Verification

Run the scripts from this folder:

```bash
python scripts/migrate_shards.py --host {IP} --port {PORT} --user {user} --password {password} --source {SourceDatabaseName}
python scripts/verify_shards.py --host {IP} --port {PORT} --user {user} --password {password} --source {SourceDatabaseName}
```

The migration script writes a JSON summary beside the script after copying the data.
If your MySQL server uses different credentials or a different host, pass those values on the command line.

## Local App Demo

Use this section if you want the full local run instead of only the migration tools.

Backend:

```bash
cd backend
go run .
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

For local development, the environment files should point to localhost:

- `backend/.env` should use `FRONTEND_URL=http://{IP or localhost}:5173`
- `frontend/.env` should use `VITE_API_URL=http://localhost:8080/api/v1`


## Generated Outputs

- Migration script output: JSON summary written beside `scripts/migrate_shards.py`.
- Verification script output: row counts and duplicate-check results printed to the terminal.
- Backend runtime output: API logs in the terminal.

## Important Files

- [Sharding report](Report.pdf) - written analysis of the sharding strategy, query routing, and trade-offs.
- [Shard DDL](sql/create_shards.sql) - creates the three shard databases and the table layout used for the simulation.
- [Shard router](implementation/shard_router.py) - central modulo routing logic shared by the migration and verification scripts.
- [Migration script](scripts/migrate_shards.py) - copies rows from `CampusTradingB` into the correct shard and writes a migration summary.
- [Verification script](scripts/verify_shards.py) - checks row counts and duplicate keys after migration.
- [Python dependencies](requirements.txt) - lists the Python package required for MySQL access.
- [Backend handlers](backend/handlers) - shard-aware lookup, insert, and browse logic for the live app.

## Related Deliverables

- `backend/` and `frontend/` are the live application pieces that demonstrate the shard routing in the browser.
- `scripts/` and `implementation/` are the supporting utilities used to move and validate the data.
- `Report.pdf` is the written analysis for the assignment submission.

## How the Design Is Used

- Partitioned tables use the modulo rule so that rows with the same primary key always go to the same shard.
- Reference tables such as `Category` and `Administrator` are replicated to every shard.
- Range and browse queries fan out across shards and merge results in application code.
- Central authentication, session, and audit tables remain on the base database, while shard-owned business data is routed to the shard databases.

## Notes

- The assignment is intentionally implemented as database-per-shard simulation, which satisfies the “multiple databases on the same server” option.
- The report documents the main trade-offs: scaling, consistency, availability, and partition tolerance.
