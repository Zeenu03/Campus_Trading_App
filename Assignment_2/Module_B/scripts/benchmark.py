#!/usr/bin/env python3
"""
Campus Trading App — SQL Index Performance Benchmark
=====================================================
Connects to a running MySQL instance (Docker or local), seeds realistic
test data if the tables are empty, then measures query performance
BEFORE and AFTER applying sql/indexes.sql.

Charts are saved to  scripts/charts/
The final report is written to  report/README.md

Usage
-----
  pip install -r requirements.txt
  python benchmark.py \\
      --host 127.0.0.1 --port 3306 \\
      --user root --password root \\
      --db CampusTradingB

Options
-------
  --indexes-sql   Path to indexes.sql  (default: ../sql/indexes.sql)
  --charts-dir    Directory for PNG output (default: ./charts)
  --report-out    Path for README.md   (default: ../report/README.md)
  --runs          Query iterations per phase (default: 10)
  --skip-seed     Skip test-data seeding
  --skip-drop     Skip dropping existing idx_% indexes before Phase 1
"""

import argparse
import os
import random
import re
import string
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import mysql.connector

# ---------------------------------------------------------------------------
# Benchmark query definitions
# ---------------------------------------------------------------------------
QUERIES = [
    {
        "id": "Q1",
        "name": "Active listings ordered by date",
        "endpoint": "GET /listings (browse page)",
        "query": "SELECT * FROM Listing WHERE Status='Listed' ORDER BY CreatedDate DESC LIMIT 20",
        "args": [],
        "index_hint": "idx_listing_status_created",
    },
    {
        "id": "Q2",
        "name": "Listings by seller",
        "endpoint": "GET /members/{id}/portfolio",
        "query": "SELECT * FROM Listing WHERE SellerID = %s",
        "args": [1],
        "index_hint": "idx_listing_seller_created",
    },
    {
        "id": "Q3",
        "name": "Submitted offers for a listing",
        "endpoint": "GET /listings/{id}/offers",
        "query": "SELECT * FROM Offer WHERE ListingID = %s AND OfferStatus = 'Submitted'",
        "args": [1],
        "index_hint": "idx_offer_listing_status",
    },
    {
        "id": "Q4",
        "name": "Unread notifications for a member",
        "endpoint": "GET /notifications (NotificationBell)",
        "query": "SELECT * FROM Notification WHERE RecipientID = %s AND IsRead = FALSE",
        "args": [1],
        "index_hint": "idx_notification_recipient_read",
    },
    {
        "id": "Q5",
        "name": "Average rating for a member",
        "endpoint": "GET /members/{id}/portfolio",
        "query": "SELECT AVG(Stars) FROM Rating WHERE RatedID = %s",
        "args": [1],
        "index_hint": "idx_rating_rated",
    },
    {
        "id": "Q6",
        "name": "Transaction count for a member",
        "endpoint": "GET /transactions",
        "query": "SELECT COUNT(*) FROM Transaction WHERE SellerID = %s OR BuyerID = %s",
        "args": [1, 1],
        "index_hint": "idx_transaction_seller / idx_transaction_buyer",
    },
    {
        "id": "Q7",
        "name": "Active wish requests ordered by date",
        "endpoint": "GET /wishrequests",
        "query": "SELECT * FROM WishRequest WHERE Status='Active' ORDER BY CreatedDate DESC LIMIT 20",
        "args": [],
        "index_hint": "idx_wishrequest_status_created",
    },
    {
        "id": "Q8",
        "name": "Audit log ordered by timestamp",
        "endpoint": "GET /admin/audit-log",
        "query": "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 20",
        "args": [],
        "index_hint": "idx_auditlog_timestamp",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rnd_str(n=8):
    return "".join(random.choices(string.ascii_lowercase, k=n))


def rnd_email():
    return f"{rnd_str(6)}.{rnd_str(4)}@iitgn.ac.in"


def rnd_phone():
    return f"9{random.randint(100000000, 999999999)}"


def get_connection(args):
    return mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.db,
        autocommit=True,
    )


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def seed_data(conn, target_members=120, target_listings=600,
              target_offers=800, target_notifications=3000,
              target_transactions=300, target_ratings=200,
              target_wishrequests=150, target_auditlogs=500):
    """Insert realistic volumes of test data if the tables are sparse."""
    cur = conn.cursor()

    # ---- count existing rows ----
    cur.execute("SELECT COUNT(*) FROM Member")
    existing_members = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM Listing")
    existing_listings = cur.fetchone()[0]

    if existing_members >= target_members and existing_listings >= target_listings:
        print(f"  Sufficient data already present "
              f"({existing_members} members, {existing_listings} listings). Skipping seed.")
        cur.close()
        return

    print(f"  Seeding test data …")

    # ---- sys_user + Member ----
    cur.execute("SELECT role_id FROM sys_role WHERE role_name = 'member'")
    row = cur.fetchone()
    if not row:
        print("  ERROR: 'member' role not found. Run init.sql first.")
        sys.exit(1)
    member_role_id = row[0]

    import hashlib
    ph = "$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LPVn1zpNnZi"  # bcrypt of "Test@1234"

    departments = ["Computer Science", "Electrical", "Mechanical", "Civil", "Chemical", "Mathematics"]
    hostels = ["Saraswati", "Laxmi", "Gargi", "Raman", "Aryabhata", "Bose"]
    conditions = ["New", "Like New", "Good", "Fair", "Poor"]
    wish_conditions = ["New", "Like New", "Good", "Fair", "Poor", "Any"]

    # Gather existing member IDs
    cur.execute("SELECT MemberID FROM Member")
    member_ids = [r[0] for r in cur.fetchall()]

    need_members = max(0, target_members - existing_members)
    for _ in range(need_members):
        email = rnd_email()
        try:
            cur.execute("INSERT INTO sys_user (email, password_hash) VALUES (%s, %s)", (email, ph))
            uid = cur.lastrowid
            cur.execute("INSERT INTO sys_user_role (user_id, role_id) VALUES (%s, %s)", (uid, member_role_id))
            dept = random.choice(departments)
            hostel = random.choice(hostels)
            cur.execute(
                "INSERT INTO Member (user_id, Name, ContactNumber, Department, YearOfStudy, Hostel, RoomNumber) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (uid, rnd_str(6).capitalize() + " " + rnd_str(5).capitalize(),
                 rnd_phone(), dept, random.randint(1, 5), hostel,
                 str(random.randint(101, 499)))
            )
            cur.execute("SELECT LAST_INSERT_ID()")
            member_ids.append(cur.fetchone()[0])
        except mysql.connector.IntegrityError:
            pass

    print(f"    Members: {len(member_ids)}")

    # ---- Categories ----
    cur.execute("SELECT CategoryID FROM Category WHERE IsActive = 1")
    cat_ids = [r[0] for r in cur.fetchall()]
    if not cat_ids:
        print("  ERROR: No active categories. Run init.sql first.")
        sys.exit(1)

    # ---- Listings ----
    cur.execute("SELECT COUNT(*) FROM Listing")
    cur_listings = cur.fetchone()[0]
    need_listings = max(0, target_listings - cur_listings)
    statuses = ["Listed"] * 6 + ["Sold"] * 2 + ["Withdrawn"] * 1
    listing_ids = []
    base_date = datetime.now() - timedelta(days=180)
    for i in range(need_listings):
        seller = random.choice(member_ids)
        cat = random.choice(cat_ids)
        status = random.choice(statuses)
        price = round(random.uniform(50, 8000), 2)
        created = base_date + timedelta(seconds=random.randint(0, 15552000))
        try:
            cur.execute(
                "INSERT INTO Listing (SellerID, CategoryID, Title, Description, AskingPrice, "
                "IsNegotiable, `Condition`, Status, CreatedDate) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (seller, cat,
                 f"{rnd_str(5).capitalize()} {rnd_str(4).capitalize()} for sale",
                 f"Good quality item. {rnd_str(20)}.",
                 price, random.choice([0, 1]),
                 random.choice(conditions), status, created)
            )
            listing_ids.append(cur.lastrowid)
        except mysql.connector.IntegrityError:
            pass

    if not listing_ids:
        cur.execute("SELECT ListingID FROM Listing")
        listing_ids = [r[0] for r in cur.fetchall()]

    print(f"    Listings: {cur_listings + len(listing_ids)}")

    # ---- Offers ----
    cur.execute("SELECT COUNT(*) FROM Offer")
    cur_offers = cur.fetchone()[0]
    need_offers = max(0, target_offers - cur_offers)
    offer_statuses = ["Submitted"] * 5 + ["Accepted"] * 2 + ["Declined"] * 2 + ["Withdrawn"] * 1
    for _ in range(need_offers):
        listing_id = random.choice(listing_ids)
        cur.execute("SELECT SellerID FROM Listing WHERE ListingID = %s", (listing_id,))
        row = cur.fetchone()
        if not row:
            continue
        seller_id = row[0]
        buyer_id = random.choice([m for m in member_ids if m != seller_id]) if len(member_ids) > 1 else seller_id
        price = round(random.uniform(20, 7000), 2)
        status = random.choice(offer_statuses)
        try:
            cur.execute(
                "INSERT INTO Offer (ListingID, BuyerID, OfferedPrice, OfferStatus) "
                "VALUES (%s, %s, %s, %s)",
                (listing_id, buyer_id, price, status)
            )
        except mysql.connector.IntegrityError:
            pass

    print(f"    Offers seeded")

    # ---- Notifications ----
    cur.execute("SELECT COUNT(*) FROM Notification")
    cur_notifs = cur.fetchone()[0]
    need_notifs = max(0, target_notifications - cur_notifs)
    notif_types = ["OfferReceived", "OfferAccepted", "OfferDeclined", "PriceDropped",
                   "StatusChanged", "General", "TransactionCompleted", "RatingReceived"]
    for _ in range(need_notifs):
        recipient = random.choice(member_ids)
        ntype = random.choice(notif_types)
        is_read = random.choice([True, False, False])
        created = datetime.now() - timedelta(seconds=random.randint(0, 2592000))
        try:
            cur.execute(
                "INSERT INTO Notification (RecipientID, NotificationType, Title, Message, IsRead, CreatedDate) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (recipient, ntype, f"{ntype} notification",
                 f"Test notification message {rnd_str(10)}.", is_read, created)
            )
        except mysql.connector.Error:
            pass

    print(f"    Notifications seeded")

    # ---- Transactions ----
    cur.execute("SELECT COUNT(*) FROM Transaction")
    cur_txns = cur.fetchone()[0]
    need_txns = max(0, target_transactions - cur_txns)
    cur.execute("SELECT OfferID, ListingID, BuyerID FROM Offer WHERE OfferStatus = 'Accepted' LIMIT 500")
    accepted_offers = cur.fetchall()
    for _ in range(need_txns):
        if not accepted_offers:
            break
        offer_id, listing_id, buyer_id = random.choice(accepted_offers)
        cur.execute("SELECT SellerID FROM Listing WHERE ListingID = %s", (listing_id,))
        row = cur.fetchone()
        if not row or row[0] == buyer_id:
            continue
        seller_id = row[0]
        price = round(random.uniform(50, 5000), 2)
        try:
            cur.execute(
                "INSERT INTO Transaction (ListingID, SellerID, BuyerID, OfferID, AgreedPrice) "
                "VALUES (%s, %s, %s, %s, %s)",
                (listing_id, seller_id, buyer_id, offer_id, price)
            )
        except mysql.connector.IntegrityError:
            pass

    print(f"    Transactions seeded")

    # ---- Ratings ----
    cur.execute("SELECT COUNT(*) FROM Rating")
    cur_ratings = cur.fetchone()[0]
    need_ratings = max(0, target_ratings - cur_ratings)
    cur.execute("SELECT TransactionID, SellerID, BuyerID FROM Transaction LIMIT 300")
    txns = cur.fetchall()
    for _ in range(need_ratings):
        if not txns:
            break
        txn_id, seller_id, buyer_id = random.choice(txns)
        rater = random.choice([seller_id, buyer_id])
        rated = seller_id if rater == buyer_id else buyer_id
        if rater == rated:
            continue
        stars = random.randint(1, 5)
        try:
            cur.execute(
                "INSERT INTO Rating (TransactionID, RaterID, RatedID, Stars, ReviewText) "
                "VALUES (%s, %s, %s, %s, %s)",
                (txn_id, rater, rated, stars, f"Review: {rnd_str(20)}")
            )
        except mysql.connector.IntegrityError:
            pass

    print(f"    Ratings seeded")

    # ---- WishRequests ----
    cur.execute("SELECT COUNT(*) FROM WishRequest")
    cur_wr = cur.fetchone()[0]
    need_wr = max(0, target_wishrequests - cur_wr)
    wr_statuses = ["Active"] * 5 + ["Fulfilled"] * 2 + ["Cancelled"] * 2 + ["Expired"] * 1
    for _ in range(need_wr):
        requester = random.choice(member_ids)
        status = random.choice(wr_statuses)
        min_b = round(random.uniform(50, 1000), 2)
        max_b = round(min_b + random.uniform(100, 3000), 2)
        created = datetime.now() - timedelta(seconds=random.randint(0, 5184000))
        try:
            cur.execute(
                "INSERT INTO WishRequest (RequesterID, ItemDescription, MinBudget, MaxBudget, "
                "PreferredCondition, Status, CreatedDate) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (requester, f"Looking for {rnd_str(6)} {rnd_str(4)}",
                 min_b, max_b, random.choice(wish_conditions), status, created)
            )
        except mysql.connector.Error:
            pass

    print(f"    WishRequests seeded")

    # ---- audit_log ----
    cur.execute("SELECT COUNT(*) FROM audit_log")
    cur_al = cur.fetchone()[0]
    need_al = max(0, target_auditlogs - cur_al)
    tables = ["Listing", "Offer", "Notification", "Transaction", "Member"]
    actions = ["INSERT", "UPDATE", "DELETE"]
    for _ in range(need_al):
        ts = datetime.now() - timedelta(seconds=random.randint(0, 7776000))
        try:
            cur.execute(
                "INSERT INTO audit_log (timestamp, session_id, user_id, action, target_table, target_id, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (ts, rnd_str(16), random.choice(member_ids),
                 random.choice(actions), random.choice(tables),
                 random.randint(1, 500), "success")
            )
        except mysql.connector.Error:
            pass

    print(f"    Audit logs seeded")
    cur.close()
    print("  Seeding complete.")


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

def list_custom_indexes(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT TABLE_NAME, INDEX_NAME
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND INDEX_NAME LIKE 'idx_%'
        GROUP BY TABLE_NAME, INDEX_NAME
    """)
    indexes = cur.fetchall()
    cur.close()
    return indexes


def drop_custom_indexes(conn):
    indexes = list_custom_indexes(conn)
    if not indexes:
        print("  No custom idx_% indexes found to drop.")
        return 0
    cur = conn.cursor()
    for table, index in indexes:
        cur.execute(f"DROP INDEX `{index}` ON `{table}`")
    cur.close()
    print(f"  Dropped {len(indexes)} custom index(es).")
    return len(indexes)


def apply_indexes(conn, sql_path):
    with open(sql_path, "r") as fh:
        raw = fh.read()

    cur = conn.cursor()
    # Strip comments and split on semicolons
    statements = []
    for stmt in raw.split(";"):
        # Remove line comments
        lines = [l for l in stmt.splitlines()
                 if not l.strip().startswith("--")]
        cleaned = " ".join(lines).strip()
        # Skip USE / SELECT (verification query) / empty
        if not cleaned:
            continue
        upper = cleaned.upper()
        if upper.startswith("USE ") or upper.startswith("SELECT "):
            continue
        statements.append(cleaned)

    applied = 0
    for stmt in statements:
        try:
            cur.execute(stmt)
            applied += 1
        except mysql.connector.Error as exc:
            if exc.errno == 1061:  # Duplicate index name
                print(f"  (skipped — already exists: {exc.msg})")
            else:
                print(f"  Warning: {exc}")
    cur.close()
    print(f"  Applied {applied} index statement(s).")
    return applied


# ---------------------------------------------------------------------------
# EXPLAIN capture
# ---------------------------------------------------------------------------

def get_explain(conn, query, args):
    cur = conn.cursor(dictionary=True)
    cur.execute("EXPLAIN " + query, args if args else None)
    rows = cur.fetchall()
    cur.close()
    return rows  # list of dicts


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

def time_query(conn, query, args, runs=10):
    times_ms = []
    for _ in range(runs):
        cur = conn.cursor()
        t0 = time.perf_counter()
        cur.execute(query, args if args else None)
        cur.fetchall()
        elapsed = (time.perf_counter() - t0) * 1000
        times_ms.append(elapsed)
        cur.close()
    return {
        "min": min(times_ms),
        "avg": sum(times_ms) / len(times_ms),
        "max": max(times_ms),
        "runs": runs,
        "all": times_ms,
    }


# ---------------------------------------------------------------------------
# Full benchmark phase
# ---------------------------------------------------------------------------

def run_phase(conn, label, runs):
    results = []
    for q in QUERIES:
        print(f"    [{label}] {q['id']}: {q['name']} …", end="", flush=True)
        explain = get_explain(conn, q["query"], q["args"])
        timing = time_query(conn, q["query"], q["args"], runs=runs)
        results.append({**q, "explain": explain, "timing": timing, "label": label})
        print(f" avg={timing['avg']:.3f} ms")
    return results


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------

BEFORE_COLOR = "#E07B39"
AFTER_COLOR  = "#4CAF50"


def save_timing_chart(before, after, out_path):
    labels = [r["id"] for r in before]
    b_avgs = [r["timing"]["avg"] for r in before]
    a_avgs = [r["timing"]["avg"] for r in after]

    x = range(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(13, 6))
    bars_b = ax.bar([i - width / 2 for i in x], b_avgs, width,
                    label="Before indexes", color=BEFORE_COLOR, alpha=0.88)
    bars_a = ax.bar([i + width / 2 for i in x], a_avgs, width,
                    label="After indexes", color=AFTER_COLOR, alpha=0.88)

    ax.set_xlabel("Query", fontsize=12)
    ax.set_ylabel("Average execution time (ms)", fontsize=12)
    ax.set_title("Query Execution Time: Before vs After Indexes", fontsize=14, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=11)
    ax.legend(fontsize=11)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    # Annotate bars
    for bar in bars_b:
        h = bar.get_height()
        ax.annotate(f"{h:.2f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, color="#555")
    for bar in bars_a:
        h = bar.get_height()
        ax.annotate(f"{h:.2f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, color="#2a6b2a")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Saved timing chart → {out_path}")


def save_rows_chart(before, after, out_path):
    labels = [r["id"] for r in before]

    def rows_of(phase_results):
        out = []
        for r in phase_results:
            rows_val = None
            for row in r["explain"]:
                rv = row.get("rows") or row.get("Rows")
                if rv is not None:
                    rows_val = int(rv)
                    break
            # Log scale requires values > 0; floor at 1
            out.append(max(rows_val if rows_val is not None else 1, 1))
        return out

    b_rows = rows_of(before)
    a_rows = rows_of(after)

    x = range(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(13, 6))
    bars_b = ax.bar([i - width / 2 for i in x], b_rows, width,
                    label="Before indexes", color=BEFORE_COLOR, alpha=0.88)
    bars_a = ax.bar([i + width / 2 for i in x], a_rows, width,
                    label="After indexes", color=AFTER_COLOR, alpha=0.88)

    ax.set_yscale("log")
    ax.set_xlabel("Query", fontsize=12)
    ax.set_ylabel("Rows examined — log scale (EXPLAIN estimate)", fontsize=12)
    ax.set_title("Rows Examined: Before vs After Indexes (Log Scale)", fontsize=14, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=11)
    ax.legend(fontsize=11)
    ax.grid(axis="y", linestyle="--", alpha=0.5, which="both")

    # Annotate bar tops with raw values
    for bar, val in zip(bars_b, b_rows):
        ax.annotate(f"{val:,}", xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, color="#555")
    for bar, val in zip(bars_a, a_rows):
        ax.annotate(f"{val:,}", xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, color="#2a6b2a")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Saved rows chart   → {out_path}")


def save_speedup_chart(before, after, out_path):
    labels = [r["id"] for r in before]
    speedups = []
    for b, a in zip(before, after):
        b_avg = b["timing"]["avg"]
        a_avg = a["timing"]["avg"]
        if b_avg > 0:
            speedups.append(((b_avg - a_avg) / b_avg) * 100)
        else:
            speedups.append(0.0)

    colors = [AFTER_COLOR if s >= 0 else BEFORE_COLOR for s in speedups]

    fig, ax = plt.subplots(figsize=(13, 5))
    bars = ax.bar(labels, speedups, color=colors, alpha=0.88)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Query", fontsize=12)
    ax.set_ylabel("Speedup (%)", fontsize=12)
    ax.set_title("Percentage Improvement After Applying Indexes", fontsize=14, fontweight="bold")
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for bar, val in zip(bars, speedups):
        ax.annotate(f"{val:+.1f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 4 if val >= 0 else -12),
                    textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, fontweight="bold")

    better = mpatches.Patch(color=AFTER_COLOR, label="Improvement")
    worse  = mpatches.Patch(color=BEFORE_COLOR, label="Regression")
    ax.legend(handles=[better, worse], fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Saved speedup chart → {out_path}")


# ---------------------------------------------------------------------------
# README generation
# ---------------------------------------------------------------------------

INDEX_CATALOGUE = [
    ("idx_listing_status_created",   "Listing",      "Status, CreatedDate",  "composite", "Q1 browse ORDER BY, /listings default sort"),
    ("idx_listing_seller_created",   "Listing",      "SellerID, CreatedDate","composite", "Q2 portfolio page, seller's listings"),
    ("idx_listing_status_category",  "Listing",      "Status, CategoryID",   "composite", "/listings?category_id= filter"),
    ("idx_listing_status_price",     "Listing",      "Status, AskingPrice",  "composite", "/listings?min_price= / max_price= filter"),
    ("idx_offer_listing_status",     "Offer",        "ListingID, OfferStatus","composite","Q3 open offers, listing detail page"),
    ("idx_offer_buyer",              "Offer",        "BuyerID",              "single",    "Buyer's active offer look-up"),
    ("idx_notification_recipient_read","Notification","RecipientID, IsRead", "composite", "Q4 unread count, NotificationBell poll"),
    ("idx_notification_recipient_created","Notification","RecipientID, CreatedDate","composite","Paginated /notifications sort"),
    ("idx_rating_rated",             "Rating",       "RatedID, RatingDate",  "composite", "Q5 AVG(Stars), portfolio ratings list"),
    ("idx_transaction_seller",       "Transaction",  "SellerID",             "single",    "Q6 /transactions WHERE SellerID"),
    ("idx_transaction_buyer",        "Transaction",  "BuyerID",              "single",    "Q6 /transactions WHERE BuyerID (OR branch)"),
    ("idx_message_thread_sent",      "Message",      "ThreadID, SentDate",   "composite", "Paginated chat history ORDER BY SentDate"),
    ("idx_wishrequest_status_created","WishRequest", "Status, CreatedDate",  "composite", "Q7 /wishrequests active board"),
    ("idx_wishrequest_requester",    "WishRequest",  "RequesterID",          "single",    "Member's own wish requests"),
    ("idx_auditlog_timestamp",       "audit_log",    "timestamp",            "single",    "Q8 /admin/audit-log ORDER BY timestamp"),
    ("idx_report_status_submitted",  "Report",       "Status, SubmittedDate","composite", "/reports filtered by status + sort"),
]


def _null(v):
    return v if v not in (None, "None", "") else "—"


def _explain_table_md(explain_rows):
    """Return a markdown table for an EXPLAIN result (list of dicts)."""
    if not explain_rows:
        return "_No EXPLAIN data_\n"
    cols = ["id", "select_type", "table", "type", "possible_keys", "key", "key_len", "rows", "Extra"]
    header = "| " + " | ".join(c for c in cols) + " |"
    sep    = "| " + " | ".join("---" for _ in cols) + " |"
    lines  = [header, sep]
    for row in explain_rows:
        vals = []
        for c in cols:
            v = row.get(c) or row.get(c.lower()) or row.get(c.capitalize())
            vals.append(_null(str(v) if v is not None else None))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def _timing_table_md(b, a):
    speedup = ((b["avg"] - a["avg"]) / b["avg"] * 100) if b["avg"] > 0 else 0.0
    direction = "faster" if speedup >= 0 else "slower"
    lines = [
        "| Metric | Before indexes | After indexes | Change |",
        "| --- | --- | --- | --- |",
        f"| Min (ms) | {b['min']:.3f} | {a['min']:.3f} | — |",
        f"| **Avg (ms)** | **{b['avg']:.3f}** | **{a['avg']:.3f}** | **{abs(speedup):.1f}% {direction}** |",
        f"| Max (ms) | {b['max']:.3f} | {a['max']:.3f} | — |",
        f"| Runs | {b['runs']} | {a['runs']} | — |",
    ]
    return "\n".join(lines) + "\n"


ACCESS_TYPE_RANK = {"system": 0, "const": 1, "eq_ref": 2, "ref": 3,
                    "range": 4, "index": 5, "ALL": 6}


def _access_type_note(before_type, after_type):
    """Return a plain-English description of the EXPLAIN access plan change."""
    b = (before_type or "").lower()
    a = (after_type or "").lower()
    mapping = {
        "all":    "full table scan (reads every row)",
        "index":  "full index scan (reads entire index)",
        "range":  "index range scan (reads only matching range)",
        "ref":    "non-unique index lookup",
        "eq_ref": "unique index lookup (at most one matching row per key)",
        "const":  "constant lookup (single-row result guaranteed)",
        "system": "system (single-row table)",
    }
    b_desc = mapping.get(b, f"`{b}`")
    a_desc = mapping.get(a, f"`{a}`")
    if b == a:
        return f"Access type unchanged at **{b_desc}**."
    return (f"The optimizer shifted from a **{b_desc}** to a **{a_desc}**. "
            "This means MySQL can now locate matching rows directly via the index "
            "rather than scanning all rows in the table.")


def generate_readme(before, after, charts_dir, out_path, index_count, runs):
    total_b_avg = sum(r["timing"]["avg"] for r in before)
    total_a_avg = sum(r["timing"]["avg"] for r in after)
    overall_speedup = ((total_b_avg - total_a_avg) / total_b_avg * 100) if total_b_avg > 0 else 0

    # Relative paths from report/ to charts/
    charts_rel = os.path.relpath(charts_dir, os.path.dirname(out_path))

    lines = []

    # ------------------------------------------------------------------ Header
    lines += [
        "# Campus Trading App — SQL Index Optimization Report",
        "",
        f"> Generated on **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**  ",
        f"> Database: `CampusTradingB` &nbsp;|&nbsp; "
        f"Queries benchmarked: **{len(QUERIES)}** &nbsp;|&nbsp; "
        f"Iterations per phase: **{runs}**",
        "",
    ]

    # ------------------------------------------------------------------ TOC
    lines += [
        "## Table of Contents",
        "",
        "1. [Executive Summary](#1-executive-summary)",
        "2. [Methodology](#2-methodology)",
        "3. [Index Catalogue](#3-index-catalogue)",
        "4. [Table–Index Relationship Diagram](#4-tableindex-relationship-diagram)",
        "5. [Benchmark Charts](#5-benchmark-charts)",
        "6. [Per-Query Analysis](#6-per-query-analysis)",
    ]
    for q in QUERIES:
        anchor = re.sub(r"[^a-z0-9]+", "-", q["name"].lower()).strip("-")
        lines.append(f"   - [{q['id']}: {q['name']}](#{q['id'].lower()}-{anchor})")
    lines += [
        "7. [Conclusion & Recommendations](#7-conclusion--recommendations)",
        "",
    ]

    # ------------------------------------------------------------------ 1. Executive Summary
    lines += [
        "---",
        "",
        "## 1. Executive Summary",
        "",
        f"| Metric | Value |",
        f"| --- | --- |",
        f"| Custom indexes created | **{index_count}** |",
        f"| Queries benchmarked | **{len(QUERIES)}** |",
        f"| Avg total time before | **{total_b_avg:.3f} ms** |",
        f"| Avg total time after | **{total_a_avg:.3f} ms** |",
        f"| Overall avg speedup | **{overall_speedup:.1f}%** |",
        "",
    ]

    lines += [
        "### Per-query speedup summary",
        "",
        "| Query | Name | Before avg (ms) | After avg (ms) | Speedup |",
        "| --- | --- | --- | --- | --- |",
    ]
    for b, a in zip(before, after):
        sp = ((b["timing"]["avg"] - a["timing"]["avg"]) / b["timing"]["avg"] * 100) if b["timing"]["avg"] > 0 else 0
        badge = f"{sp:+.1f}%"
        lines.append(
            f"| {b['id']} | {b['name']} | {b['timing']['avg']:.3f} | {a['timing']['avg']:.3f} | {badge} |"
        )
    lines += [""]

    # ------------------------------------------------------------------ 2. Methodology
    lines += [
        "---",
        "",
        "## 2. Methodology",
        "",
        "### Test environment",
        "",
        "| Component | Details |",
        "| --- | --- |",
        "| Database engine | MySQL 8.0 (Docker container) |",
        "| Schema | `CampusTradingB` initialized from `sql/init.sql` |",
        "| Storage engine | InnoDB (default) |",
        "| Data volume | ~120 members, ~600 listings, ~800 offers, ~3 000 notifications |",
        "",
        "### Procedure",
        "",
        "1. All `idx_%` custom indexes are **dropped** to establish a clean baseline.",
        "2. Each benchmark query is executed **{runs} times** and min/avg/max times are recorded.".format(runs=runs),
        "3. `EXPLAIN` is run for each query to capture the optimizer's access plan.",
        "4. All indexes from `sql/indexes.sql` are **applied**.",
        "5. The same queries are executed another **{runs} times** under identical conditions.".format(runs=runs),
        "6. Results are compared and this report is generated.",
        "",
        "All timing measurements use Python's `time.perf_counter()` (nanosecond resolution).",
        "The reported value is the **arithmetic mean** across all iterations.",
        "",
    ]

    # ------------------------------------------------------------------ 3. Index Catalogue
    lines += [
        "---",
        "",
        "## 3. Index Catalogue",
        "",
        "| Index Name | Table | Columns | Type | Targeted Query / API Endpoint |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in INDEX_CATALOGUE:
        lines.append(f"| `{row[0]}` | `{row[1]}` | `{row[2]}` | {row[3]} | {row[4]} |")
    lines += [""]

    # ------------------------------------------------------------------ 4. Mermaid diagram
    lines += [
        "---",
        "",
        "## 4. Table–Index Relationship Diagram",
        "",
        "The diagram below shows which indexes are applied to which tables "
        "and the primary API endpoint they serve.",
        "",
        "```mermaid",
        "flowchart LR",
        '  subgraph listing_grp ["Listing"]',
        "    idx_listing_status_created",
        "    idx_listing_seller_created",
        "    idx_listing_status_category",
        "    idx_listing_status_price",
        "  end",
        '  subgraph offer_grp ["Offer"]',
        "    idx_offer_listing_status",
        "    idx_offer_buyer",
        "  end",
        '  subgraph notif_grp ["Notification"]',
        "    idx_notification_recipient_read",
        "    idx_notification_recipient_created",
        "  end",
        '  subgraph rating_grp ["Rating"]',
        "    idx_rating_rated",
        "  end",
        '  subgraph txn_grp ["Transaction"]',
        "    idx_transaction_seller",
        "    idx_transaction_buyer",
        "  end",
        '  subgraph msg_grp ["Message"]',
        "    idx_message_thread_sent",
        "  end",
        '  subgraph wr_grp ["WishRequest"]',
        "    idx_wishrequest_status_created",
        "    idx_wishrequest_requester",
        "  end",
        '  subgraph audit_grp ["audit_log"]',
        "    idx_auditlog_timestamp",
        "  end",
        '  subgraph rpt_grp ["Report"]',
        "    idx_report_status_submitted",
        "  end",
        "",
        '  Q1["Q1: GET /listings"] --> idx_listing_status_created',
        '  Q2["Q2: Portfolio"] --> idx_listing_seller_created',
        '  Q2 --> idx_rating_rated',
        '  Q3["Q3: GET /listings/{id}/offers"] --> idx_offer_listing_status',
        '  Q4["Q4: NotificationBell"] --> idx_notification_recipient_read',
        '  Q5["Q5: Avg rating"] --> idx_rating_rated',
        '  Q6["Q6: GET /transactions"] --> idx_transaction_seller',
        '  Q6 --> idx_transaction_buyer',
        '  Q7["Q7: GET /wishrequests"] --> idx_wishrequest_status_created',
        '  Q8["Q8: GET /admin/audit-log"] --> idx_auditlog_timestamp',
        "```",
        "",
    ]

    # ------------------------------------------------------------------ 5. Charts
    timing_chart_rel  = os.path.join(charts_rel, "timing.png").replace("\\", "/")
    rows_chart_rel    = os.path.join(charts_rel, "rows_examined.png").replace("\\", "/")
    speedup_chart_rel = os.path.join(charts_rel, "speedup.png").replace("\\", "/")

    lines += [
        "---",
        "",
        "## 5. Benchmark Charts",
        "",
        "### Execution time (avg ms) — before vs after",
        "",
        f"![Execution time comparison]({timing_chart_rel})",
        "",
        "### Rows examined (EXPLAIN estimate) — before vs after",
        "",
        f"![Rows examined comparison]({rows_chart_rel})",
        "",
        "### Percentage speedup per query",
        "",
        f"![Speedup percentage]({speedup_chart_rel})",
        "",
    ]

    # ------------------------------------------------------------------ 6. Per-query
    lines += [
        "---",
        "",
        "## 6. Per-Query Analysis",
        "",
    ]

    for b, a in zip(before, after):
        qid   = b["id"]
        name  = b["name"]
        query = b["query"]
        endpoint = b["endpoint"]
        hint  = b["index_hint"]

        # Section header anchor: "q1-active-listings-ordered-by-date"
        anchor_name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        lines += [
            f"### {qid}: {name}",
            "",
            f"**API endpoint:** `{endpoint}`  ",
            f"**Index(es) applied:** `{hint}`",
            "",
            "```sql",
            query,
            "```",
            "",
        ]

        # EXPLAIN before
        b_explain = b["explain"]
        a_explain = a["explain"]
        b_type = (b_explain[0].get("type") or b_explain[0].get("Type") or "") if b_explain else ""
        a_type = (a_explain[0].get("type") or a_explain[0].get("Type") or "") if a_explain else ""

        lines += [
            "#### EXPLAIN plan — Before indexes",
            "",
            _explain_table_md(b_explain),
            "",
            "#### EXPLAIN plan — After indexes",
            "",
            _explain_table_md(a_explain),
            "",
            "#### Access plan interpretation",
            "",
            _access_type_note(b_type, a_type),
            "",
            "#### Timing statistics",
            "",
            _timing_table_md(b["timing"], a["timing"]),
            "",
        ]

    # ------------------------------------------------------------------ 7. Conclusion
    lines += [
        "---",
        "",
        "## 7. Conclusion & Recommendations",
        "",
        f"Applying **{index_count} custom indexes** to `CampusTradingB` reduced the combined "
        f"average execution time of the {len(QUERIES)} benchmark queries from "
        f"**{total_b_avg:.3f} ms** to **{total_a_avg:.3f} ms** — "
        f"an overall improvement of **{overall_speedup:.1f}%**.",
        "",
        "### Most impactful indexes",
        "",
    ]

    ranked = sorted(
        zip(before, after),
        key=lambda pair: (pair[0]["timing"]["avg"] - pair[1]["timing"]["avg"]) / pair[0]["timing"]["avg"]
                         if pair[0]["timing"]["avg"] > 0 else 0,
        reverse=True,
    )
    lines += [
        "| Rank | Query | Index(es) | Avg before (ms) | Avg after (ms) | Speedup |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for rank, (b, a) in enumerate(ranked, 1):
        sp = ((b["timing"]["avg"] - a["timing"]["avg"]) / b["timing"]["avg"] * 100) if b["timing"]["avg"] > 0 else 0
        lines.append(
            f"| {rank} | {b['id']}: {b['name']} | `{b['index_hint']}` | "
            f"{b['timing']['avg']:.3f} | {a['timing']['avg']:.3f} | {sp:+.1f}% |"
        )

    lines += [
        "",
        "### Key observations",
        "",
        "- **Composite indexes outperform single-column indexes** when queries filter on "
        "  multiple columns simultaneously (e.g., `Status + CreatedDate` for Q1, "
        "  `RecipientID + IsRead` for Q4).",
        "- **InnoDB already maintains a clustered index** on every primary key. "
        "  The indexes added here complement that by covering the most common "
        "  secondary access paths.",
        "- **OR predicates** (Q6: `SellerID=? OR BuyerID=?`) require two separate indexes "
        "  to allow the optimizer to perform an index union rather than a full table scan.",
        "- **ORDER BY columns** benefit from being included as the last column of a "
        "  composite index so MySQL can satisfy the sort from the index itself, "
        "  eliminating a filesort step.",
        "",
        "### Recommendations",
        "",
        "1. **Monitor slow-query log** (`long_query_time = 0.1`) in production to catch "
        "   regressions early.",
        "2. **Re-evaluate indexes** after major feature additions that introduce new query "
        "   patterns.",
        "3. **Avoid over-indexing** — every additional index slightly slows `INSERT`/`UPDATE`/`DELETE` "
        "   operations because InnoDB must maintain all indexes on each write. The 16 indexes "
        "   added here target the highest-traffic read paths only.",
        "4. Consider **covering indexes** for the browse query (Q1) if profiling shows that "
        "   the full `SELECT *` is a bottleneck — include frequently projected columns in "
        "   the index itself.",
        "",
        "---",
        "",
        "_Report generated by `scripts/benchmark.py`_",
        "",
    ]

    with open(out_path, "w") as fh:
        fh.write("\n".join(lines))
    print(f"  Report written → {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Campus Trading App — SQL Index Benchmark"
    )
    parser.add_argument("--host",        default="127.0.0.1")
    parser.add_argument("--port",        type=int, default=3306)
    parser.add_argument("--user",        default="root")
    parser.add_argument("--password",    default="root")
    parser.add_argument("--db",          default="CampusTradingB")
    parser.add_argument("--indexes-sql", default=str(Path(__file__).parent.parent / "sql" / "indexes.sql"))
    parser.add_argument("--charts-dir",  default=str(Path(__file__).parent / "charts"))
    parser.add_argument("--report-out",  default=str(Path(__file__).parent.parent / "report" / "README.md"))
    parser.add_argument("--runs",        type=int, default=10)
    parser.add_argument("--skip-seed",   action="store_true")
    parser.add_argument("--skip-drop",   action="store_true")
    args = parser.parse_args()

    charts_dir = Path(args.charts_dir)
    charts_dir.mkdir(parents=True, exist_ok=True)
    Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Campus Trading App — SQL Index Performance Benchmark")
    print(f"{'='*60}")
    print(f"  Host:   {args.host}:{args.port}")
    print(f"  DB:     {args.db}")
    print(f"  Runs:   {args.runs} per query per phase")
    print(f"  Charts: {charts_dir}")
    print(f"  Report: {args.report_out}")
    print()

    conn = get_connection(args)
    print("  Connected to MySQL.")

    # Seed
    if not args.skip_seed:
        print("\n[1/5] Seeding test data …")
        seed_data(conn)
    else:
        print("\n[1/5] Seed skipped.")

    # Phase 1 — no indexes
    print("\n[2/5] Phase 1: Benchmarking WITHOUT indexes …")
    if not args.skip_drop:
        drop_custom_indexes(conn)
    before = run_phase(conn, "Before", args.runs)

    # Apply indexes
    print(f"\n[3/5] Applying indexes from {args.indexes_sql} …")
    index_count = apply_indexes(conn, args.indexes_sql)

    # Phase 2 — with indexes
    print("\n[4/5] Phase 2: Benchmarking WITH indexes …")
    after = run_phase(conn, "After", args.runs)

    # Charts + README
    print("\n[5/5] Generating charts and report …")
    save_timing_chart(before, after,  charts_dir / "timing.png")
    save_rows_chart(before, after,    charts_dir / "rows_examined.png")
    save_speedup_chart(before, after, charts_dir / "speedup.png")
    generate_readme(before, after, charts_dir, args.report_out, index_count, args.runs)

    conn.close()

    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"  Charts → {charts_dir}/")
    print(f"  Report → {args.report_out}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
