"""Phase 1 smoke tests for transaction lifecycle in Module A."""

from __future__ import annotations

import tempfile
import unittest

from database import DatabaseManager


class TestPhase1Transactions(unittest.TestCase):
    def _log_case(self, title: str) -> None:
        print(f"\n[Phase 1] {title}")

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        wal_path = f"{self.tmpdir.name}/wal.log"
        self.dbm = DatabaseManager(wal_path=wal_path)

        ok, _ = self.dbm.create_database("campus")
        self.assertTrue(ok)

        schema = {
            "OfferID": int,
            "ListingID": int,
            "BuyerID": int,
            "OfferStatus": str,
            "AgreedPrice": float,
        }
        ok, msg = self.dbm.create_table(
            "campus",
            "Offer",
            schema,
            search_key="OfferID",
        )
        self.assertTrue(ok, msg)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_insert_commit_persists(self) -> None:
        self._log_case("Insert + Commit -> row persists")
        tx = self.dbm.begin_transaction()

        ok, msg = self.dbm.tx_insert(
            tx,
            "campus",
            "Offer",
            {
                "OfferID": 1,
                "ListingID": 101,
                "BuyerID": 7,
                "OfferStatus": "Submitted",
                "AgreedPrice": 0.0,
            },
        )
        self.assertTrue(ok, msg)

        ok, msg = self.dbm.commit_transaction(tx)
        self.assertTrue(ok, msg)

        table, _ = self.dbm.get_table("campus", "Offer")
        self.assertIsNotNone(table)
        self.assertIsNotNone(table.get(1))

    def test_insert_rollback_undoes_change(self) -> None:
        self._log_case("Insert + Rollback -> row removed")
        tx = self.dbm.begin_transaction()

        ok, msg = self.dbm.tx_insert(
            tx,
            "campus",
            "Offer",
            {
                "OfferID": 2,
                "ListingID": 102,
                "BuyerID": 9,
                "OfferStatus": "Submitted",
                "AgreedPrice": 0.0,
            },
        )
        self.assertTrue(ok, msg)

        ok, msg = self.dbm.rollback_transaction(tx)
        self.assertTrue(ok, msg)

        table, _ = self.dbm.get_table("campus", "Offer")
        self.assertIsNotNone(table)
        self.assertIsNone(table.get(2))

    def test_update_rollback_restores_before_image(self) -> None:
        self._log_case("Update + Rollback -> before-image restored")
        table, _ = self.dbm.get_table("campus", "Offer")
        self.assertIsNotNone(table)

        ok, _ = table.insert(
            {
                "OfferID": 3,
                "ListingID": 103,
                "BuyerID": 5,
                "OfferStatus": "Submitted",
                "AgreedPrice": 0.0,
            }
        )
        self.assertTrue(ok)

        tx = self.dbm.begin_transaction()

        ok, msg = self.dbm.tx_update(
            tx,
            "campus",
            "Offer",
            3,
            {
                "OfferID": 3,
                "ListingID": 103,
                "BuyerID": 5,
                "OfferStatus": "Accepted",
                "AgreedPrice": 45.0,
            },
        )
        self.assertTrue(ok, msg)

        ok, msg = self.dbm.rollback_transaction(tx)
        self.assertTrue(ok, msg)

        row = table.get(3)
        self.assertIsNotNone(row)
        self.assertEqual(row["OfferStatus"], "Submitted")
        self.assertEqual(row["AgreedPrice"], 0.0)


if __name__ == "__main__":
    unittest.main()
