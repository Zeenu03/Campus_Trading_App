"""Phase 4 tests for crash recovery REDO/UNDO replay."""

from __future__ import annotations

import tempfile
import unittest

from database import DatabaseManager, RecoveryManager


class TestPhase4RecoveryReplay(unittest.TestCase):
    def _log_case(self, title: str) -> None:
        print(f"\n[Phase 4] {title}")

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.wal_path = f"{self.tmpdir.name}/wal.log"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    @staticmethod
    def _prepare_offer_table(dbm: DatabaseManager) -> None:
        ok, _ = dbm.create_database("campus")
        assert ok
        schema = {
            "OfferID": int,
            "ListingID": int,
            "BuyerID": int,
            "OfferStatus": str,
            "AgreedPrice": float,
        }
        ok, msg = dbm.create_table("campus", "Offer", schema, search_key="OfferID")
        assert ok, msg

    def test_crash_before_commit_undo_incomplete_transaction(self) -> None:
        self._log_case("Crash before commit -> UNDO uncommitted row")
        dbm = DatabaseManager(wal_path=self.wal_path)
        self._prepare_offer_table(dbm)

        tx_id = dbm.begin_transaction()
        ok, msg = dbm.tx_insert(
            tx_id,
            "campus",
            "Offer",
            {
                "OfferID": 201,
                "ListingID": 900,
                "BuyerID": 3001,
                "OfferStatus": "Submitted",
                "AgreedPrice": 0.0,
            },
        )
        self.assertTrue(ok, msg)

        # Simulate crash before commit: data change happened, tx has no COMMIT/ROLLBACK.
        table, _ = dbm.get_table("campus", "Offer")
        self.assertIsNotNone(table.get(201))

        recovery = RecoveryManager(dbm.wal)
        result = recovery.recover_into(dbm)

        self.assertIn(tx_id, result["undo_transactions"])
        self.assertGreaterEqual(result["applied_undo"], 1)
        self.assertIsNone(table.get(201))

    def test_crash_after_commit_redo_on_restart(self) -> None:
        self._log_case("Crash after commit + restart -> REDO committed row")
        # First process: commit transaction and produce WAL.
        writer = DatabaseManager(wal_path=self.wal_path)
        self._prepare_offer_table(writer)

        tx_id = writer.begin_transaction()
        ok, msg = writer.tx_insert(
            tx_id,
            "campus",
            "Offer",
            {
                "OfferID": 301,
                "ListingID": 901,
                "BuyerID": 3002,
                "OfferStatus": "Submitted",
                "AgreedPrice": 0.0,
            },
        )
        self.assertTrue(ok, msg)
        self.assertTrue(writer.commit_transaction(tx_id)[0])

        # Simulated restart: new process with same WAL but empty in-memory data.
        restarted = DatabaseManager(wal_path=self.wal_path)
        self._prepare_offer_table(restarted)
        table, _ = restarted.get_table("campus", "Offer")
        self.assertIsNone(table.get(301))

        recovery = RecoveryManager(restarted.wal)
        result = recovery.recover_into(restarted)

        self.assertIn(tx_id, result["redo_transactions"])
        self.assertGreaterEqual(result["applied_redo"], 1)

        row = table.get(301)
        self.assertIsNotNone(row)
        self.assertEqual(row["BuyerID"], 3002)

    def test_crash_after_offer_update_before_listing_tx_undo_prevents_split_brain(self) -> None:
        self._log_case("Crash after offer-update only -> UNDO prevents split-brain")
        # Writer process with full tables.
        writer = DatabaseManager(wal_path=self.wal_path)
        ok, _ = writer.create_database("campus")
        self.assertTrue(ok)

        offer_schema = {
            "OfferID": int,
            "ListingID": int,
            "BuyerID": int,
            "OfferedPrice": float,
            "AgreedPrice": float,
            "OfferStatus": str,
            "Reason": str,
            "ResponseDate": str,
        }
        listing_schema = {
            "ListingID": int,
            "SellerID": int,
            "Status": str,
            "LastModifiedDate": str,
        }
        transaction_schema = {
            "TransactionID": int,
            "ListingID": int,
            "SellerID": int,
            "BuyerID": int,
            "OfferID": int,
            "AgreedPrice": float,
            "Status": str,
            "CreatedDate": str,
        }

        self.assertTrue(writer.create_table("campus", "Offer", offer_schema, search_key="OfferID")[0])
        self.assertTrue(writer.create_table("campus", "Listing", listing_schema, search_key="ListingID")[0])
        self.assertTrue(writer.create_table("campus", "Transaction", transaction_schema, search_key="TransactionID")[0])

        offer_table, _ = writer.get_table("campus", "Offer")
        listing_table, _ = writer.get_table("campus", "Listing")
        transaction_table, _ = writer.get_table("campus", "Transaction")

        self.assertTrue(
            listing_table.insert(
                {
                    "ListingID": 777,
                    "SellerID": 100,
                    "Status": "Listed",
                    "LastModifiedDate": "",
                }
            )[0]
        )
        self.assertTrue(
            offer_table.insert(
                {
                    "OfferID": 888,
                    "ListingID": 777,
                    "BuyerID": 200,
                    "OfferedPrice": 99.0,
                    "AgreedPrice": 0.0,
                    "OfferStatus": "Submitted",
                    "Reason": "",
                    "ResponseDate": "",
                }
            )[0]
        )

        # Simulate crash point: accepted-offer update applied, but listing/transaction updates not applied.
        tx_id = writer.begin_transaction()
        ok, msg = writer.tx_update(
            tx_id,
            "campus",
            "Offer",
            888,
            {
                "OfferID": 888,
                "ListingID": 777,
                "BuyerID": 200,
                "OfferedPrice": 99.0,
                "AgreedPrice": 99.0,
                "OfferStatus": "Accepted",
                "Reason": "",
                "ResponseDate": "crash-point",
            },
        )
        self.assertTrue(ok, msg)
        self.assertEqual(offer_table.get(888)["OfferStatus"], "Accepted")

        # Restart process with baseline data loaded (pre-crash committed state).
        restarted = DatabaseManager(wal_path=self.wal_path)
        ok, _ = restarted.create_database("campus")
        self.assertTrue(ok)
        self.assertTrue(restarted.create_table("campus", "Offer", offer_schema, search_key="OfferID")[0])
        self.assertTrue(restarted.create_table("campus", "Listing", listing_schema, search_key="ListingID")[0])
        self.assertTrue(restarted.create_table("campus", "Transaction", transaction_schema, search_key="TransactionID")[0])

        r_offer, _ = restarted.get_table("campus", "Offer")
        r_listing, _ = restarted.get_table("campus", "Listing")
        r_tx, _ = restarted.get_table("campus", "Transaction")

        self.assertTrue(
            r_listing.insert(
                {
                    "ListingID": 777,
                    "SellerID": 100,
                    "Status": "Listed",
                    "LastModifiedDate": "",
                }
            )[0]
        )
        self.assertTrue(
            r_offer.insert(
                {
                    "OfferID": 888,
                    "ListingID": 777,
                    "BuyerID": 200,
                    "OfferedPrice": 99.0,
                    "AgreedPrice": 0.0,
                    "OfferStatus": "Submitted",
                    "Reason": "",
                    "ResponseDate": "",
                }
            )[0]
        )

        rec = RecoveryManager(restarted.wal)
        result = rec.recover_into(restarted)

        self.assertIn(tx_id, result["undo_transactions"])
        self.assertGreaterEqual(result["applied_undo"], 1)

        # Split-brain prevention: offer must not remain accepted without listing/transaction effects.
        self.assertEqual(r_offer.get(888)["OfferStatus"], "Submitted")
        self.assertEqual(r_listing.get(777)["Status"], "Listed")
        self.assertEqual(len(r_tx.get_all()), 0)


if __name__ == "__main__":
    unittest.main()
