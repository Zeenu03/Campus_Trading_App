"""
Performance Benchmarking Script
Campus Trading Application - Module B (Phase 7)

Measures query execution time BEFORE and AFTER applying indexes.
Saves results to benchmark_results.json and generates comparison charts.

Usage:
    python benchmarks/run_benchmark.py

Prerequisites:
    - Database populated with seed data (04_seed_data.sql)
    - App running or db connection available
    - matplotlib, pandas installed
"""

import json
import time
import os
import sys

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

# ----------------------------------------------------------------
# Test queries (from MODULE_B_DESIGN_DOC.md §11.2)
# ----------------------------------------------------------------
BENCHMARK_QUERIES = [
    {
        "id": "Q1",
        "description": "Listings by category + status (Browse)",
        "sql": "SELECT * FROM Listing WHERE CategoryID = 2 AND Status = 'Listed' ORDER BY CreatedDate DESC"
    },
    {
        "id": "Q2",
        "description": "Listings by seller (My Listings)",
        "sql": "SELECT * FROM Listing WHERE SellerID = 1 AND Status = 'Listed'"
    },
    {
        "id": "Q3",
        "description": "Offers for a listing with buyer info",
        "sql": """SELECT o.*, m.Name AS BuyerName
                  FROM Offer o
                  JOIN Member m ON o.BuyerID = m.MemberID
                  WHERE o.ListingID = 1 AND o.OfferStatus = 'Submitted'"""
    },
    {
        "id": "Q4",
        "description": "Unread notifications for a user",
        "sql": """SELECT * FROM Notification
                  WHERE RecipientID = 1 AND IsRead = FALSE
                  ORDER BY CreatedDate DESC"""
    },
    {
        "id": "Q5",
        "description": "Price range query (₹100–₹1000)",
        "sql": "SELECT * FROM Listing WHERE AskingPrice BETWEEN 100 AND 1000 AND Status = 'Listed'"
    },
    {
        "id": "Q6",
        "description": "Member average rating",
        "sql": "SELECT AVG(Stars), COUNT(*) FROM Rating WHERE RatedID = 7"
    },
    {
        "id": "Q7",
        "description": "Transaction history (seller)",
        "sql": """SELECT t.*, l.Title
                  FROM `Transaction` t JOIN Listing l ON t.ListingID = l.ListingID
                  WHERE t.SellerID = 7
                  ORDER BY t.TransactionDate DESC"""
    },
    {
        "id": "Q8",
        "description": "Messages in thread",
        "sql": """SELECT m.*, mem.Name AS SenderName
                  FROM Message m JOIN Member mem ON m.SenderID = mem.MemberID
                  WHERE m.ThreadID = 1
                  ORDER BY m.SentDate"""
    },
]

ITERATIONS = 10  # How many times to run each query (average)


def run_query_timed(connection, sql):
    """Execute a query ITERATIONS times and return avg time + EXPLAIN output."""
    times = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        try:
            connection.execute(text(sql))
        except Exception:
            pass  # table may not have data for all queries
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)

    avg_ms = round(sum(times) / len(times), 4)
    min_ms = round(min(times), 4)
    max_ms = round(max(times), 4)

    # EXPLAIN output
    explain_rows = []
    try:
        result = connection.execute(text(f"EXPLAIN {sql}"))
        for row in result:
            explain_rows.append(dict(row._mapping))
    except Exception as e:
        explain_rows = [{"error": str(e)}]

    return avg_ms, min_ms, max_ms, explain_rows


def run_phase(connection, label):
    """Run all benchmark queries and return results."""
    phase_results = []
    for q in BENCHMARK_QUERIES:
        print(f"  [{label}] Running {q['id']}: {q['description'][:50]}...", end=" ", flush=True)
        avg, mn, mx, explain = run_query_timed(connection, q['sql'])
        print(f"{avg:.3f} ms")
        phase_results.append({
            "id": q["id"],
            "description": q["description"],
            "avg_ms": avg,
            "min_ms": mn,
            "max_ms": mx,
            "explain": explain
        })
    return phase_results


def save_explain_outputs(results_before, results_after):
    """Save EXPLAIN outputs to individual files."""
    out_dir = os.path.join(os.path.dirname(__file__), "explain_outputs")
    os.makedirs(out_dir, exist_ok=True)

    for q_before, q_after in zip(results_before, results_after):
        qid = q_before["id"]
        fname = os.path.join(out_dir, f"{qid}_explain.txt")
        with open(fname, "w") as f:
            f.write(f"Query: {qid} — {q_before['description']}\n")
            f.write("=" * 70 + "\n\n")
            f.write("BEFORE INDEXES:\n")
            for row in q_before["explain"]:
                f.write(f"  {row}\n")
            f.write("\nAFTER INDEXES:\n")
            for row in q_after["explain"]:
                f.write(f"  {row}\n")
            f.write("\n")
            f.write(f"Avg time BEFORE: {q_before['avg_ms']:.3f} ms\n")
            f.write(f"Avg time AFTER:  {q_after['avg_ms']:.3f} ms\n")
            improvement = q_before['avg_ms'] / q_after['avg_ms'] if q_after['avg_ms'] > 0 else float('inf')
            f.write(f"Improvement:     {improvement:.1f}x\n")
    print(f"EXPLAIN outputs saved to {out_dir}/")


def generate_charts(results_before, results_after, output_dir):
    """Generate bar chart comparing before/after times."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not installed — skipping chart generation")
        return

    labels = [r["id"] for r in results_before]
    before_times = [r["avg_ms"] for r in results_before]
    after_times = [r["avg_ms"] for r in results_after]
    improvements = [b / a if a > 0 else 0 for b, a in zip(before_times, after_times)]

    x = np.arange(len(labels))
    width = 0.35

    # Chart 1: Side-by-side response times
    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar(x - width/2, before_times, width, label='Without Indexes', color='#e74c3c', alpha=0.85)
    bars2 = ax.bar(x + width/2, after_times,  width, label='With Indexes',    color='#27ae60', alpha=0.85)

    ax.set_xlabel('Query', fontsize=12)
    ax.set_ylabel('Avg Execution Time (ms)', fontsize=12)
    ax.set_title('Query Performance: Before vs After Indexes\nCampus Trading — Module B', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)

    for bar in bars1:
        ax.annotate(f'{bar.get_height():.2f}',
                    xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
    for bar in bars2:
        ax.annotate(f'{bar.get_height():.2f}',
                    xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    chart1_path = os.path.join(output_dir, 'benchmark_comparison.png')
    plt.savefig(chart1_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Chart saved: {chart1_path}")

    # Chart 2: Speedup factor
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    colors = ['#27ae60' if imp >= 2 else '#f39c12' if imp >= 1.2 else '#e74c3c' for imp in improvements]
    bars3 = ax2.bar(labels, improvements, color=colors, alpha=0.85)
    ax2.axhline(y=1, color='gray', linestyle='--', alpha=0.5, label='No improvement (1x)')
    ax2.set_xlabel('Query', fontsize=12)
    ax2.set_ylabel('Speedup Factor (x times faster)', fontsize=12)
    ax2.set_title('Index Speedup per Query\nCampus Trading — Module B', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    for bar, imp in zip(bars3, improvements):
        ax2.annotate(f'{imp:.1f}x',
                     xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=9, fontweight='bold')
    plt.tight_layout()
    chart2_path = os.path.join(output_dir, 'speedup_chart.png')
    plt.savefig(chart2_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Chart saved: {chart2_path}")


def run_benchmarks():
    """Main benchmark runner."""
    app = create_app()
    output_dir = os.path.dirname(os.path.abspath(__file__))

    with app.app_context():
        with db.engine.connect() as conn:

            # ---- PHASE A: Without indexes ----
            print("\n" + "="*60)
            print("PHASE A: Running queries WITHOUT indexes")
            print("="*60)
            # Drop indexes first
            index_sql_path = os.path.join(os.path.dirname(output_dir), 'sql', '05_drop_indexes.sql')
            if os.path.exists(index_sql_path):
                try:
                    with open(index_sql_path) as f:
                        for stmt in f.read().split(';'):
                            stmt = stmt.strip()
                            if stmt and not stmt.startswith('--') and not stmt.startswith('USE'):
                                try:
                                    conn.execute(text(stmt))
                                except Exception:
                                    pass
                    conn.commit()
                    print("Indexes dropped.")
                except Exception as e:
                    print(f"Could not drop indexes (may not exist yet): {e}")

            results_before = run_phase(conn, "NO INDEX")

            # ---- PHASE B: Apply indexes ----
            print("\n" + "="*60)
            print("PHASE B: Applying indexes...")
            print("="*60)
            create_sql_path = os.path.join(os.path.dirname(output_dir), 'sql', '03_create_indexes.sql')
            if os.path.exists(create_sql_path):
                with open(create_sql_path) as f:
                    for stmt in f.read().split(';'):
                        stmt = stmt.strip()
                        if stmt and not stmt.startswith('--') and not stmt.startswith('USE'):
                            try:
                                conn.execute(text(stmt))
                            except Exception:
                                pass
                conn.commit()
                print("Indexes created.")

            print("\nRunning queries WITH indexes:")
            results_after = run_phase(conn, "WITH INDEX")

    # ---- Save results ----
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "iterations_per_query": ITERATIONS,
        "without_indexes": results_before,
        "with_indexes": results_after,
        "summary": [
            {
                "id": b["id"],
                "description": b["description"],
                "before_ms": b["avg_ms"],
                "after_ms": a["avg_ms"],
                "speedup": round(b["avg_ms"] / a["avg_ms"], 2) if a["avg_ms"] > 0 else None
            }
            for b, a in zip(results_before, results_after)
        ]
    }

    results_path = os.path.join(output_dir, 'benchmark_results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_path}")

    # ---- Print summary table ----
    print("\n" + "="*70)
    print(f"{'Query':<5} {'Description':<40} {'Before':>8} {'After':>8} {'Speedup':>8}")
    print("-"*70)
    for row in results["summary"]:
        speedup = f"{row['speedup']:.1f}x" if row['speedup'] else "N/A"
        print(f"{row['id']:<5} {row['description'][:40]:<40} {row['before_ms']:>7.3f}  {row['after_ms']:>7.3f}  {speedup:>7}")
    print("="*70)

    # ---- Save EXPLAIN outputs ----
    save_explain_outputs(results_before, results_after)

    # ---- Generate charts ----
    generate_charts(results_before, results_after, output_dir)

    print("\nBenchmarking complete!")


if __name__ == '__main__':
    run_benchmarks()
