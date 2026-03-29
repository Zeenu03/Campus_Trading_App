"""Phase 4 tests for crash recovery REDO/UNDO replay."""

from __future__ import annotations

import tempfile
import unittest

from database import DatabaseManager, RecoveryManager


class TestPhase4RecoveryReplay(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
