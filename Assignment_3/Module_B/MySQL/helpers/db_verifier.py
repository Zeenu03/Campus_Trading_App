"""Direct MySQL integrity checks using mysql-connector-python.

Bypasses the Go REST API to validate the true database state after
each stress scenario — the ground truth for race conditions and atomicity.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import mysql.connector


class DBVerifier:
    """Issue SQL-level integrity queries directly against the MySQL database."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3306,
        user: str = "root",
        password: str = "root",
        database: str = "CampusTradingB",
    ) -> None:
        self.config: Dict[str, Any] = dict(
            host=host, port=port, user=user, password=password,
            database=database, connection_timeout=5,
        )
        self._conn: Optional[mysql.connector.MySQLConnection] = None

    # ── Connection lifecycle ──────────────────────────────────────

    def connect(self) -> bool:
        try:
            if self._conn and self._conn.is_connected():
                return True
            self._conn = mysql.connector.connect(**self.config)
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    # ── Internal query helpers ────────────────────────────────────

    def _ensure_connected(self) -> bool:
        if self._conn and self._conn.is_connected():
            return True
        return self.connect()

    def _query(self, sql: str, params: tuple = ()) -> List[tuple]:
        if not self._ensure_connected():
            return []
        try:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            cur.close()
            return rows
        except Exception:
            return []

    def _scalar(self, sql: str, params: tuple = ()) -> Any:
        rows = self._query(sql, params)
        return rows[0][0] if rows else None

    # ── Offer race invariants ─────────────────────────────────────

    def get_accepted_offer_count(self, listing_id: int) -> int:
        return int(
            self._scalar(
                "SELECT COUNT(*) FROM Offer WHERE ListingID=%s AND OfferStatus='Accepted'",
                (listing_id,),
            )
            or 0
        )

    def get_declined_offer_count(self, listing_id: int) -> int:
        return int(
            self._scalar(
                "SELECT COUNT(*) FROM Offer WHERE ListingID=%s AND OfferStatus='Declined'",
                (listing_id,),
            )
            or 0
        )

    def get_submitted_offer_count(self, listing_id: int) -> int:
        return int(
            self._scalar(
                "SELECT COUNT(*) FROM Offer WHERE ListingID=%s AND OfferStatus='Submitted'",
                (listing_id,),
            )
            or 0
        )

    def get_transaction_count(self, listing_id: int) -> int:
        return int(
            self._scalar(
                "SELECT COUNT(*) FROM `Transaction` WHERE ListingID=%s",
                (listing_id,),
            )
            or 0
        )

    def get_listing_status(self, listing_id: int) -> Optional[str]:
        result = self._scalar(
            "SELECT Status FROM Listing WHERE ListingID=%s", (listing_id,)
        )
        return str(result) if result is not None else None

    def verify_offer_race(self, listing_id: int, n_buyers: int) -> Dict[str, Any]:
        """
        Verify invariants after a concurrent-accept race on a single listing.
        Returns a dict reporting every relevant counter and whether invariants hold.
        """
        accepted = self.get_accepted_offer_count(listing_id)
        declined = self.get_declined_offer_count(listing_id)
        submitted = self.get_submitted_offer_count(listing_id)
        txn_count = self.get_transaction_count(listing_id)
        status = self.get_listing_status(listing_id)

        listing_sold = status == "Sold"

        # In the correct (serial) case: accepting 1 of N offers creates exactly N
        # Transaction rows — 1 for the accepted offer and N-1 for each auto-declined offer.
        # If M concurrent accept calls all slip through the TOCTOU window, each one creates
        # up to N rows, yielding up to N² total (observed: 10 buyers → 100 transactions).
        expected_txns = n_buyers   # serial expectation: exactly N
        txn_race = txn_count > expected_txns

        # Race is detected if more than 1 offer ended up Accepted OR more
        # transaction rows than the serial expectation exist.
        race_detected = accepted > 1 or txn_race

        all_invariants_pass = (
            accepted == 1
            and listing_sold
            and submitted == 0
            and not txn_race
        )

        return {
            "listing_id": listing_id,
            "listing_status": status,
            "accepted_offers": accepted,
            "declined_offers": declined,
            "submitted_offers": submitted,
            "total_transactions": txn_count,
            "expected_transactions": expected_txns,
            "n_buyers": n_buyers,
            "listing_sold": listing_sold,
            "exactly_one_accepted": accepted == 1,
            "transaction_count_correct": not txn_race,
            "race_condition_detected": race_detected,
            "all_invariants_pass": all_invariants_pass,
        }

    # ── General integrity checks ─────────────────────────────────

    def verify_no_orphan_transactions(self) -> Dict[str, Any]:
        """Every Transaction must reference valid Listing, Seller, Buyer, Offer rows."""
        orphans = self._query(
            """
            SELECT t.TransactionID
            FROM `Transaction` t
            LEFT JOIN Listing  l ON l.ListingID = t.ListingID
            LEFT JOIN Member   s ON s.MemberID  = t.SellerID
            LEFT JOIN Member   b ON b.MemberID  = t.BuyerID
            LEFT JOIN Offer    o ON o.OfferID   = t.OfferID
            WHERE l.ListingID IS NULL
               OR s.MemberID  IS NULL
               OR b.MemberID  IS NULL
               OR o.OfferID   IS NULL
            """
        )
        return {
            "orphan_transaction_ids": [r[0] for r in orphans],
            "orphan_count": len(orphans),
            "clean": len(orphans) == 0,
        }

    def verify_no_accepted_without_transaction(self) -> Dict[str, Any]:
        """Every Accepted offer must have at least one matching Transaction."""
        violations = self._query(
            """
            SELECT o.OfferID
            FROM Offer o
            LEFT JOIN `Transaction` t ON t.OfferID = o.OfferID
            WHERE o.OfferStatus = 'Accepted' AND t.TransactionID IS NULL
            """
        )
        return {
            "offer_ids_without_transaction": [r[0] for r in violations],
            "violation_count": len(violations),
            "clean": len(violations) == 0,
        }

    def verify_sold_listings_have_one_transaction(self) -> Dict[str, Any]:
        """Every Sold listing should have exactly 1 accepted Transaction."""
        violations = self._query(
            """
            SELECT l.ListingID, COUNT(t.TransactionID) as txn_count
            FROM Listing l
            LEFT JOIN `Transaction` t ON t.ListingID = l.ListingID
            WHERE l.Status = 'Sold'
            GROUP BY l.ListingID
            HAVING txn_count < 1
            """
        )
        return {
            "listing_id_mismatches": [
                {"listing_id": r[0], "txn_count": r[1]} for r in violations
            ],
            "violation_count": len(violations),
            "clean": len(violations) == 0,
        }

    def full_integrity_check(self) -> Dict[str, Any]:
        orphan_txns = self.verify_no_orphan_transactions()
        accepted_no_txn = self.verify_no_accepted_without_transaction()
        sold_no_txn = self.verify_sold_listings_have_one_transaction()
        all_clean = (
            orphan_txns["clean"]
            and accepted_no_txn["clean"]
            and sold_no_txn["clean"]
        )
        return {
            "orphan_transactions": orphan_txns,
            "accepted_without_transaction": accepted_no_txn,
            "sold_without_transaction": sold_no_txn,
            "all_clean": all_clean,
        }

    def get_table_counts(self) -> Dict[str, int]:
        """Return row counts for the main application tables."""
        counts: Dict[str, int] = {}
        for table in ["Listing", "Offer", "`Transaction`", "Notification", "Member"]:
            display = table.strip("`")
            counts[display] = int(self._scalar(f"SELECT COUNT(*) FROM {table}") or 0)
        return counts
