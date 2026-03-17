# Module B — Campus Trading Application

**CS432 Databases | Team 8 | IITGN | March 2026**

A complete Flask web application with RESTful APIs, JWT authentication, RBAC, audit logging, and MySQL query optimization.

---

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — set DB_PASSWORD to your MySQL root password

# 3. Create the database (if it doesn't exist yet)
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS CampusTrading CHARACTER SET utf8mb4;"

# 4. Run the SINGLE master setup script (handles correct table order)
mysql -u root -p < sql/00_setup_all.sql

# 5. Generate real bcrypt password hashes
python3 generate_hashes.py

# 6. Apply performance indexes
mysql -u root -p CampusTrading < sql/03_create_indexes.sql

# 7. Run the app
python3 run.py
# → http://localhost:5000
```

**Default login credentials (after step 5):**
| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin |
| amal.perera | password123 | RegularUser |
| nimali.fernando | password123 | RegularUser |

> ⚠️ **Why one script?** `User` has foreign keys to `Member` and `Administrator`.
> Running `01_create_auth_tables.sql` alone fails because those tables don't exist yet.
> `00_setup_all.sql` creates everything in the correct dependency order.

---

## Project Structure

```
Module_B/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Config classes (Dev/Test/Prod)
│   ├── models/              # SQLAlchemy models (14 tables)
│   │   ├── user.py          # User, Session, AuditLog
│   │   ├── member.py        # Member
│   │   ├── admin.py         # Administrator, Category
│   │   ├── listing.py       # Listing, ListingImage
│   │   ├── trading.py       # Offer, Transaction, Rating
│   │   └── communication.py # Message, Notification, Report, etc.
│   ├── routes/
│   │   ├── auth.py          # /api/login, /api/logout, /api/isAuth, /api/register
│   │   ├── members.py       # /api/members CRUD
│   │   ├── listings.py      # /api/listings CRUD + /api/categories
│   │   ├── offers.py        # /api/offers CRUD + accept/decline/withdraw
│   │   ├── transactions.py  # /api/transactions + confirm/cancel/rate
│   │   ├── portfolio.py     # /api/members/<id>/portfolio
│   │   ├── admin.py         # /api/admin/* (admin-only)
│   │   └── views.py         # Web UI HTML pages
│   ├── middleware/
│   │   ├── auth.py          # @require_auth decorator
│   │   └── rbac.py          # @require_admin, @require_ownership
│   ├── services/
│   │   ├── auth_service.py  # bcrypt + JWT
│   │   └── audit_service.py # Dual-channel logging
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS + JS
├── sql/
│   ├── 01_create_auth_tables.sql  # User, Session, AuditLog tables + triggers
│   ├── 02_campus_trading.sql      # 14 domain tables
│   ├── 03_create_indexes.sql      # 45+ performance indexes
│   ├── 04_seed_data.sql           # Sample data for testing
│   └── 05_drop_indexes.sql        # For benchmarking (before phase)
├── benchmarks/
│   ├── run_benchmark.py           # Automated benchmark script
│   ├── benchmark_results.json     # Results (generated after running)
│   └── explain_outputs/           # EXPLAIN analysis per query
├── tests/
│   ├── test_auth.py
│   ├── test_rbac.py
│   └── test_api.py
├── logs/                    # audit.log (generated at runtime)
├── report.docx              # Optimization report document
├── requirements.txt
├── .env.example
└── run.py                   # Application entry point
```

---

## API Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/login` | POST | ❌ | Authenticate user |
| `/api/logout` | POST | ✅ | Revoke session |
| `/api/isAuth` | GET | ✅ | Check session validity |
| `/api/register` | POST | ❌ | Register new user |
| `/api/members` | GET/POST | ✅ | List / create members |
| `/api/members/<id>` | GET/PUT/DELETE | ✅ | Get / update / delete member |
| `/api/members/<id>/portfolio` | GET | ✅ | View member portfolio |
| `/api/listings` | GET/POST | ✅ | Browse / create listings |
| `/api/listings/<id>` | GET/PUT/DELETE | ✅ | Get / update / delete listing |
| `/api/offers` | GET/POST | ✅ | List / make offers |
| `/api/offers/<id>/accept` | PUT | ✅ | Accept offer (seller) |
| `/api/offers/<id>/decline` | PUT | ✅ | Decline offer (seller) |
| `/api/offers/<id>/withdraw` | PUT | ✅ | Withdraw offer (buyer) |
| `/api/transactions` | GET | ✅ | View transactions |
| `/api/transactions/<id>/confirm` | PUT | ✅ | Confirm transaction |
| `/api/transactions/<id>/rate` | POST | ✅ | Rate after completion |
| `/api/categories` | GET | ✅ | List categories |
| `/api/admin/stats` | GET | 🔑 Admin | Platform stats |
| `/api/admin/users` | GET/PUT/DELETE | 🔑 Admin | Manage users |
| `/api/admin/reports` | GET/PUT | 🔑 Admin | Manage reports |
| `/api/admin/audit-logs` | GET | 🔑 Admin | View audit trail |

---

## Running Benchmarks

```bash
python3 benchmarks/run_benchmark.py
```

This will:
1. Drop all indexes (`05_drop_indexes.sql`)
2. Run 8 test queries × 10 iterations each → record times
3. Apply indexes (`03_create_indexes.sql`)
4. Run same queries again → compare
5. Save `benchmarks/benchmark_results.json`
6. Save `benchmarks/explain_outputs/` EXPLAIN analysis
7. Generate `benchmarks/benchmark_comparison.png` and `speedup_chart.png`

---

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_rbac.py -v
python -m pytest tests/test_api.py -v
```

---

## Web UI Pages

| URL | Page |
|-----|------|
| `/login` | Sign-in page |
| `/dashboard` | Home with stats & recent listings |
| `/listings` | Browse all listings with filters |
| `/listings/<id>` | Listing detail + make offer |
| `/listings/create` | Post a new listing |
| `/members` | Member directory |
| `/members/<id>/portfolio` | Member profile & stats |
| `/admin` | Admin panel (users, reports, audit log) |

---

## Phase Completion

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Foundation | ✅ Complete | Project structure, config, SQL |
| Phase 2: Models | ✅ Complete | All 14+ SQLAlchemy models |
| Phase 3: Auth | ✅ Complete | JWT + bcrypt + session tracking |
| Phase 4: RBAC | ✅ Complete | Decorators + audit logging |
| Phase 5: API Routes | ✅ Complete | Members, Listings, Offers, Transactions, Admin |
| Phase 6: Web UI | ✅ Complete | Bootstrap 5 templates for all pages |
| Phase 7: Benchmarks | ✅ Complete | Benchmark script + EXPLAIN analysis |
| Phase 8: Report | ✅ Complete | report.docx with full documentation |

---

## Correct SQL execution order (if running individually)

```
01  ← WRONG to run alone — it references Member/Administrator
```

**Always use `00_full_setup.sql` or follow this order:**

```bash
# Step 1: Core domain tables first (Member, Listing, etc.)
mysql -u root -p CampusTrading < sql/02_campus_trading.sql

# Step 2: Auth tables (User/Session FK → Member/Administrator)
mysql -u root -p CampusTrading < sql/01_create_auth_tables.sql

# Step 3: Indexes
mysql -u root -p CampusTrading < sql/03_create_indexes.sql

# Step 4: Seed data
mysql -u root -p CampusTrading < sql/04_seed_data.sql
```

> `01_create_auth_tables.sql` was updated to add the `User→Member` and `User→Administrator`
> foreign keys via `ALTER TABLE` at the **end** of the file, so it is safe to run after `02_campus_trading.sql`.
