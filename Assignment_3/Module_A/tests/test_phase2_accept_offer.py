"""Phase 2 tests for multi-table atomic accept-offer flow."""

from __future__ import annotations

import tempfile
import unittest

from database import DatabaseManager


class TestPhase2AcceptOffer(unittest.TestCase):
    def _log_case(self, title: str) -> None:
        print(f"\n[Phase 2] {title}")

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
        notification_schema = {
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

        self.assertTrue(self.dbm.create_table("campus", "Offer", offer_schema, search_key="OfferID")[0])
        self.assertTrue(self.dbm.create_table("campus", "Listing", listing_schema, search_key="ListingID")[0])
        self.assertTrue(self.dbm.create_table("campus", "Transaction", transaction_schema, search_key="TransactionID")[0])
        self.assertTrue(self.dbm.create_table("campus", "Notification", notification_schema, search_key="NotificationID")[0])

        listing_table, _ = self.dbm.get_table("campus", "Listing")
        self.assertIsNotNone(listing_table)
        ok, _ = listing_table.insert(
            {
                "ListingID": 100,
                "SellerID": 501,
                "Status": "Listed",
                "LastModifiedDate": "",
            }
        )
        self.assertTrue(ok)

        offer_table, _ = self.dbm.get_table("campus", "Offer")
        self.assertIsNotNone(offer_table)

        seed_offers = [
            {
                "OfferID": 10,
                "ListingID": 100,
                "BuyerID": 701,
                "OfferedPrice": 200.0,
                "AgreedPrice": 0.0,
                "OfferStatus": "Submitted",
                "Reason": "",
                "ResponseDate": "",
            },
            {
                "OfferID": 11,
                "ListingID": 100,
                "BuyerID": 702,
                "OfferedPrice": 190.0,
                "AgreedPrice": 0.0,
                "OfferStatus": "Submitted",
                "Reason": "",
                "ResponseDate": "",
            },
            {
                "OfferID": 12,
                "ListingID": 100,
                "BuyerID": 703,
                "OfferedPrice": 180.0,
                "AgreedPrice": 0.0,
                "OfferStatus": "Submitted",
                "Reason": "",
                "ResponseDate": "",
            },
        ]

        for row in seed_offers:
            ok, msg = offer_table.insert(row)
            self.assertTrue(ok, msg)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _state_snapshot(self) -> dict:
        offer_table, _ = self.dbm.get_table("campus", "Offer")
        listing_table, _ = self.dbm.get_table("campus", "Listing")
        transaction_table, _ = self.dbm.get_table("campus", "Transaction")
        notification_table, _ = self.dbm.get_table("campus", "Notification")

        return {
            "offer10": dict(offer_table.get(10)),
            "offer11": dict(offer_table.get(11)),
            "offer12": dict(offer_table.get(12)),
            "listing100": dict(listing_table.get(100)),
            "tx_count": len(transaction_table.get_all()),
            "notif_count": len(notification_table.get_all()),
        }

    def test_accept_offer_success_commits_all_side_effects(self) -> None:
        self._log_case("Accept offer success -> all side effects committed")
        ok, msg = self.dbm.accept_offer_atomic(
            db_name="campus",
            offer_id=10,
            acting_seller_id=501,
            include_notifications=True,
            create_declined_transactions=True,
        )
        self.assertTrue(ok, msg)

        offer_table, _ = self.dbm.get_table("campus", "Offer")
        listing_table, _ = self.dbm.get_table("campus", "Listing")
        transaction_table, _ = self.dbm.get_table("campus", "Transaction")
        notification_table, _ = self.dbm.get_table("campus", "Notification")

        accepted = offer_table.get(10)
        self.assertEqual(accepted["OfferStatus"], "Accepted")
        self.assertEqual(float(accepted["AgreedPrice"]), 200.0)

        self.assertEqual(offer_table.get(11)["OfferStatus"], "Declined")
        self.assertEqual(offer_table.get(12)["OfferStatus"], "Declined")

        listing = listing_table.get(100)
        self.assertEqual(listing["Status"], "Sold")

        tx_rows = transaction_table.get_all()
        self.assertEqual(len(tx_rows), 3)

        notif_rows = notification_table.get_all()
        self.assertEqual(len(notif_rows), 4)

    def test_failure_injection_rolls_back_everything(self) -> None:
        self._log_case("Failure injection -> full rollback of side effects")
        ok, _ = self.dbm.accept_offer_atomic(
            db_name="campus",
            offer_id=10,
            acting_seller_id=501,
            include_notifications=True,
            create_declined_transactions=True,
            fail_after_step=3,
        )
        self.assertFalse(ok)

        offer_table, _ = self.dbm.get_table("campus", "Offer")
        listing_table, _ = self.dbm.get_table("campus", "Listing")
        transaction_table, _ = self.dbm.get_table("campus", "Transaction")
        notification_table, _ = self.dbm.get_table("campus", "Notification")

        self.assertEqual(offer_table.get(10)["OfferStatus"], "Submitted")
        self.assertEqual(offer_table.get(11)["OfferStatus"], "Submitted")
        self.assertEqual(offer_table.get(12)["OfferStatus"], "Submitted")
        self.assertEqual(listing_table.get(100)["Status"], "Listed")

        self.assertEqual(len(transaction_table.get_all()), 0)
        self.assertEqual(len(notification_table.get_all()), 0)

    def test_invalid_accept_wrong_seller_no_state_change(self) -> None:
        self._log_case("Consistency: wrong seller -> abort, no state change")
        before = self._state_snapshot()

        ok, msg = self.dbm.accept_offer_atomic(
            db_name="campus",
            offer_id=10,
            acting_seller_id=9999,
            include_notifications=True,
            create_declined_transactions=True,
        )

        self.assertFalse(ok)
        self.assertIn("listing owner", msg)

        after = self._state_snapshot()
        self.assertEqual(before, after)

    def test_invalid_accept_non_submitted_offer_no_state_change(self) -> None:
        self._log_case("Consistency: non-submitted offer -> abort, no state change")
        offer_table, _ = self.dbm.get_table("campus", "Offer")
        seed = dict(offer_table.get(10))
        seed["OfferStatus"] = "Declined"
        ok, msg = offer_table.update(10, seed)
        self.assertTrue(ok, msg)

        before = self._state_snapshot()
        ok, msg = self.dbm.accept_offer_atomic(
            db_name="campus",
            offer_id=10,
            acting_seller_id=501,
            include_notifications=True,
            create_declined_transactions=True,
        )
        self.assertFalse(ok)
        self.assertIn("no longer active", msg)

        after = self._state_snapshot()
        self.assertEqual(before, after)

    def test_invalid_accept_listing_sold_no_state_change(self) -> None:
        self._log_case("Consistency: sold listing -> reject accept, no state change")
        listing_table, _ = self.dbm.get_table("campus", "Listing")
        listing = dict(listing_table.get(100))
        listing["Status"] = "Sold"
        ok, msg = listing_table.update(100, listing)
        self.assertTrue(ok, msg)

        before = self._state_snapshot()
        ok, msg = self.dbm.accept_offer_atomic(
            db_name="campus",
            offer_id=10,
            acting_seller_id=501,
            include_notifications=True,
            create_declined_transactions=True,
        )
        self.assertFalse(ok)
        self.assertIn("not available", msg)

        after = self._state_snapshot()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
