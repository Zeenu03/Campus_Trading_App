# Campus Trading App — Module B

A full-stack campus marketplace for IIT Gandhinagar students — buy, sell, offer, chat, and rate, all within a verified `@iitgn.ac.in` community.

**Stack:** Go 1.21+ (Chi router) · MySQL 8.0 · React 18 (Vite) · Tailwind CSS  
**All source lives under `Assignment2/ModuleB/`.**

---

## Prerequisites

| Tool           | Minimum version | Purpose                 |
| -------------- | --------------- | ----------------------- |
| Docker Desktop | 24+             | Run MySQL (recommended) |
| Go             | 1.21            | Backend API             |
| Node.js + npm  | 18 / 9          | Frontend                |
| Python         | 3.9             | Benchmark script        |

> A local MySQL 8.0 installation can be used instead of Docker — see [Option B](#option-b-local-mysql) below.

---

## Quick Start (Docker — recommended)

```bash
# Clone and enter the project directory
cd Assignment2/Module_B

# 1. Start MySQL in Docker (auto-loads sql/init.sql)
docker compose up -d

# 2. Wait ~30 s for the first-run schema import, then verify
docker exec campus_trading_mysql mysqladmin ping -h localhost -uroot -proot --silent

# 3. Configure the backend
cp backend/.env.example backend/.env
# Edit backend/.env — DB_PASSWORD=root (matches docker-compose.yml)

# 4. Create the SuperAdmin account
cd backend && go run ./cmd/seed && cd ..

# 5. Start the backend
cd backend && go run . &

# 6. Start the frontend
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173** and log in with `superadmin@iitgn.ac.in` / `Admin@iitgn2025`.

---

## Option B — Local MySQL

```bash
# 1. Run the schema script against your local MySQL instance
mysql -u root -p < Assignment2/ModuleB/sql/init.sql

# 2. Set your credentials in backend/.env
cp Assignment2/ModuleB/backend/.env.example Assignment2/ModuleB/backend/.env
# Edit DB_HOST / DB_USER / DB_PASSWORD as needed

# 3. Seed SuperAdmin, start backend & frontend (same as steps 4–6 above)
```

---

## Environment Variables

All configuration is in `Assignment2/ModuleB/backend/.env`:

```env
# MySQL connection
DB_HOST=localhost       # Use 127.0.0.1 for Docker
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root        # Change for production
DB_NAME=CampusTradingB

# Server
PORT=8080
FRONTEND_URL=http://localhost:5173
AUDIT_LOG_PATH=./logs/audit.log
UPLOADS_DIR=./uploads

# SuperAdmin seed (used by: go run ./cmd/seed)
SUPERADMIN_EMAIL=superadmin@iitgn.ac.in
SUPERADMIN_PASSWORD=Admin@iitgn2025
SUPERADMIN_NAME=Super Administrator
```

> **Important:** Change `DB_PASSWORD` and `SUPERADMIN_PASSWORD` before any public deployment.

---

## Seeding Test Accounts

### SuperAdmin (required)

```bash
cd Assignment2/ModuleB/backend
go run ./cmd/seed
```

| Field    | Value                    |
| -------- | ------------------------ |
| Email    | `superadmin@iitgn.ac.in` |
| Password | `Admin@iitgn2025`        |
| Role     | SuperAdmin               |

### Sample Members (optional)

```bash
cd Assignment2/ModuleB/backend
go run ./cmd/seedmembers
```

Creates five member accounts: `sample.user1@iitgn.ac.in` … `sample.user5@iitgn.ac.in`  
Password (all five): `Sample@iitgn25`  
Re-running is safe — existing emails are skipped.

---

## Running the SQL Index Benchmark

The benchmark script connects directly to MySQL, seeds realistic data, measures 8 queries before and after applying indexes, generates three PNG charts, and writes `report/README.md`.

### 1. Install Python dependencies

```bash
cd Assignment2/ModuleB/scripts
pip install -r requirements.txt
```

`requirements.txt`:

```
mysql-connector-python>=8.0.0
matplotlib>=3.7.0
```

### 2. Run the benchmark

```bash
# From Assignment2/ModuleB/scripts/
python benchmark.py \
  --host 127.0.0.1 \
  --port 3306 \
  --user root \
  --password root \
  --db CampusTradingB
```

**What it does — step by step:**

| Step | Action                                                                                                              |
| ---- | ------------------------------------------------------------------------------------------------------------------- |
| 1    | Connects to MySQL and seeds ~120 members, ~600 listings, ~800 offers, ~3 000 notifications if the tables are sparse |
| 2    | **Phase 1 (Before):** Drops all `idx_%` indexes → runs 8 queries × 10 iterations, captures EXPLAIN                  |
| 3    | Applies all 16 indexes from `sql/indexes.sql`                                                                       |
| 4    | **Phase 2 (After):** Re-runs the same 8 queries × 10 iterations                                                     |
| 5    | Saves three PNG charts to `scripts/charts/`                                                                         |
| 6    | Writes the full analysis to `report/README.md`                                                                      |

### 3. CLI options

| Flag            | Default               | Description                                   |
| --------------- | --------------------- | --------------------------------------------- |
| `--host`        | `127.0.0.1`           | MySQL host                                    |
| `--port`        | `3306`                | MySQL port                                    |
| `--user`        | `root`                | MySQL user                                    |
| `--password`    | `root`                | MySQL password                                |
| `--db`          | `CampusTradingB`      | Database name                                 |
| `--indexes-sql` | `../sql/indexes.sql`  | Path to index definitions                     |
| `--charts-dir`  | `./charts`            | Output directory for PNG files                |
| `--report-out`  | `../report/README.md` | Output path for the report                    |
| `--runs`        | `10`                  | Query iterations per phase                    |
| `--skip-seed`   | off                   | Skip data seeding                             |
| `--skip-drop`   | off                   | Skip dropping existing indexes before Phase 1 |

### 4. Generated outputs

| File                               | Description                                                                  |
| ---------------------------------- | ---------------------------------------------------------------------------- |
| `scripts/charts/timing.png`        | Grouped bar chart — avg ms before vs after per query                         |
| `scripts/charts/rows_examined.png` | Rows examined (EXPLAIN estimate) before vs after                             |
| `scripts/charts/speedup.png`       | Percentage improvement per query                                             |
| `report/README.md`                 | Full benchmark report with EXPLAIN tables, timing stats, and embedded charts |

### 5. Applying indexes manually

To apply or reapply indexes without running the full script:

```bash
# Docker
docker exec -i campus_trading_mysql \
  mysql -uroot -proot CampusTradingB < Assignment2/ModuleB/sql/indexes.sql

# Local MySQL
mysql -u root -p CampusTradingB < Assignment2/ModuleB/sql/indexes.sql
```

To verify indexes were created:

```sql
SELECT TABLE_NAME, INDEX_NAME,
       GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ', ') AS Columns
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = 'CampusTradingB'
  AND INDEX_NAME LIKE 'idx_%'
GROUP BY TABLE_NAME, INDEX_NAME
ORDER BY TABLE_NAME;
```

---

## Benchmark Results (reproduced 2026-03-22)

| Query                        | Endpoint                      | Before avg (ms) | After avg (ms) | Speedup    |
| ---------------------------- | ----------------------------- | --------------- | -------------- | ---------- |
| Q1 — Active listings by date | `GET /listings`               | 0.660           | 0.442          | **+33.0%** |
| Q2 — Listings by seller      | `GET /members/{id}/portfolio` | 0.252           | 0.217          | **+13.6%** |
| Q3 — Submitted offers        | `GET /listings/{id}/offers`   | 0.241           | 0.181          | **+24.9%** |
| Q4 — Unread notifications    | `GET /notifications`          | 0.307           | 0.261          | **+14.9%** |
| Q5 — AVG rating              | Portfolio                     | 0.173           | 0.190          | −9.3%      |
| Q6 — Transaction count       | `GET /transactions`           | 0.287           | 0.201          | **+29.9%** |
| Q7 — Active wish requests    | `GET /wishrequests`           | 0.349           | 0.266          | **+23.8%** |
| Q8 — Audit log by timestamp  | `GET /admin/audit-log`        | 1.379           | 1.600          | −16.0%     |
| **Combined**                 |                               | **3.648 ms**    | **3.358 ms**   | **+7.9%**  |

> Full EXPLAIN plan analysis and charts: [`report/README.md`](report/IndexOptimizationReport.md)  
> Full assignment report (all 5 subtasks): [`report/ASSIGNMENT_REPORT.md`](report/ASSIGNMENT_REPORT.md)

---

## In-App Benchmark UI

Admins can run a live before/after comparison directly in the browser:

1. Log in as an admin and navigate to **Admin → Query Benchmark**
2. Click **"Run Before-Index Benchmark"** to record baseline timings and EXPLAIN plans
3. Apply indexes (see above)
4. Click **"Run After-Index Benchmark"** to see the improvement

The UI shows access type, rows examined, possible keys, key used, and avg execution time for each of the 5 in-app benchmark queries — with colour-coded before/after comparison.

---

## API Reference

All endpoints are prefixed with `/api/v1`.  
Authentication uses an `HttpOnly` session cookie set by `POST /auth/login`.

### Auth

| Method | Path             | Auth    | Description                                               |
| ------ | ---------------- | ------- | --------------------------------------------------------- |
| POST   | `/auth/login`    | Public  | Sets `session_id` cookie; logs `LastLoginDate` for admins |
| POST   | `/auth/register` | Public  | Atomic: creates `sys_user` + `Member` in one transaction  |
| POST   | `/auth/logout`   | Session | Revokes the current session                               |
| GET    | `/auth/me`       | Session | Returns current user info + role                          |

### Members

| Method | Path                      | Auth         | Description                                              |
| ------ | ------------------------- | ------------ | -------------------------------------------------------- |
| GET    | `/members`                | Admin        | Paginated member list with optional name/email search    |
| GET    | `/members/{id}/portfolio` | Session      | Profile, listings, transactions, ratings, watchlist      |
| PUT    | `/members/{id}`           | Own \| Admin | Update profile fields or `is_active` flag                |
| DELETE | `/members/{id}`           | Admin        | Soft-delete: deactivates user, withdraws listings/offers |

### Listings

| Method | Path                              | Auth                                                                                                   |
| ------ | --------------------------------- | ------------------------------------------------------------------------------------------------------ |
| GET    | `/listings`                       | Session — filters: `status`, `q`, `category_id`, `condition`, `min_price`, `max_price`, `sort`, `page` |
| POST   | `/listings`                       | Member                                                                                                 |
| GET    | `/listings/{id}`                  | Session                                                                                                |
| PUT    | `/listings/{id}`                  | Own \| Admin                                                                                           |
| DELETE | `/listings/{id}`                  | Own \| Admin — withdraws listing, auto-declines open offers                                            |
| POST   | `/listings/{id}/images`           | Own \| Admin — multipart upload                                                                        |
| DELETE | `/listings/{id}/images/{imageId}` | Own \| Admin                                                                                           |

### Offers

| Method | Path                        | Auth                                                                        |
| ------ | --------------------------- | --------------------------------------------------------------------------- |
| GET    | `/listings/{id}/my-offer`   | Own Buyer                                                                   |
| GET    | `/listings/{id}/offers`     | Own Seller \| Admin                                                         |
| POST   | `/listings/{id}/offers`     | Member                                                                      |
| PUT    | `/offers/{id}/accept`       | Own Seller — marks listing Sold, declines other offers, creates Transaction |
| PUT    | `/offers/{id}/decline`      | Own Seller                                                                  |
| PUT    | `/offers/{id}/withdraw`     | Own Buyer                                                                   |
| PUT    | `/offers/{id}/price`        | Own Buyer — update offered price                                            |
| PUT    | `/offers/{id}/buyer-accept` | Own Buyer — matches seller asking price                                     |
| PUT    | `/offers/{id}/seller-price` | Own Seller — set per-offer counter price                                    |

### Transactions & Ratings

| Method | Path                      | Auth                                      |
| ------ | ------------------------- | ----------------------------------------- |
| GET    | `/transactions`           | Session — members see own; admins see all |
| POST   | `/transactions/{id}/rate` | Own Party (Accepted transactions only)    |

### Messaging

| Method | Path                          | Auth                |
| ------ | ----------------------------- | ------------------- |
| GET    | `/listings/{id}/my-thread`    | Own Buyer           |
| POST   | `/listings/{id}/threads`      | Member              |
| GET    | `/listings/{id}/interactions` | Own Seller \| Admin |
| GET    | `/threads/{id}/messages`      | Buyer or Seller     |
| POST   | `/threads/{id}/messages`      | Buyer or Seller     |

### Wish Requests / Watchlist / Notifications / Reports

| Method      | Path                             | Auth              |
| ----------- | -------------------------------- | ----------------- |
| GET \| POST | `/wishrequests`                  | Session \| Member |
| PUT         | `/wishrequests/{id}`             | Own               |
| GET \| POST | `/watchlist`                     | Member            |
| DELETE      | `/watchlist/{id}`                | Own               |
| DELETE      | `/watchlist/listing/{listingId}` | Member            |
| GET         | `/notifications`                 | Member            |
| PUT         | `/notifications/{id}/read`       | Own               |
| GET \| POST | `/reports`                       | Admin \| Session  |
| PUT         | `/reports/{id}/resolve`          | Admin             |

### Admin

| Method | Path                  | Description                               |
| ------ | --------------------- | ----------------------------------------- |
| GET    | `/admin/audit-log`    | Paginated audit entries                   |
| GET    | `/admin/benchmark`    | 5 queries: EXPLAIN + timing (3 runs, avg) |
| GET    | `/admin/stats`        | Dashboard counts                          |
| POST   | `/admin/users`        | Create admin account (SuperAdmin only)    |
| GET    | `/admin/members/{id}` | Admin-level member detail                 |

---

## RBAC Summary

| Role           | Key capabilities                                                          |
| -------------- | ------------------------------------------------------------------------- |
| **member**     | CRUD own listings, offers, wish requests, watchlist; read public listings |
| **admin**      | Full CRUD on all tables, view audit log, manage reports, benchmark        |
| **SuperAdmin** | All admin capabilities + `POST /admin/users`                              |

Role membership is stored in `sys_user_role`. `SessionGuard` reads roles on every request and injects them into the request context. `AdminOnly` middleware blocks non-admins at the router level; individual handlers perform resource-ownership checks.

---

## Audit Logging

Every API call is captured in two places by `AuditMiddleware`:

1. **`audit_log` DB table** — queryable, tied to the authenticated session
2. **`logs/audit.log` file** — append-only flat file for tamper evidence

The middleware sets MySQL session variables `@session_id` and `@current_user_id` before every write transaction. The 42 DB-level audit triggers (3 per table) read these variables when recording changes. A direct DB write (via `mysql` CLI or any DB client) never passes through the API, so `@session_id` is `NULL` — making unauthorised modifications immediately identifiable:

```sql
-- Find all direct DB writes (no API session)
SELECT * FROM audit_log WHERE session_id IS NULL;
```

In the admin UI (`/admin/audit`), these rows are highlighted red.

---

## File Structure

```
Assignment2/ModuleB/
├── backend/
│   ├── main.go                  # Chi router, CORS, middleware chain, routes
│   ├── go.mod / go.sum
│   ├── .env.example             # Copy to .env and fill in values
│   ├── db/db.go                 # MySQL connection pool (env-based config)
│   ├── middleware/
│   │   ├── session.go           # SessionGuard — validates cookie, injects context
│   │   ├── role.go              # RoleGuard, AdminOnly, MemberOnly, AnyAuth
│   │   ├── owner.go             # IsOwnerOrAdmin helpers
│   │   └── audit.go             # AuditMiddleware + SetSessionVars
│   ├── handlers/
│   │   ├── auth.go              # login, logout, register, me
│   │   ├── members.go           # CRUD + portfolio
│   │   ├── listings.go          # CRUD + browse + images
│   │   ├── offers.go            # submit, accept, decline, withdraw, counter
│   │   ├── transactions.go      # list, rate
│   │   ├── threads.go           # create thread, list interactions, messages
│   │   ├── wishrequests.go      # browse, create, cancel, update
│   │   ├── watchlist.go         # add, remove, list
│   │   ├── notifications.go     # list, mark read
│   │   ├── reports.go           # file, list, resolve
│   │   ├── categories.go        # list active categories
│   │   └── admin.go             # audit log, benchmark, stats, create admin
│   ├── models/models.go         # Go structs + JSON tags
│   ├── audit/writer.go          # audit.log file appender
│   └── cmd/
│       ├── seed/main.go         # Creates SuperAdmin account
│       └── seedmembers/main.go  # Creates 5 sample member accounts
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Router + AuthProvider
│   │   ├── api/client.js        # fetch wrapper (cookie-based auth)
│   │   ├── context/AuthContext.jsx
│   │   ├── components/          # Layout, ProtectedRoute, Pagination, ChatPanel, etc.
│   │   └── pages/
│   │       ├── Listings.jsx     # Browse + filter
│   │       ├── ListingDetail.jsx # Detail + offer + chat
│   │       ├── Portfolio.jsx    # Member profile
│   │       └── admin/
│   │           ├── Benchmark.jsx # Before/after benchmark UI
│   │           ├── Audit.jsx
│   │           ├── Members.jsx
│   │           └── Reports.jsx
│   └── vite.config.js
├── sql/
│   ├── init.sql                 # Schema, triggers, seed categories
│   └── indexes.sql              # 16 performance indexes (SubTask 4)
├── scripts/
│   ├── benchmark.py             # End-to-end benchmark + report generator
│   ├── requirements.txt         # mysql-connector-python, matplotlib
│   └── charts/                  # Generated PNG charts (after running benchmark.py)
│       ├── timing.png
│       ├── rows_examined.png
│       └── speedup.png
├── report/
│   ├── README.md                # Auto-generated benchmark report (benchmark.py output)
│   └── ASSIGNMENT_REPORT.md     # Full assignment report (SubTasks 1–5)
├── logs/
│   └── audit.log                # Sample / live audit log
├── docker-compose.yml           # MySQL 8.0 container with init.sql auto-load
└── README.md                    # This file
```
