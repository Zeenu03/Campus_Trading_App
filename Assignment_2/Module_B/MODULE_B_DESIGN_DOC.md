# Module B: Local API Development, RBAC, and Database Optimization

## Campus Trading Application - Design Document

**Team 8** | CS 432 Databases | March 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [Tech Stack Selection](#2-tech-stack-selection)
3. [Project Structure](#3-project-structure)
4. [Database Design](#4-database-design)
5. [Authentication & Session Management](#5-authentication--session-management)
6. [Role-Based Access Control (RBAC)](#6-role-based-access-control-rbac)
7. [API Design](#7-api-design)
8. [Web UI Design](#8-web-ui-design)
9. [Security & Logging](#9-security--logging)
10. [SQL Indexing Strategy](#10-sql-indexing-strategy)
11. [Performance Benchmarking Plan](#11-performance-benchmarking-plan)
12. [Implementation Timeline](#12-implementation-timeline)

---

## 1. Overview

### 1.1 Objectives

Module B requires building a complete web application with:

| Requirement | Description | Marks |
|-------------|-------------|-------|
| Local DB & Secure API | Core/Project setup, CRUD APIs, Session Validation, Member Portfolio | 20 |
| Security & RBAC | Role enforcement, deletion integrity, unauthorized access logging | 10 |
| Database Optimization | Logical indexing strategy, query profiling | 10 |
| Optimization Report | Benchmarking graphs, EXPLAIN analysis, documentation | 10 |
| Video Demonstration | Clear narration of UI/API, RBAC, logging | 10 |
| **Total** | | **60** |

### 1.2 Key Features

1. **Web UI** - User-friendly interface for Campus Trading operations
2. **RESTful APIs** - CRUD operations on all 14 tables
3. **Authentication** - JWT-based session management
4. **RBAC** - Admin vs Regular User access control
5. **Audit Logging** - Track all database modifications
6. **SQL Indexing** - Optimize query performance
7. **Benchmarking** - Measure before/after performance

---

## 2. Tech Stack Selection

### 2.1 Recommended Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Backend** | Python + Flask | Simple, well-documented, good for prototyping |
| **Database** | MySQL 8.0 | Already using for Assignment 1, supports CHECK constraints |
| **ORM** | SQLAlchemy | Powerful, supports raw SQL for EXPLAIN |
| **Authentication** | JWT (PyJWT) | Stateless, secure, easy to implement |
| **Frontend** | HTML + Bootstrap 5 + Jinja2 | Simple, responsive, no JS framework needed |
| **Password Hashing** | bcrypt | Industry standard, secure |
| **Logging** | Python logging + file handler | Built-in, easy audit trail |

### 2.2 Alternative Stacks

**Option B: Node.js Stack**
- Backend: Express.js
- ORM: Sequelize or Knex.js
- Auth: jsonwebtoken
- Frontend: EJS templates + Bootstrap

**Option C: Full-Stack Python**
- Backend: FastAPI (async, automatic docs)
- ORM: SQLAlchemy
- Auth: python-jose
- Frontend: Jinja2 + HTMX

### 2.3 Dependencies

```txt
# requirements.txt for Module B
flask>=3.0.0
flask-sqlalchemy>=3.1.0
flask-cors>=4.0.0
pymysql>=1.1.0
pyjwt>=2.8.0
bcrypt>=4.1.0
python-dotenv>=1.0.0
pandas>=2.0.0
matplotlib>=3.7.0
```

---

## 3. Project Structure

```
Module_B/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration settings
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py              # User, Login, UserGroup models
│   │   ├── member.py            # Member model
│   │   ├── listing.py           # Listing, ListingImage models
│   │   ├── trading.py           # Offer, Transaction, Rating models
│   │   ├── communication.py     # MessageThread, Message, Notification
│   │   └── admin.py             # Administrator, Report, Category models
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py              # /login, /logout, /isAuth
│   │   ├── members.py           # /members CRUD
│   │   ├── listings.py          # /listings CRUD
│   │   ├── offers.py            # /offers CRUD
│   │   ├── transactions.py      # /transactions CRUD
│   │   ├── admin.py             # Admin-only routes
│   │   └── portfolio.py         # Member portfolio view
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py              # JWT verification decorator
│   │   ├── rbac.py              # Role checking decorator
│   │   └── logger.py            # Audit logging middleware
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py      # Authentication logic
│   │   └── audit_service.py     # Logging service
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── listings/
│   │   ├── members/
│   │   └── portfolio.html
│   └── static/                  # CSS, JS, images
│       ├── css/
│       └── js/
├── sql/
│   ├── 01_create_auth_tables.sql    # User, Login, UserGroup tables
│   ├── 02_campus_trading.sql        # Original 14 tables
│   ├── 03_create_indexes.sql        # Index definitions
│   ├── 04_seed_data.sql             # Sample data
│   └── 05_drop_indexes.sql          # For benchmarking
├── logs/
│   └── audit.log                # API audit trail
├── benchmarks/
│   ├── benchmark_results.json
│   └── explain_outputs/
├── tests/
│   ├── test_auth.py
│   ├── test_rbac.py
│   └── test_api.py
├── report.pdf                   # Or report.ipynb
├── requirements.txt
├── .env.example
├── run.py                       # Application entry point
└── README.md
```

---

## 4. Database Design

### 4.1 Core System Tables (New)

These tables manage authentication and authorization separately from project data.

#### 4.1.1 User Table (Core Authentication)

```sql
CREATE TABLE User (
    UserID          INT             AUTO_INCREMENT PRIMARY KEY,
    Username        VARCHAR(50)     NOT NULL UNIQUE,
    Email           VARCHAR(150)    NOT NULL UNIQUE,
    PasswordHash    VARCHAR(256)    NOT NULL,
    Role            ENUM('Admin', 'RegularUser') NOT NULL DEFAULT 'RegularUser',
    IsActive        BOOLEAN         NOT NULL DEFAULT TRUE,
    CreatedAt       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt       DATETIME        NULL ON UPDATE CURRENT_TIMESTAMP,

    -- Link to Member/Administrator (nullable - user may not have profile yet)
    MemberID        INT             NULL,
    AdminID         INT             NULL,

    CONSTRAINT FK_User_Member FOREIGN KEY (MemberID)
        REFERENCES Member(MemberID) ON DELETE SET NULL,
    CONSTRAINT FK_User_Admin FOREIGN KEY (AdminID)
        REFERENCES Administrator(AdminID) ON DELETE SET NULL,
    CONSTRAINT CHK_User_Role_Link CHECK (
        (Role = 'Admin' AND AdminID IS NOT NULL) OR
        (Role = 'RegularUser') OR
        (MemberID IS NULL AND AdminID IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.1.2 Session Table (JWT Tracking)

```sql
CREATE TABLE Session (
    SessionID       INT             AUTO_INCREMENT PRIMARY KEY,
    UserID          INT             NOT NULL,
    Token           VARCHAR(512)    NOT NULL,
    IssuedAt        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ExpiresAt       DATETIME        NOT NULL,
    IsRevoked       BOOLEAN         NOT NULL DEFAULT FALSE,
    IPAddress       VARCHAR(45)     NULL,
    UserAgent       VARCHAR(256)    NULL,

    CONSTRAINT FK_Session_User FOREIGN KEY (UserID)
        REFERENCES User(UserID) ON DELETE CASCADE,

    INDEX IDX_Session_Token (Token(255)),
    INDEX IDX_Session_UserID (UserID),
    INDEX IDX_Session_ExpiresAt (ExpiresAt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.1.3 UserGroup Table (For Future RBAC Extension)

```sql
CREATE TABLE UserGroup (
    GroupID         INT             AUTO_INCREMENT PRIMARY KEY,
    GroupName       VARCHAR(50)     NOT NULL UNIQUE,
    Description     VARCHAR(256)    NULL,
    Permissions     JSON            NULL,  -- Store permissions as JSON
    CreatedAt       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE UserGroupMapping (
    MappingID       INT             AUTO_INCREMENT PRIMARY KEY,
    UserID          INT             NOT NULL,
    GroupID         INT             NOT NULL,
    AssignedAt      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    AssignedBy      INT             NULL,

    CONSTRAINT FK_UGM_User FOREIGN KEY (UserID)
        REFERENCES User(UserID) ON DELETE CASCADE,
    CONSTRAINT FK_UGM_Group FOREIGN KEY (GroupID)
        REFERENCES UserGroup(GroupID) ON DELETE CASCADE,
    CONSTRAINT FK_UGM_AssignedBy FOREIGN KEY (AssignedBy)
        REFERENCES User(UserID) ON DELETE SET NULL,

    CONSTRAINT UQ_UserGroup UNIQUE (UserID, GroupID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.1.4 AuditLog Table

```sql
CREATE TABLE AuditLog (
    LogID           INT             AUTO_INCREMENT PRIMARY KEY,
    Timestamp       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UserID          INT             NULL,
    Username        VARCHAR(50)     NULL,
    Action          VARCHAR(20)     NOT NULL,  -- CREATE, READ, UPDATE, DELETE
    TableName       VARCHAR(50)     NOT NULL,
    RecordID        INT             NULL,
    OldValues       JSON            NULL,
    NewValues       JSON            NULL,
    IPAddress       VARCHAR(45)     NULL,
    UserAgent       VARCHAR(256)    NULL,
    APIEndpoint     VARCHAR(200)    NULL,
    ResponseStatus  INT             NULL,
    IsAuthorized    BOOLEAN         NOT NULL DEFAULT TRUE,

    INDEX IDX_AuditLog_Timestamp (Timestamp),
    INDEX IDX_AuditLog_UserID (UserID),
    INDEX IDX_AuditLog_TableName (TableName),
    INDEX IDX_AuditLog_Action (Action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 4.2 Existing Tables (From Assignment 1)

The 14 tables from Assignment 1 remain unchanged:

| # | Table | Purpose |
|---|-------|---------|
| 1 | Member | Campus Trading users |
| 2 | Administrator | Platform admins |
| 3 | Category | Product categories |
| 4 | WishRequest | Item requests |
| 5 | Listing | Items for sale |
| 6 | ListingImage | Listing photos |
| 7 | Offer | Price negotiations |
| 8 | Transaction | Completed trades |
| 9 | Rating | User reviews |
| 10 | Watchlist | Saved items |
| 11 | Report | Flagged content |
| 12 | Notification | User alerts |
| 13 | MessageThread | Conversations |
| 14 | Message | Individual messages |

### 4.3 Entity Relationship Diagram

```
                    ┌─────────────┐
                    │    User     │
                    │  (Auth)     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌─────────┐  ┌──────────┐  ┌─────────┐
        │ Session │  │  Member  │  │  Admin  │
        └─────────┘  └────┬─────┘  └─────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
   ┌─────────┐      ┌──────────┐      ┌──────────┐
   │ Listing │◄────►│   Offer  │◄────►│Transaction│
   └────┬────┘      └──────────┘      └─────┬────┘
        │                                   │
        ▼                                   ▼
   ┌──────────┐                        ┌─────────┐
   │ListingImg│                        │ Rating  │
   └──────────┘                        └─────────┘
```

---

## 5. Authentication & Session Management

### 5.1 Authentication Flow

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│  Client  │      │   API    │      │  Auth    │      │ Database │
│  (UI)    │      │  Server  │      │ Service  │      │          │
└────┬─────┘      └────┬─────┘      └────┬─────┘      └────┬─────┘
     │                 │                 │                 │
     │  POST /login    │                 │                 │
     │ {user, pass}    │                 │                 │
     │────────────────►│                 │                 │
     │                 │  validate()     │                 │
     │                 │────────────────►│                 │
     │                 │                 │  SELECT User    │
     │                 │                 │────────────────►│
     │                 │                 │◄────────────────│
     │                 │                 │                 │
     │                 │                 │ verify password │
     │                 │                 │ generate JWT    │
     │                 │◄────────────────│                 │
     │                 │                 │  INSERT Session │
     │                 │                 │────────────────►│
     │                 │                 │                 │
     │  200 + JWT      │                 │                 │
     │◄────────────────│                 │                 │
     │                 │                 │                 │
```

### 5.2 JWT Token Structure

```python
# JWT Payload
{
    "sub": user_id,           # Subject (User ID)
    "username": "john_doe",
    "email": "john@iitgn.ac.in",
    "role": "RegularUser",    # Admin or RegularUser
    "member_id": 5,           # Optional: linked Member ID
    "iat": 1709312400,        # Issued At
    "exp": 1709398800,        # Expires (24 hours)
    "jti": "unique-token-id"  # JWT ID for revocation
}
```

### 5.3 Session Validation

```python
# Middleware: auth.py
from functools import wraps
from flask import request, jsonify
import jwt

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Get token from header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'error': 'No session found'}), 401

        try:
            # Decode and verify token
            payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])

            # Check if session is revoked
            session = Session.query.filter_by(
                token=token,
                is_revoked=False
            ).first()

            if not session:
                return jsonify({'error': 'Session expired'}), 401

            # Add user info to request context
            request.current_user = payload

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Session expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid session token'}), 401

        return f(*args, **kwargs)

    return decorated
```

### 5.4 API Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/login` | POST | Authenticate user | No |
| `/api/logout` | POST | Revoke session | Yes |
| `/api/isAuth` | GET | Verify session | Yes |
| `/api/register` | POST | Create new user | No |
| `/api/refresh` | POST | Refresh token | Yes |

---

## 6. Role-Based Access Control (RBAC)

### 6.1 Role Definitions

| Role | Description | Permissions |
|------|-------------|-------------|
| **Admin** | Platform administrators | Full CRUD on all tables, user management, report resolution |
| **RegularUser** | Campus Trading members | Read all, CRUD on own listings/offers/messages |

### 6.2 Permission Matrix

| Resource | Admin | RegularUser (Own) | RegularUser (Others) |
|----------|-------|-------------------|----------------------|
| **Members** | CRUD | RU (profile) | R (public info) |
| **Listings** | CRUD | CRUD | R |
| **Offers** | CRUD | CRUD | R (on own listings) |
| **Transactions** | CRUD | R | - |
| **Messages** | CRUD | CRUD | - |
| **Reports** | CRUD | C | - |
| **Categories** | CRUD | R | R |
| **Users** | CRUD | RU (self) | - |

### 6.3 RBAC Middleware

```python
# Middleware: rbac.py
from functools import wraps
from flask import request, jsonify

def require_role(*allowed_roles):
    """Decorator to check if user has required role."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = request.current_user

            if user.get('role') not in allowed_roles:
                # Log unauthorized access attempt
                audit_log(
                    user_id=user.get('sub'),
                    action='ACCESS_DENIED',
                    endpoint=request.path,
                    is_authorized=False
                )
                return jsonify({'error': 'Insufficient permissions'}), 403

            return f(*args, **kwargs)
        return decorated
    return decorator

def require_ownership_or_admin(resource_type):
    """Check if user owns the resource or is admin."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = request.current_user
            resource_id = kwargs.get('id')

            # Admins can access anything
            if user.get('role') == 'Admin':
                return f(*args, **kwargs)

            # Check ownership
            if resource_type == 'listing':
                listing = Listing.query.get(resource_id)
                if listing and listing.seller_id == user.get('member_id'):
                    return f(*args, **kwargs)

            elif resource_type == 'member':
                if resource_id == user.get('member_id'):
                    return f(*args, **kwargs)

            return jsonify({'error': 'Access denied'}), 403

        return decorated
    return decorator
```

### 6.4 Usage Example

```python
# routes/listings.py
from app.middleware.auth import require_auth
from app.middleware.rbac import require_role, require_ownership_or_admin

@app.route('/api/listings', methods=['GET'])
@require_auth
def get_listings():
    """Anyone authenticated can view listings."""
    listings = Listing.query.filter_by(status='Listed').all()
    return jsonify([l.to_dict() for l in listings])

@app.route('/api/listings', methods=['POST'])
@require_auth
def create_listing():
    """Any authenticated user can create a listing."""
    # ... create listing with seller_id = current_user.member_id
    pass

@app.route('/api/listings/<int:id>', methods=['PUT'])
@require_auth
@require_ownership_or_admin('listing')
def update_listing(id):
    """Only owner or admin can update."""
    pass

@app.route('/api/listings/<int:id>', methods=['DELETE'])
@require_auth
@require_role('Admin')
def delete_listing(id):
    """Only admin can delete listings."""
    pass
```

---

## 7. API Design

### 7.1 RESTful Endpoints Overview

| Resource | GET | POST | PUT | DELETE |
|----------|-----|------|-----|--------|
| `/api/members` | List all | Create | - | - |
| `/api/members/{id}` | Get one | - | Update | Delete |
| `/api/members/{id}/portfolio` | View portfolio | - | - | - |
| `/api/listings` | List all | Create | - | - |
| `/api/listings/{id}` | Get one | - | Update | Delete |
| `/api/offers` | List (filtered) | Create | - | - |
| `/api/offers/{id}` | Get one | - | Update | Delete |
| `/api/transactions` | List | Create | - | - |
| `/api/transactions/{id}` | Get one | - | Update | - |
| `/api/categories` | List all | Create | - | - |
| `/api/reports` | List (admin) | Create | - | - |
| `/api/reports/{id}` | Get one | - | Resolve | - |

### 7.2 Request/Response Examples

#### Login

```http
POST /api/login
Content-Type: application/json

{
    "user": "john_doe",
    "password": "securepassword123"
}
```

**Success Response (200):**
```json
{
    "message": "Login successful",
    "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
        "id": 1,
        "username": "john_doe",
        "role": "RegularUser",
        "member_id": 5
    }
}
```

**Error Response (401):**
```json
{
    "error": "Invalid credentials"
}
```

#### isAuth

```http
GET /api/isAuth
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Success Response (200):**
```json
{
    "message": "User is authenticated",
    "username": "john_doe",
    "role": "RegularUser",
    "expiry": "2026-03-14T12:00:00Z"
}
```

#### Create Listing

```http
POST /api/listings
Authorization: Bearer <token>
Content-Type: application/json

{
    "category_id": 6,
    "title": "Engineering Mechanics by Meriam",
    "description": "8th edition, good condition",
    "asking_price": 35.00,
    "is_negotiable": true,
    "condition": "Good",
    "course_code": "ME-201"
}
```

**Success Response (201):**
```json
{
    "message": "Listing created",
    "listing": {
        "id": 21,
        "title": "Engineering Mechanics by Meriam",
        "status": "Listed",
        "created_date": "2026-03-13T10:30:00Z"
    }
}
```

#### Member Portfolio

```http
GET /api/members/5/portfolio
Authorization: Bearer <token>
```

**Response (200):**
```json
{
    "member": {
        "id": 5,
        "name": "Ravindu Bandara",
        "department": "Mechanical Engineering",
        "year_of_study": 3,
        "hostel": "Hostel A",
        "average_rating": 4.5,
        "total_transactions": 12
    },
    "active_listings": [
        {"id": 15, "title": "Foldable Study Chair", "price": 35.00}
    ],
    "recent_transactions": [
        {"id": 5, "item": "Wooden Study Desk", "type": "sold", "date": "2025-12-20"}
    ],
    "ratings_received": [
        {"stars": 5, "review": "Great seller!", "from": "Pamudi S."}
    ]
}
```

### 7.3 Error Response Format

```json
{
    "error": "Error message here",
    "code": "ERROR_CODE",
    "details": {}  // Optional additional info
}
```

| HTTP Status | Meaning |
|-------------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (no/invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 500 | Server Error |

---

## 8. Web UI Design

### 8.1 Page Structure

| Page | Route | Description | Access |
|------|-------|-------------|--------|
| Login | `/login` | Authentication page | Public |
| Dashboard | `/dashboard` | Overview with stats | Authenticated |
| Listings | `/listings` | Browse/search listings | Authenticated |
| My Listings | `/my-listings` | User's own listings | Authenticated |
| Listing Detail | `/listings/{id}` | Single listing view | Authenticated |
| Create Listing | `/listings/new` | Create new listing | Authenticated |
| Portfolio | `/members/{id}` | Member profile | Authenticated |
| My Portfolio | `/profile` | Own profile | Authenticated |
| Admin Panel | `/admin` | User/report management | Admin only |
| Transactions | `/transactions` | Transaction history | Authenticated |

### 8.2 UI Wireframes

#### Login Page
```
┌────────────────────────────────────────┐
│           CAMPUS TRADING               │
│                                        │
│   ┌────────────────────────────────┐   │
│   │  Username                      │   │
│   └────────────────────────────────┘   │
│   ┌────────────────────────────────┐   │
│   │  Password                      │   │
│   └────────────────────────────────┘   │
│                                        │
│   ┌────────────────────────────────┐   │
│   │           LOGIN                │   │
│   └────────────────────────────────┘   │
│                                        │
│   Don't have an account? Register      │
└────────────────────────────────────────┘
```

#### Dashboard
```
┌────────────────────────────────────────────────────────────┐
│  CAMPUS TRADING    [Search...]    [Profile] [Logout]       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Welcome, Ravindu!                              [+ New]    │
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Active   │  │ Pending  │  │ Sales    │  │ Rating   │   │
│  │ Listings │  │ Offers   │  │ This Mo. │  │          │   │
│  │    3     │  │    5     │  │    2     │  │   4.5★   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                            │
│  Recent Listings                            [View All →]   │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ [IMG] Engineering Mechanics    $35    Listed        │  │
│  │ [IMG] Physics Textbook         $28    Listed        │  │
│  │ [IMG] Arduino Kit              $30    Pending       │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

#### Member Portfolio
```
┌────────────────────────────────────────────────────────────┐
│  CAMPUS TRADING    [Search...]    [Profile] [Logout]       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────┐  Ravindu Bandara                             │
│  │  [IMG]  │  Mechanical Engineering, Year 3               │
│  │         │  Hostel A, Room A-205                         │
│  └─────────┘  ★★★★½ (4.5) - 12 transactions               │
│               Member since: April 2025                     │
│                                                            │
│  ─────────────────────────────────────────────────────────│
│                                                            │
│  Active Listings (3)                                       │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ [IMG] Foldable Chair     $35   [View] [Edit]        │  │
│  │ [IMG] Study Desk         $60   [View] [Edit]        │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                            │
│  Recent Reviews                                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ ★★★★★ "Great seller, item as described!" - Pamudi   │  │
│  │ ★★★★☆ "Good buyer, easy to coordinate" - Dilshan   │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 8.3 Bootstrap Components

- **Navbar**: Responsive navigation with user dropdown
- **Cards**: For listings, stats, and profiles
- **Tables**: For admin panel, transactions
- **Forms**: For create/edit operations
- **Modals**: For confirmations, quick actions
- **Alerts**: For success/error messages
- **Badges**: For status indicators

---

## 9. Security & Logging

### 9.1 Security Measures

| Measure | Implementation |
|---------|----------------|
| Password Hashing | bcrypt with salt rounds = 12 |
| JWT Signing | HS256 with secret key from env |
| Session Expiry | 24 hours, refresh available |
| Input Validation | SQLAlchemy parameterized queries |
| CORS | Restricted to allowed origins |
| Rate Limiting | 100 requests/minute per IP |

### 9.2 Audit Logging

All API operations are logged to:
1. **File**: `logs/audit.log`
2. **Database**: `AuditLog` table

#### Log Format (File)

```
[2026-03-13 10:30:45] [INFO] [user_id=5] [CREATE] Listing #21 created
[2026-03-13 10:31:12] [INFO] [user_id=5] [UPDATE] Listing #21 updated
[2026-03-13 10:32:00] [WARN] [user_id=8] [ACCESS_DENIED] Attempted DELETE on Listing #21
[2026-03-13 10:33:15] [ALERT] [user_id=NULL] [UNAUTHORIZED] Direct DB modification detected on Member #12
```

#### Logging Service

```python
# services/audit_service.py
import logging
import json
from datetime import datetime
from app.models import AuditLog, db

# Configure file logger
file_handler = logging.FileHandler('logs/audit.log')
file_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(message)s'
))
logger = logging.getLogger('audit')
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

def audit_log(user_id, action, table_name, record_id=None,
              old_values=None, new_values=None, is_authorized=True,
              request=None):
    """
    Log an API operation to both file and database.
    """
    # Create log entry
    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=json.dumps(old_values) if old_values else None,
        new_values=json.dumps(new_values) if new_values else None,
        is_authorized=is_authorized,
        ip_address=request.remote_addr if request else None,
        user_agent=request.headers.get('User-Agent') if request else None,
        api_endpoint=request.path if request else None
    )

    db.session.add(log_entry)
    db.session.commit()

    # Also log to file
    level = logging.INFO if is_authorized else logging.WARNING
    msg = f"[user_id={user_id}] [{action}] {table_name}"
    if record_id:
        msg += f" #{record_id}"
    if not is_authorized:
        msg = f"[ACCESS_DENIED] {msg}"

    logger.log(level, msg)
```

### 9.3 Detecting Unauthorized Direct DB Modifications

To detect modifications made without going through the API:

1. **Timestamp Monitoring**: Compare `UpdatedAt` with last API call
2. **Checksum Verification**: Store hash of critical fields
3. **Trigger-Based Logging**: Database triggers that log to separate table

```sql
-- Trigger to detect non-API modifications
DELIMITER //
CREATE TRIGGER trg_Member_Update_Audit
AFTER UPDATE ON Member
FOR EACH ROW
BEGIN
    -- Check if this update came from API (API sets @api_call = 1)
    IF @api_call IS NULL OR @api_call != 1 THEN
        INSERT INTO AuditLog (
            Timestamp, Action, TableName, RecordID,
            OldValues, NewValues, IsAuthorized
        ) VALUES (
            NOW(), 'UPDATE', 'Member', NEW.MemberID,
            JSON_OBJECT('Name', OLD.Name, 'Email', OLD.Email),
            JSON_OBJECT('Name', NEW.Name, 'Email', NEW.Email),
            FALSE
        );
    END IF;
END//
DELIMITER ;
```

---

## 10. SQL Indexing Strategy

### 10.1 Index Analysis

Based on common query patterns in Campus Trading:

| Table | Column(s) | Index Type | Query Pattern |
|-------|-----------|------------|---------------|
| **Listing** | SellerID | B-Tree | Filter by seller |
| **Listing** | CategoryID | B-Tree | Filter by category |
| **Listing** | Status | B-Tree | Filter active listings |
| **Listing** | (CategoryID, Status) | Composite | Category + active |
| **Listing** | AskingPrice | B-Tree | Price range queries |
| **Listing** | CreatedDate | B-Tree | Sort by newest |
| **Offer** | ListingID | B-Tree | Offers per listing |
| **Offer** | BuyerID | B-Tree | User's offers |
| **Offer** | (ListingID, OfferStatus) | Composite | Active offers per listing |
| **Transaction** | SellerID | B-Tree | Seller history |
| **Transaction** | BuyerID | B-Tree | Buyer history |
| **Rating** | RatedID | B-Tree | User's ratings |
| **Message** | ThreadID | B-Tree | Messages in thread |
| **Notification** | RecipientID | B-Tree | User's notifications |
| **Notification** | (RecipientID, IsRead) | Composite | Unread notifications |

### 10.2 Index Creation SQL

```sql
-- 03_create_indexes.sql

-- Listing indexes
CREATE INDEX IDX_Listing_SellerID ON Listing(SellerID);
CREATE INDEX IDX_Listing_CategoryID ON Listing(CategoryID);
CREATE INDEX IDX_Listing_Status ON Listing(Status);
CREATE INDEX IDX_Listing_Category_Status ON Listing(CategoryID, Status);
CREATE INDEX IDX_Listing_Price ON Listing(AskingPrice);
CREATE INDEX IDX_Listing_CreatedDate ON Listing(CreatedDate DESC);

-- Offer indexes
CREATE INDEX IDX_Offer_ListingID ON Offer(ListingID);
CREATE INDEX IDX_Offer_BuyerID ON Offer(BuyerID);
CREATE INDEX IDX_Offer_Listing_Status ON Offer(ListingID, OfferStatus);

-- Transaction indexes
CREATE INDEX IDX_Transaction_SellerID ON `Transaction`(SellerID);
CREATE INDEX IDX_Transaction_BuyerID ON `Transaction`(BuyerID);
CREATE INDEX IDX_Transaction_Date ON `Transaction`(TransactionDate DESC);

-- Rating indexes
CREATE INDEX IDX_Rating_RatedID ON Rating(RatedID);
CREATE INDEX IDX_Rating_TransactionID ON Rating(TransactionID);

-- Message indexes
CREATE INDEX IDX_Message_ThreadID ON Message(ThreadID);
CREATE INDEX IDX_Message_SentDate ON Message(SentDate DESC);

-- Notification indexes
CREATE INDEX IDX_Notification_RecipientID ON Notification(RecipientID);
CREATE INDEX IDX_Notification_Recipient_Read ON Notification(RecipientID, IsRead);
CREATE INDEX IDX_Notification_Created ON Notification(CreatedDate DESC);

-- Session indexes (for auth)
CREATE INDEX IDX_Session_Token ON Session(Token(255));
CREATE INDEX IDX_Session_UserID ON Session(UserID);
```

### 10.3 Drop Indexes (For Benchmarking)

```sql
-- 05_drop_indexes.sql

DROP INDEX IDX_Listing_SellerID ON Listing;
DROP INDEX IDX_Listing_CategoryID ON Listing;
DROP INDEX IDX_Listing_Status ON Listing;
-- ... etc
```

---

## 11. Performance Benchmarking Plan

### 11.1 Metrics to Measure

| Metric | Description | Tool |
|--------|-------------|------|
| API Response Time | End-to-end request time | Python time module |
| SQL Query Time | Database query execution | MySQL EXPLAIN ANALYZE |
| Rows Examined | Number of rows scanned | EXPLAIN output |
| Index Usage | Whether index was used | EXPLAIN output |

### 11.2 Test Queries

```sql
-- Q1: Get listings by category (common browse operation)
SELECT * FROM Listing
WHERE CategoryID = 6 AND Status = 'Listed'
ORDER BY CreatedDate DESC;

-- Q2: Get member's active listings
SELECT * FROM Listing
WHERE SellerID = 5 AND Status = 'Listed';

-- Q3: Get offers for a listing
SELECT o.*, m.Name as BuyerName
FROM Offer o
JOIN Member m ON o.BuyerID = m.MemberID
WHERE o.ListingID = 8 AND o.OfferStatus = 'Submitted';

-- Q4: Get user's unread notifications
SELECT * FROM Notification
WHERE RecipientID = 5 AND IsRead = FALSE
ORDER BY CreatedDate DESC;

-- Q5: Price range query
SELECT * FROM Listing
WHERE AskingPrice BETWEEN 10 AND 50 AND Status = 'Listed';

-- Q6: Member rating average
SELECT AVG(Stars) FROM Rating WHERE RatedID = 5;
```

### 11.3 Benchmarking Process

```python
# benchmarks/run_benchmark.py
import time
import json
from app import create_app, db

def benchmark_query(query, description):
    """Run a query and measure execution time."""

    # Without index (run DROP INDEX first)
    start = time.perf_counter()
    result = db.session.execute(query)
    without_index = time.perf_counter() - start

    # Get EXPLAIN output
    explain = db.session.execute(f"EXPLAIN {query}").fetchall()

    return {
        'description': description,
        'query': query,
        'time_ms': without_index * 1000,
        'explain': [dict(row) for row in explain]
    }

def run_benchmarks():
    results = {
        'without_indexes': [],
        'with_indexes': []
    }

    queries = [
        ("SELECT * FROM Listing WHERE CategoryID = 6 AND Status = 'Listed'",
         "Listings by category"),
        ("SELECT * FROM Listing WHERE SellerID = 5",
         "Listings by seller"),
        # ... more queries
    ]

    # Run without indexes
    for query, desc in queries:
        results['without_indexes'].append(
            benchmark_query(query, desc)
        )

    # Create indexes
    db.session.execute(open('sql/03_create_indexes.sql').read())

    # Run with indexes
    for query, desc in queries:
        results['with_indexes'].append(
            benchmark_query(query, desc)
        )

    return results
```

### 11.4 Expected Results

| Query | Without Index | With Index | Improvement |
|-------|---------------|------------|-------------|
| Listings by category | ~50ms | ~5ms | 10x |
| Listings by seller | ~30ms | ~2ms | 15x |
| Offers for listing | ~20ms | ~1ms | 20x |
| Unread notifications | ~40ms | ~3ms | 13x |
| Price range | ~60ms | ~8ms | 7.5x |

### 11.5 EXPLAIN Output Analysis

**Before Index:**
```
+----+-------------+---------+------+---------------+------+---------+------+-------+-------------+
| id | select_type | table   | type | possible_keys | key  | key_len | ref  | rows  | Extra       |
+----+-------------+---------+------+---------------+------+---------+------+-------+-------------+
|  1 | SIMPLE      | Listing | ALL  | NULL          | NULL | NULL    | NULL | 10000 | Using where |
+----+-------------+---------+------+---------------+------+---------+------+-------+-------------+
```
- `type: ALL` = Full table scan
- `rows: 10000` = Examining all rows

**After Index:**
```
+----+-------------+---------+------+------------------------+------------------------+---------+-------+------+-------------+
| id | select_type | table   | type | possible_keys          | key                    | key_len | ref   | rows | Extra       |
+----+-------------+---------+------+------------------------+------------------------+---------+-------+------+-------------+
|  1 | SIMPLE      | Listing | ref  | IDX_Listing_Category   | IDX_Listing_Category   | 4       | const |   50 | Using where |
+----+-------------+---------+------+------------------------+------------------------+---------+-------+------+-------------+
```
- `type: ref` = Index lookup
- `rows: 50` = Only examining matching rows

---

## 12. Implementation Timeline

| Phase | Tasks | Files |
|-------|-------|-------|
| **Phase 1: Setup** | Project structure, DB setup, models | `config.py`, `models/*`, SQL scripts |
| **Phase 2: Auth** | User registration, login, JWT | `routes/auth.py`, `middleware/auth.py` |
| **Phase 3: RBAC** | Role decorators, permission checks | `middleware/rbac.py` |
| **Phase 4: APIs** | CRUD endpoints for all tables | `routes/*.py` |
| **Phase 5: UI** | HTML templates, forms | `templates/*` |
| **Phase 6: Logging** | Audit trail implementation | `services/audit_service.py` |
| **Phase 7: Indexing** | Create indexes, benchmark | `sql/*.sql`, `benchmarks/*` |
| **Phase 8: Report** | Documentation, graphs | `report.pdf` |
| **Phase 9: Video** | Screen recording | 3-5 minutes |

---

## Appendix A: Environment Variables

```env
# .env.example
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-super-secret-key-here

# Database
DB_HOST=localhost
DB_PORT=3306
DB_NAME=CampusTrading
DB_USER=root
DB_PASSWORD=your-password

# JWT
JWT_SECRET_KEY=another-secret-key
JWT_ACCESS_TOKEN_EXPIRES=86400

# Logging
LOG_LEVEL=INFO
AUDIT_LOG_PATH=logs/audit.log
```

---

## Appendix B: API Quick Reference

| Endpoint | Method | Auth | Role | Description |
|----------|--------|------|------|-------------|
| `/api/login` | POST | No | - | Login |
| `/api/logout` | POST | Yes | Any | Logout |
| `/api/isAuth` | GET | Yes | Any | Check session |
| `/api/members` | GET | Yes | Any | List members |
| `/api/members/{id}` | GET | Yes | Any | Get member |
| `/api/members/{id}/portfolio` | GET | Yes | Any | View portfolio |
| `/api/listings` | GET | Yes | Any | List listings |
| `/api/listings` | POST | Yes | Any | Create listing |
| `/api/listings/{id}` | PUT | Yes | Owner/Admin | Update listing |
| `/api/listings/{id}` | DELETE | Yes | Admin | Delete listing |
| `/api/offers` | POST | Yes | Any | Make offer |
| `/api/offers/{id}` | PUT | Yes | Owner/Admin | Update offer |
| `/api/admin/users` | GET | Yes | Admin | List users |
| `/api/admin/reports` | GET | Yes | Admin | List reports |

---

**Document Version:** 1.0
**Last Updated:** March 2026
**Team 8 - CS432 Databases**
