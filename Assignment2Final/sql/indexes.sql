-- ============================================================
-- Campus Trading App — SQL Performance Indexes
-- ============================================================
-- Apply AFTER init.sql has been run and the database is populated.
--
-- Docker:
--   docker exec -i campus_trading_mysql \
--     mysql -uroot -proot CampusTradingB < sql/indexes.sql
--
-- Local MySQL:
--   mysql -u root -p CampusTradingB < sql/indexes.sql
-- ============================================================

USE CampusTradingB;

-- ------------------------------------------------------------
-- TABLE: Listing
-- Rationale:
--   Most-hit table in the app. Queried by the browse page
--   (GET /listings), portfolio page, and listing detail page.
--
--   Q1  WHERE Status='Listed' ORDER BY CreatedDate DESC
--   Q2  WHERE SellerID = ?
--   API WHERE Status=? AND CategoryID=?         (/listings filters)
--   API WHERE Status=? AND AskingPrice BETWEEN  (/listings price range)
-- ------------------------------------------------------------

-- Q1 benchmark + browse page sort
CREATE INDEX idx_listing_status_created
    ON Listing (Status, CreatedDate);

-- Q2 benchmark + portfolio page (seller's listings)
CREATE INDEX idx_listing_seller_created
    ON Listing (SellerID, CreatedDate);

-- Category-filtered browse (composite covers both WHERE cols)
CREATE INDEX idx_listing_status_category
    ON Listing (Status, CategoryID);

-- Price-range browse
CREATE INDEX idx_listing_status_price
    ON Listing (Status, AskingPrice);

-- ------------------------------------------------------------
-- TABLE: Offer
-- Rationale:
--   Q3  WHERE ListingID=? AND OfferStatus='Submitted'
--   API WHERE BuyerID=? (buyer's active offers)
-- ------------------------------------------------------------

-- Q3 benchmark + listing detail offer list
CREATE INDEX idx_offer_listing_status
    ON Offer (ListingID, OfferStatus);

-- Buyer's offer history
CREATE INDEX idx_offer_buyer
    ON Offer (BuyerID);

-- ------------------------------------------------------------
-- TABLE: Notification
-- Rationale:
--   Polled by the NotificationBell component on every page load.
--   Q4  WHERE RecipientID=? AND IsRead=FALSE
--   API WHERE RecipientID=? ORDER BY CreatedDate DESC
-- ------------------------------------------------------------

-- Q4 benchmark — unread count + list
CREATE INDEX idx_notification_recipient_read
    ON Notification (RecipientID, IsRead);

-- Paginated notification list (covers ORDER BY)
CREATE INDEX idx_notification_recipient_created
    ON Notification (RecipientID, CreatedDate);

-- ------------------------------------------------------------
-- TABLE: Rating
-- Rationale:
--   Q5  AVG(Stars) WHERE RatedID=?
--   API WHERE RatedID=? ORDER BY RatingDate DESC (portfolio)
-- ------------------------------------------------------------

CREATE INDEX idx_rating_rated
    ON Rating (RatedID, RatingDate);

-- ------------------------------------------------------------
-- TABLE: Transaction
-- Rationale:
--   WHERE SellerID=? OR BuyerID=?  (GET /transactions)
--   The OR requires two separate indexes so the optimizer can
--   use an index union.
-- ------------------------------------------------------------

CREATE INDEX idx_transaction_seller
    ON Transaction (SellerID);

CREATE INDEX idx_transaction_buyer
    ON Transaction (BuyerID);

-- ------------------------------------------------------------
-- TABLE: Message
-- Rationale:
--   WHERE ThreadID=? ORDER BY SentDate ASC LIMIT ? OFFSET ?
--   (GET /threads/{id}/messages — paginated chat history)
-- ------------------------------------------------------------

CREATE INDEX idx_message_thread_sent
    ON Message (ThreadID, SentDate);

-- ------------------------------------------------------------
-- TABLE: WishRequest
-- Rationale:
--   WHERE Status='Active' ORDER BY CreatedDate DESC  (GET /wishrequests)
--   WHERE RequesterID=?  (member's own wish requests in portfolio)
-- ------------------------------------------------------------

CREATE INDEX idx_wishrequest_status_created
    ON WishRequest (Status, CreatedDate);

CREATE INDEX idx_wishrequest_requester
    ON WishRequest (RequesterID);

-- ------------------------------------------------------------
-- TABLE: audit_log
-- Rationale:
--   ORDER BY timestamp DESC LIMIT ? OFFSET ?  (GET /admin/audit-log)
--   Without this index MySQL sorts the entire table on each page.
-- ------------------------------------------------------------

CREATE INDEX idx_auditlog_timestamp
    ON audit_log (timestamp);

-- ------------------------------------------------------------
-- TABLE: Report
-- Rationale:
--   WHERE Status=? ORDER BY SubmittedDate DESC  (GET /reports)
-- ------------------------------------------------------------

CREATE INDEX idx_report_status_submitted
    ON Report (Status, SubmittedDate);

-- ------------------------------------------------------------
-- Verification — list all custom indexes just created
-- ------------------------------------------------------------
SELECT
    TABLE_NAME        AS `Table`,
    INDEX_NAME        AS `Index`,
    GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ', ') AS `Columns`,
    IF(NON_UNIQUE = 0, 'UNIQUE', 'INDEX') AS `Type`
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND INDEX_NAME LIKE 'idx_%'
GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE
ORDER BY TABLE_NAME, INDEX_NAME;
