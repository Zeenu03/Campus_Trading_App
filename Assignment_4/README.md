# Assignment 4 Sharding

This folder contains the Assignment 4 sharding work for the Campus Trading App.

The implementation follows the Task 1 shard layout with three shard endpoints and a modulo routing rule:

`shard_id = record_id % 3`

Use the assigned database name on each shard host. The expected shard endpoints are:

- Shard 1: `10.0.116.184:3307`
- Shard 2: `10.0.116.184:3308`
- Shard 3: `10.0.116.184:3309`

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
- `Report.md` - final written report for the assignment.

## Quick Start

1. Make sure MySQL 8 is running and the assigned database already exists on the shard hosts.
2. Create and activate a Python virtual environment if needed. In this workspace, the scripts were run with the venv:

   - `source .venv/bin/activate`

3. Install the Python dependency used by the migration scripts:

   - `pip install -r requirements.txt`

4. Configure the shard endpoints in [backend/.env.example](backend/.env.example) or your local `.env`.

   ```bash
   export SHARD_0_HOST=10.0.116.184
   export SHARD_0_PORT=3307
   export SHARD_1_HOST=10.0.116.184
   export SHARD_1_PORT=3308
   export SHARD_2_HOST=10.0.116.184
   export SHARD_2_PORT=3309
   ```

5. Seed or prepare the source database with the desired sample data.
6. Initialize the shard schema first if the shard databases are empty.

   ```bash
   python scripts/init_shards.py --host 10.7.27.157 --port 3306 --user root --password root --source CampusTradingB
   ```

7. Run the migration script to copy rows into the three shards.
8. Run the verification script to confirm totals, duplicate checks, and that the central tables stay on Shard 1.
9. Start the backend and frontend to test shard-backed browse and insert flows in the browser.

## Migration and Verification

Run the scripts from this folder:

```bash
python scripts/migrate_shards.py --host 10.0.116.184 --port 3306 --user {user} --password {password} --source {SourceDatabaseName} --shard-hosts 10.0.116.184,10.0.116.184,10.0.116.184 --shard-ports 3307,3308,3309
python scripts/verify_shards.py --host 10.0.116.184 --port 3306 --user {user} --password {password} --source {SourceDatabaseName} --shard-hosts 10.0.116.184,10.0.116.184,10.0.116.184 --shard-ports 3307,3308,3309
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

For local development, the environment files can still point to localhost. For Task 1, update the shard hosts and ports to the provided MySQL endpoints.

- `backend/.env` should use `FRONTEND_URL=http://{IP or localhost}:5173`
- `frontend/.env` should use `VITE_API_URL=http://localhost:8080/api/v1`

## Generated Outputs

- Migration script output: JSON summary written beside `scripts/migrate_shards.py`.
- Verification script output: row counts and duplicate-check results printed to the terminal.
- Backend runtime output: API logs in the terminal.

## Important Files

- [Sharding report](Report.md) - written analysis of the sharding strategy, query routing, and trade-offs.
- [Shard DDL](sql/create_shards.sql) - legacy helper for the local single-server shard simulation.
- [Shard router](implementation/shard_router.py) - central modulo routing logic shared by the migration and verification scripts.
- [Migration script](scripts/migrate_shards.py) - copies rows from the source database into the correct shard hosts and writes a migration summary.
- [Verification script](scripts/verify_shards.py) - checks row counts and duplicate keys after migration.
- [Python dependencies](requirements.txt) - lists the Python package required for MySQL access.
- [Backend handlers](backend/handlers) - shard-aware lookup, insert, and browse logic for the live app.

## Related Deliverables

- `backend/` and `frontend/` are the live application pieces that demonstrate the shard routing in the browser.
- `scripts/` and `implementation/` are the supporting utilities used to move and validate the data.
- `Report.md` is the written analysis for the assignment submission.

## How the Design Is Used

- Partitioned tables use the modulo rule so that rows with the same primary key always go to the same shard.
- `Category` is replicated to every shard, while `Administrator`, `Member`, and the low-usage control tables live only on Shard 1.
- Range and browse queries fan out across shards and merge results in application code.
- Central authentication, member, session, and audit tables live only on Shard 1, while Shard 2 and Shard 3 contain only replicated and partitioned tables.

## Notes

- The assignment now uses the provided shard hosts and can still fall back to a local single-server simulation if you override the shard environment variables.
- The shard schema initializer creates the required tables on the three shard databases before migration.
- The report covers the main trade-offs: scaling, consistency, availability, and partition tolerance.
