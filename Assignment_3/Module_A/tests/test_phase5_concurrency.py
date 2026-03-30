"""Phase 5 tests for concurrent transaction behavior and isolation invariants."""

from __future__ import annotations

import tempfile
import threading
import unittest

from database import DatabaseManager


class TestPhase5Concurrency(unittest.TestCase):
    def _log_case(self, title: str) -> None:
        print(f"\n[Phase 5] {title}")

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        wal_path = f"{self.tmpdir.name}/wal.log"
        self.dbm = DatabaseManager(wal_path=wal_path)

        ok, _ = self.dbm.create_database("campus")
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

        self.assertTrue(self.dbm.create_table("campus", "Offer", offer_schema, search_key="OfferID")[0])
        self.assertTrue(self.dbm.create_table("campus", "Listing", listing_schema, search_key="ListingID")[0])
        self.assertTrue(self.dbm.create_table("campus", "Transaction", transaction_schema, search_key="TransactionID")[0])

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _seed_listing_and_offers(self) -> None:
        listing_table, _ = self.dbm.get_table("campus", "Listing")
        offer_table, _ = self.dbm.get_table("campus", "Offer")

        ok, _ = listing_table.insert(
            {
                "ListingID": 500,
                "SellerID": 999,
                "Status": "Listed",
                "LastModifiedDate": "",
            }
        )
        self.assertTrue(ok)

        seed = [
            {
                "OfferID": 41,
                "ListingID": 500,
                "BuyerID": 101,
                "OfferedPrice": 250.0,
                "AgreedPrice": 0.0,
                "OfferStatus": "Submitted",
                "Reason": "",
                "ResponseDate": "",
            },
            {
                "OfferID": 42,
                "ListingID": 500,
                "BuyerID": 102,
                "OfferedPrice": 245.0,
                "AgreedPrice": 0.0,
                "OfferStatus": "Submitted",
                "Reason": "",
                "ResponseDate": "",
            },
        ]
        for row in seed:
            ok, msg = offer_table.insert(row)
            self.assertTrue(ok, msg)

    def test_competing_accepts_same_listing_single_winner(self) -> None:
        self._log_case("Isolation: competing offers on one listing -> single winner")
        self._seed_listing_and_offers()

        start_barrier = threading.Barrier(2)
        results: list[tuple[int, bool, str]] = []
        results_lock = threading.Lock()

        def runner(offer_id: int) -> None:
            start_barrier.wait()
            ok, msg = self.dbm.accept_offer_atomic(
                db_name="campus",
                offer_id=offer_id,
                acting_seller_id=999,
                include_notifications=False,
                create_declined_transactions=True,
            )
            with results_lock:
                results.append((offer_id, ok, msg))

        t1 = threading.Thread(target=runner, args=(41,))
        t2 = threading.Thread(target=runner, args=(42,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = [r for r in results if r[1]]
        failures = [r for r in results if not r[1]]

        self.assertEqual(len(successes), 1, f"expected exactly one success, got: {results}")
        self.assertEqual(len(failures), 1, f"expected exactly one failure, got: {results}")

        offer_table, _ = self.dbm.get_table("campus", "Offer")
        listing_table, _ = self.dbm.get_table("campus", "Listing")
        transaction_table, _ = self.dbm.get_table("campus", "Transaction")

        offers = [row for _, row in offer_table.get_all()]
        accepted_count = sum(1 for row in offers if row["OfferStatus"] == "Accepted")
        declined_count = sum(1 for row in offers if row["OfferStatus"] == "Declined")

        self.assertEqual(accepted_count, 1)
        self.assertEqual(declined_count, 1)
        self.assertEqual(listing_table.get(500)["Status"], "Sold")

        # Winner path creates one accepted + one declined transaction row for two submitted offers.
        self.assertEqual(len(transaction_table.get_all()), 2)

    def test_many_threads_same_offer_only_one_commit(self) -> None:
        self._log_case("Isolation: many threads same offer -> one commit")
        self._seed_listing_and_offers()

        thread_count = 10
        start_barrier = threading.Barrier(thread_count)
        results: list[tuple[bool, str]] = []
        results_lock = threading.Lock()

        def runner() -> None:
            start_barrier.wait()
            ok, msg = self.dbm.accept_offer_atomic(
                db_name="campus",
                offer_id=41,
                acting_seller_id=999,
                include_notifications=False,
                create_declined_transactions=False,
            )
            with results_lock:
                results.append((ok, msg))

        threads = [threading.Thread(target=runner) for _ in range(thread_count)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        success_count = sum(1 for ok, _ in results if ok)
        self.assertEqual(success_count, 1, f"expected single winner commit, got: {results}")

        offer_table, _ = self.dbm.get_table("campus", "Offer")
        listing_table, _ = self.dbm.get_table("campus", "Listing")
        transaction_table, _ = self.dbm.get_table("campus", "Transaction")

        self.assertEqual(offer_table.get(41)["OfferStatus"], "Accepted")
        self.assertEqual(listing_table.get(500)["Status"], "Sold")
        self.assertEqual(len(transaction_table.get_all()), 1)


if __name__ == "__main__":
    unittest.main()
