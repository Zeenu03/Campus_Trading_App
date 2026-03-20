"""
Standalone DatabaseManager demo for Campus Trading listings.

Creates dummy data, forces a deeper B+ Tree (target height >= 4), performs
CRUD + range query, and generates a tree visualization.

Run:
    python listing_db_manager_demo.py
"""

from __future__ import annotations

import os
import random
from typing import Tuple

from database import DatabaseManager


def _make_listing_record(listing_id: int, rng: random.Random) -> dict:
    categories = ["Books", "Electronics", "Furniture", "Stationery", "Sports"]
    category = categories[listing_id % len(categories)]
    return {
        "listing_id": listing_id,
        "title": f"Dummy Listing {listing_id}",
        "category": category,
        "price": round(rng.uniform(5.0, 500.0), 2),
        "seller_member_id": rng.randint(1, 120),
    }


def build_demo_environment(order: int = 6, target_height: int = 4, seed: int = 42) -> Tuple[DatabaseManager, object]:
    """Build a demo DB environment and return (manager, listing_table)."""
    rng = random.Random(seed)

    db_manager = DatabaseManager()
    ok, msg = db_manager.create_database("campus_trading_demo")
    print(f"create_database -> {ok}, {msg}")

    listing_schema = {
        "listing_id": int,
        "title": str,
        "category": str,
        "price": float,
        "seller_member_id": int,
    }

    ok, msg = db_manager.create_table(
        "campus_trading_demo",
        "listing",
        listing_schema,
        order=order,
        search_key="listing_id",
    )
    print(f"create_table -> {ok}, {msg}")

    listing_table, msg = db_manager.get_table("campus_trading_demo", "listing")
    if listing_table is None:
        raise RuntimeError(msg)

    next_id = 1000
    while listing_table.data.get_height() < target_height:
        ok, insert_msg = listing_table.insert(_make_listing_record(next_id, rng))
        if not ok:
            raise RuntimeError(insert_msg)
        next_id += 1

    print(f"Inserted records: {len(listing_table)}")
    print(f"B+ Tree height: {listing_table.data.get_height()}")

    # CRUD demo
    print("\nCRUD demo")
    target_id = 1020
    print("search:", listing_table.get(target_id))

    updated = _make_listing_record(target_id, rng)
    updated["title"] = "Updated Dummy Listing 1020"
    ok, msg = listing_table.update(target_id, updated)
    print(f"update -> {ok}, {msg}")

    ok, msg = listing_table.delete(1030)
    print(f"delete -> {ok}, {msg}")

    # Range query demo
    print("\nRange query (listing_id 1010 to 1025)")
    rows = listing_table.range_query(1010, 1025)
    print(f"rows returned: {len(rows)}")
    for key, value in rows[:8]:
        print(f"  {key} -> {value['title']} (${value['price']})")

    # Visualization
    print("\nGenerating visualization...")
    dot = listing_table.data.visualize_tree()
    if dot:
        os.makedirs("visualizations/tree_outputs", exist_ok=True)
        output_path = "visualizations/tree_outputs/db_manager_listing_dummy_tree"
        dot.render(output_path, format="png", cleanup=True)
        print(f"saved: {output_path}.png")
    else:
        print("Graphviz not available. Install with: pip install graphviz")

    return db_manager, listing_table


if __name__ == "__main__":
    build_demo_environment(order=6, target_height=4, seed=42)
