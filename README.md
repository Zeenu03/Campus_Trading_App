# Campus Trading App — Module B

A full-stack campus marketplace for IIT Gandhinagar students.

**Stack:** Go (Chi router) · MySQL 8.0 · React (Vite) · Tailwind CSS

---

## Prerequisites

- **MySQL 8.0+** running locally
- **Go 1.21+**
- **Node.js 18+** and npm

---

## 1. Database Setup

### 1a. Run the schema script

```bash
mysql -u root -p < sql/init.sql
```

This creates the `CampusTradingB` database with:
- Core auth tables (`sys_user`, `sys_session`, `sys_role`, `sys_user_role`, `audit_log`)
- All 14 project tables (Member, Listing, Offer, etc.) with CHECK constraints
- Audit triggers (42 triggers — 3 per table) that capture `@session_id`
- Category seed data (15 categories)

### 1b. Create the SuperAdmin account

```bash
cp .env.example .env
# Edit .env to set DB credentials
go run ./backend/cmd/seed
```

Default credentials created:
| Field    | Value                    |
|----------|--------------------------|
| Email    | `superadmin@iitgn.ac.in` |
| Password | `Admin@iitgn2025`        |
| Role     | SuperAdmin               |

> **Important:** Change the password before deploying.

### 1c. Sample member accounts (optional)

Five registered students with **no listings** (same pattern as `/auth/register`):

```bash
cd Assignment2Final/backend
go run ./cmd/seedmembers
```

Emails: `sample.user1@iitgn.ac.in` … `sample.user5@iitgn.ac.in`  
Password (all five): `Sample@iitgn25`  

Re-running skips any email that already exists.

---

## 2. Environment Variables

Copy `.env.example` to `.env` and set:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=CampusTradingB
PORT=8080
FRONTEND_URL=http://localhost:5173
AUDIT_LOG_PATH=./logs/audit.log
```

---

## 3. Running the Application

### Backend

```bash
cd backend
go run .
```

Server starts on `http://localhost:8080`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App opens at `http://localhost:5173`.

---

## 4. API Reference

All endpoints are prefixed with `/api/v1`.

### Auth
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | Public | Login, sets HttpOnly session cookie |
| POST | `/auth/logout` | Any | Revoke session |
| POST | `/auth/register` | Public | Atomic member creation |
| GET | `/auth/me` | Any | Current user info |

### Members
| Method | Path | Auth |
|--------|------|------|
| GET | `/members` | Admin |
| GET | `/members/:id/portfolio` | Own\|Admin |
| PUT | `/members/:id` | Own\|Admin |
| DELETE | `/members/:id` | Admin (soft delete) |

### Listings
| Method | Path | Auth |
|--------|------|------|
| GET | `/listings` | Auth |
| POST | `/listings` | Member |
| GET | `/listings/:id` | Auth |
| PUT | `/listings/:id` | Own\|Admin |
| DELETE | `/listings/:id` | Own\|Admin |

### Offers
| Method | Path | Auth |
|--------|------|------|
| GET | `/listings/:id/offers` | Seller\|Admin |
| POST | `/listings/:id/offers` | Member |
| PUT | `/offers/:id/accept` | Own Seller |
| PUT | `/offers/:id/decline` | Own Seller |
| PUT | `/offers/:id/withdraw` | Own Buyer |

### Transactions / Ratings
| Method | Path | Auth |
|--------|------|------|
| GET | `/transactions` | Auth |
| PUT | `/transactions/:id/confirm` | Own Party |
| POST | `/transactions/:id/rate` | Own Party (Completed only) |

### Other Resources
- `GET/POST /wishrequests` — browse/create (max 5 active)
- `GET/POST /watchlist`, `DELETE /watchlist/:id`
- `GET /notifications`, `PUT /notifications/:id/read`
- `GET/POST /reports`, `PUT /reports/:id/resolve` (admin)

### Admin
| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/audit-log` | Paginated audit entries |
| GET | `/admin/benchmark` | Query timing + EXPLAIN results |
| GET | `/admin/stats` | Dashboard statistics |
| POST | `/admin/users` | Create admin (SuperAdmin only) |

---

## 5. Benchmark Endpoint

The benchmark endpoint runs EXPLAIN on 5 critical queries and times them (3 runs, average):

```bash
# 1. Record baseline (no indexes):
curl -b cookies.txt http://localhost:8080/api/v1/admin/benchmark

# 2. Apply indexes:
mysql -u root -p CampusTradingB < sql/indexes.sql

# 3. Record after-index results:
curl -b cookies.txt http://localhost:8080/api/v1/admin/benchmark
```

Or use the admin UI at `/admin/benchmark` in the React app.

**Queries benchmarked:**
- **Q1** — Listed listings ordered by date (tests `idx_listing_status_expiry`, `idx_listing_created`)
- **Q2** — Listings by seller (tests `idx_listing_seller`)
- **Q3** — Submitted offers for a listing (tests `idx_offer_status`)
- **Q4** — Unread notifications (tests `idx_notif_recipient_read`)
- **Q5** — Average rating for a member (tests `idx_rating_rated`)

Expected improvements after indexing:
| Query | Before | After |
|-------|--------|-------|
| Access type | `ALL` (full scan) | `ref` or `range` |
| Rows examined | N (all rows) | 1–10 |
| Extra | `Using filesort` | `Using index` |

---

## 6. RBAC Summary

| Role | Capabilities |
|------|-------------|
| **admin** | Full CRUD on all tables, view audit log, manage reports, create admin accounts |
| **member** | CRUD own listings/offers/wishreqs/watchlist, read-only on public listings |
| **SuperAdmin** | All admin capabilities + `POST /admin/users` |

---

## 7. Audit Log

Every API write operation is logged in two places:
1. **`audit_log` DB table** — written by `AuditMiddleware` (API-level) and MySQL triggers (DB-level)
2. **`logs/audit.log` file** — appended by `AuditMiddleware`

**Detecting unauthorized direct DB writes:**
- The API middleware sets `SET @session_id = ?` before every write transaction
- MySQL triggers read `@session_id` and insert into `audit_log`
- Direct DB writes (mysql CLI, DBeaver, etc.) never call the API, so `@session_id` is NULL
- In the audit log table: `SELECT * FROM audit_log WHERE session_id IS NULL;`
- In the admin UI (`/admin/audit`): rows with `session_id = NULL` are highlighted **red**

---

## 8. File Structure

```
/
├── backend/
│   ├── main.go              # Chi router, middleware, routes
│   ├── go.mod
│   ├── db/db.go             # MySQL connection pool
│   ├── middleware/
│   │   ├── session.go       # SessionGuard
│   │   ├── role.go          # RoleGuard, AdminOnly, MemberOnly
│   │   ├── owner.go         # IsOwnerOrAdmin helpers
│   │   └── audit.go         # AuditMiddleware + SetSessionVars
│   ├── handlers/
│   │   ├── auth.go          # login, logout, register, me
│   │   ├── members.go       # CRUD + portfolio
│   │   ├── listings.go      # CRUD + browse
│   │   ├── offers.go        # submit, accept, decline, withdraw
│   │   ├── transactions.go  # list, confirm, rate
│   │   ├── wishrequests.go  # browse, create, update
│   │   ├── watchlist.go     # add, remove, list
│   │   ├── notifications.go # list, mark read
│   │   ├── reports.go       # file, list, resolve
│   │   └── admin.go         # audit, benchmark, stats, users
│   ├── models/models.go     # Go structs
│   ├── audit/writer.go      # audit.log file appender
│   └── cmd/seed/main.go     # SuperAdmin creator
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Router + AuthProvider
│   │   ├── context/AuthContext.jsx
│   │   ├── api/client.js    # fetch wrapper
│   │   ├── components/      # Layout, ProtectedRoute, Pagination, etc.
│   │   └── pages/           # All pages + admin/ subdirectory
│   └── vite.config.js
├── sql/
│   ├── init.sql             # Schema + seeds + triggers
│   └── indexes.sql          # Subtask 4 indexes
├── logs/
│   └── audit.log            # Sample audit log
├── .env.example
└── README.md
```
