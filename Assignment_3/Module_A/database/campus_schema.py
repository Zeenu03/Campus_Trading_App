"""Campus Trading schema definitions, seed profile, and setup helpers.

Provides the canonical table schemas for the campus trading application,
a SeedProfile for repeatable test and stress data, and helpers to install
schemas and seed deterministic rows into any DatabaseManager instance.

This module intentionally lives in database/ so both scripts/ and tests/
can import it without path gymnastics, but it is NOT part of the engine's
public API — the engine (DatabaseManager, WAL, etc.) is schema-neutral.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .db_manager import DatabaseManager


# ---------------------------------------------------------------------------
# Table names (canonical ordering)
# ---------------------------------------------------------------------------

CAMPUS_TABLE_NAMES: Tuple[str, ...] = ("Offer", "Listing", "Transaction", "Notification")


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

OFFER_SCHEMA: Dict[str, type] = {
    "OfferID": int,
    "ListingID": int,
    "BuyerID": int,
    "OfferedPrice": float,
    "AgreedPrice": float,
    "OfferStatus": str,
    "Reason": str,
    "ResponseDate": str,
}

LISTING_SCHEMA: Dict[str, type] = {
    "ListingID": int,
    "SellerID": int,
    "Status": str,
    "AskingPrice": float,
    "LastModifiedDate": str,
}

TRANSACTION_SCHEMA: Dict[str, type] = {
    "TransactionID": int,
    "ListingID": int,
    "SellerID": int,
    "BuyerID": int,
    "OfferID": int,
    "AgreedPrice": float,
    "Status": str,
    "CreatedDate": str,
}

NOTIFICATION_SCHEMA: Dict[str, type] = {
    "NotificationID": int,
    "RecipientID": int,
    "NotificationType": str,
    "Title": str,
    "Message": str,
    "RelatedListingID": int,
    "RelatedOfferID": int,
    "RelatedTransactionID": int,
    "CreatedDate": str,
}

_TABLE_SPECS: Tuple[Tuple[str, Dict[str, type], str], ...] = (
    ("Offer", OFFER_SCHEMA, "OfferID"),
    ("Listing", LISTING_SCHEMA, "ListingID"),
    ("Transaction", TRANSACTION_SCHEMA, "TransactionID"),
    ("Notification", NOTIFICATION_SCHEMA, "NotificationID"),
)


# ---------------------------------------------------------------------------
# Seed profile
# ---------------------------------------------------------------------------

@dataclass
class SeedProfile:
    """Deterministic seed parameters for repeatable stress and ACID tests.

    All IDs are small fixed integers so test runs and WAL logs are easy to read.
    """
    db_name: str = "campus"
    seller_id: int = 10
    buyer_ids: List[int] = field(default_factory=lambda: [101, 102, 103])
    listing_base_id: int = 1000
    offer_base_id: int = 2000
    listings_per_run: int = 3


DEFAULT_PROFILE: SeedProfile = SeedProfile()


# ---------------------------------------------------------------------------
# Schema installation
# ---------------------------------------------------------------------------

def install_campus_schema(
    dbm: DatabaseManager,
    profile: SeedProfile = DEFAULT_PROFILE,
) -> None:
    """Create the campus logical database and all four tables in *dbm*.

    Safe to call on a fresh DatabaseManager. Raises RuntimeError on failure.
    Used both for initial bootstrap and for post-crash schema reinstall
    before WAL recovery replay.
    """
    ok, msg = dbm.create_database(profile.db_name)
    if not ok:
        raise RuntimeError(f"Failed to create database '{profile.db_name}': {msg}")

    for table_name, schema, search_key in _TABLE_SPECS:
        ok, msg = dbm.create_table(profile.db_name, table_name, schema, search_key=search_key)
        if not ok:
            raise RuntimeError(f"Failed to create table '{table_name}': {msg}")


# ---------------------------------------------------------------------------
# Deterministic seed data
# ---------------------------------------------------------------------------

def seed_campus_tables(
    dbm: DatabaseManager,
    profile: SeedProfile = DEFAULT_PROFILE,
) -> None:
    """Insert deterministic listings and offers based on *profile*.

    Creates ``profile.listings_per_run`` listings, each with one offer per
    buyer in ``profile.buyer_ids``. Offer IDs are derived from
    ``offer_base_id`` so they are repeatable and easy to reference in tests.

    Note: rows are inserted directly into the B+ Tree (not WAL-logged). This
    is intentional for stress/test runs where WAL seeding overhead is
    unwanted. For demos that need full durability from WAL replay, use
    ``seed_campus_tables_transactional`` instead.
    """
    listing_table, msg = dbm.get_table(profile.db_name, "Listing")
    if listing_table is None:
        raise RuntimeError(f"Cannot seed listings: {msg}")

    offer_table, msg = dbm.get_table(profile.db_name, "Offer")
    if offer_table is None:
        raise RuntimeError(f"Cannot seed offers: {msg}")

    for i in range(profile.listings_per_run):
        listing_id = profile.listing_base_id + i
        ok, msg = listing_table.insert({
            "ListingID": listing_id,
            "SellerID": profile.seller_id,
            "Status": "Listed",
            "AskingPrice": float(100 + i * 10),
            "LastModifiedDate": "",
        })
        if not ok:
            raise RuntimeError(f"Seed listing {listing_id} failed: {msg}")

        for j, buyer_id in enumerate(profile.buyer_ids):
            offer_id = profile.offer_base_id + i * len(profile.buyer_ids) + j
            ok, msg = offer_table.insert({
                "OfferID": offer_id,
                "ListingID": listing_id,
                "BuyerID": buyer_id,
                "OfferedPrice": float(90 + j * 5),
                "AgreedPrice": 0.0,
                "OfferStatus": "Submitted",
                "Reason": "",
                "ResponseDate": "",
            })
            if not ok:
                raise RuntimeError(f"Seed offer {offer_id} failed: {msg}")


def seed_campus_tables_transactional(
    dbm: DatabaseManager,
    profile: SeedProfile = DEFAULT_PROFILE,
) -> None:
    """Insert deterministic listings and offers via committed WAL transactions.

    Identical data to ``seed_campus_tables`` but every row is inserted through
    ``DatabaseManager.tx_insert`` inside a single committed transaction, so the
    WAL records each change. This is required when the seeded state must survive
    a simulated crash and be recovered via ``RecoveryManager.recover_into`` —
    i.e. for the Durability section of ACID demos.

    Stress / concurrency tests should continue to use the non-transactional
    ``seed_campus_tables`` (lower overhead, no WAL growth).
    """
    rows: List[tuple] = []
    for i in range(profile.listings_per_run):
        listing_id = profile.listing_base_id + i
        rows.append(("Listing", {
            "ListingID": listing_id,
            "SellerID": profile.seller_id,
            "Status": "Listed",
            "AskingPrice": float(100 + i * 10),
            "LastModifiedDate": "",
        }))
        for j, buyer_id in enumerate(profile.buyer_ids):
            offer_id = profile.offer_base_id + i * len(profile.buyer_ids) + j
            rows.append(("Offer", {
                "OfferID": offer_id,
                "ListingID": listing_id,
                "BuyerID": buyer_id,
                "OfferedPrice": float(90 + j * 5),
                "AgreedPrice": 0.0,
                "OfferStatus": "Submitted",
                "Reason": "",
                "ResponseDate": "",
            }))

    def _seed_tx(tx_id: str) -> None:
        for table_name, row in rows:
            ok, msg = dbm.tx_insert(tx_id, profile.db_name, table_name, row)
            if not ok:
                raise RuntimeError(f"Transactional seed of '{table_name}' failed: {msg}")

    ok, msg, _ = dbm.run_transaction(_seed_tx)
    if not ok:
        raise RuntimeError(f"seed_campus_tables_transactional failed: {msg}")
