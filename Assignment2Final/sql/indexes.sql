-- ============================================================
-- Campus Trading Application - Module B - Indexes (Subtask 4)
-- ============================================================
-- Run AFTER init.sql and AFTER recording benchmark baseline.
-- Usage:
--   1. Run init.sql
--   2. Hit GET /api/v1/admin/benchmark  → save "before" results
--   3. Run this file: mysql -u root -p CampusTradingB < sql/indexes.sql
--   4. Hit GET /api/v1/admin/benchmark  → compare "after" results
-- ============================================================

USE CampusTradingB;

CREATE INDEX idx_listing_seller          ON Listing (SellerID);
CREATE INDEX idx_listing_status_expiry   ON Listing (Status, ExpiryDate);
CREATE INDEX idx_listing_category_status ON Listing (CategoryID, Status);
CREATE INDEX idx_listing_created         ON Listing (CreatedDate DESC);
CREATE INDEX idx_offer_listing           ON Offer (ListingID);
CREATE INDEX idx_offer_buyer             ON Offer (BuyerID);
CREATE INDEX idx_offer_status            ON Offer (ListingID, OfferStatus);
CREATE INDEX idx_tx_seller               ON `Transaction` (SellerID);
CREATE INDEX idx_tx_buyer                ON `Transaction` (BuyerID);
CREATE UNIQUE INDEX idx_rating_tx        ON Rating (TransactionID, RaterID);
CREATE INDEX idx_rating_rated            ON Rating (RatedID);
CREATE INDEX idx_notif_recipient_read    ON Notification (RecipientID, IsRead);
CREATE INDEX idx_session_expires         ON sys_session (is_revoked, expires_at);
CREATE INDEX idx_wishreq_requester       ON WishRequest (RequesterID, Status);
CREATE INDEX idx_wishreq_browse          ON WishRequest (Status, CategoryID, CreatedDate);
CREATE INDEX idx_wishreqimg_parent_order ON WishRequestImage (WishRequestID, ImageOrder);
CREATE INDEX idx_listingwishreq_wishreq  ON ListingWishRequest (WishRequestID, ListingID);
