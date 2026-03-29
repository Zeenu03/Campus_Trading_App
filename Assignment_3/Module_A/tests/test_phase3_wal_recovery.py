"""Phase 3 tests for WAL durability semantics and recovery analysis."""

from __future__ import annotations

import tempfile
import unittest

from database import DatabaseManager, RecoveryManager


class TestPhase3WalRecovery(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.wal_path = f"{self.tmpdir.name}/wal.log"

        self.dbm = DatabaseManager(wal_path=self.wal_path)
        ok, _ = self.dbm.create_database("campus")
        self.assertTrue(ok)

        offer_schema = {
            "OfferID": int,
            "ListingID": int,
            "BuyerID": int,
            "OfferStatus": str,
            "AgreedPrice": float,
        }
        ok, msg = self.dbm.create_table("campus", "Offer", offer_schema, search_key="OfferID")
        self.assertTrue(ok, msg)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_wal_contains_begin_change_commit_and_monotonic_lsn(self) -> None:
        tx = self.dbm.begin_transaction()
        ok, msg = self.dbm.tx_insert(
            tx,
            "campus",
            "Offer",
            {
                "OfferID": 100,
                "ListingID": 501,
                "BuyerID": 700,
                "OfferStatus": "Submitted",
                "AgreedPrice": 0.0,
            },
        )
        self.assertTrue(ok, msg)

        ok, msg = self.dbm.commit_transaction(tx)
        self.assertTrue(ok, msg)

        entries = self.dbm.wal.read_entries()
        tx_entries = [e for e in entries if e.get("tx_id") == tx]

        self.assertEqual([e.get("type") for e in tx_entries], ["BEGIN", "INSERT", "COMMIT"])

        lsns = [int(e["lsn"]) for e in entries]
        self.assertEqual(lsns, sorted(lsns))
        self.assertEqual(len(set(lsns)), len(lsns))

    def test_recovery_analysis_separates_committed_and_rolled_back(self) -> None:
        tx_commit = self.dbm.begin_transaction()
        ok, msg = self.dbm.tx_insert(
            tx_commit,
            "campus",
            "Offer",
            {
                "OfferID": 101,
                "ListingID": 502,
                "BuyerID": 701,
                "OfferStatus": "Submitted",
                "AgreedPrice": 0.0,
            },
        )
        self.assertTrue(ok, msg)
        self.assertTrue(self.dbm.commit_transaction(tx_commit)[0])

        tx_rollback = self.dbm.begin_transaction()
        ok, msg = self.dbm.tx_insert(
            tx_rollback,
            "campus",
            "Offer",
            {
                "OfferID": 102,
                "ListingID": 503,
                "BuyerID": 702,
                "OfferStatus": "Submitted",
                "AgreedPrice": 0.0,
            },
        )
        self.assertTrue(ok, msg)
        self.assertTrue(self.dbm.rollback_transaction(tx_rollback)[0])

        recovery = RecoveryManager(self.dbm.wal)
        summary = recovery.analyze()

        self.assertIn(tx_commit, summary.committed_transactions)
        self.assertIn(tx_rollback, summary.rolled_back_transactions)
        self.assertNotIn(tx_rollback, summary.uncommitted_transactions)


if __name__ == "__main__":
    unittest.main()
