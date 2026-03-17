-- ============================================================
-- Campus Trading Application - Drop Indexes Script
-- Module B: For Benchmarking (Before/After Comparison)
-- ============================================================
-- Run this script to remove all indexes before benchmarking
-- Then run 03_create_indexes.sql to add them back
-- ============================================================

USE CampusTrading;

-- ============================================================
-- LISTING TABLE
-- ============================================================
DROP INDEX IDX_Listing_SellerID ON Listing;
DROP INDEX IDX_Listing_CategoryID ON Listing;
DROP INDEX IDX_Listing_Status ON Listing;
DROP INDEX IDX_Listing_Category_Status ON Listing;
DROP INDEX IDX_Listing_Price ON Listing;
DROP INDEX IDX_Listing_CreatedDate ON Listing;
DROP INDEX IDX_Listing_Seller_Status ON Listing;
DROP INDEX IDX_Listing_WishRequestID ON Listing;

-- ============================================================
-- OFFER TABLE
-- ============================================================
DROP INDEX IDX_Offer_ListingID ON Offer;
DROP INDEX IDX_Offer_BuyerID ON Offer;
DROP INDEX IDX_Offer_Listing_Status ON Offer;
DROP INDEX IDX_Offer_SubmittedDate ON Offer;
DROP INDEX IDX_Offer_ExpiryDate ON Offer;

-- ============================================================
-- TRANSACTION TABLE
-- ============================================================
DROP INDEX IDX_Transaction_SellerID ON `Transaction`;
DROP INDEX IDX_Transaction_BuyerID ON `Transaction`;
DROP INDEX IDX_Transaction_Date ON `Transaction`;
DROP INDEX IDX_Transaction_Status ON `Transaction`;
DROP INDEX IDX_Transaction_ListingID ON `Transaction`;

-- ============================================================
-- RATING TABLE
-- ============================================================
DROP INDEX IDX_Rating_RatedID ON Rating;
DROP INDEX IDX_Rating_RaterID ON Rating;
DROP INDEX IDX_Rating_TransactionID ON Rating;

-- ============================================================
-- MESSAGE & THREAD
-- ============================================================
DROP INDEX IDX_Message_ThreadID ON Message;
DROP INDEX IDX_Message_SentDate ON Message;
DROP INDEX IDX_MessageThread_ListingID ON MessageThread;
DROP INDEX IDX_MessageThread_BuyerID ON MessageThread;

-- ============================================================
-- NOTIFICATION TABLE
-- ============================================================
DROP INDEX IDX_Notification_RecipientID ON Notification;
DROP INDEX IDX_Notification_Recipient_Read ON Notification;
DROP INDEX IDX_Notification_Created ON Notification;
DROP INDEX IDX_Notification_Type ON Notification;

-- ============================================================
-- WATCHLIST TABLE
-- ============================================================
DROP INDEX IDX_Watchlist_MemberID ON Watchlist;
DROP INDEX IDX_Watchlist_ListingID ON Watchlist;

-- ============================================================
-- REPORT TABLE
-- ============================================================
DROP INDEX IDX_Report_Status ON Report;
DROP INDEX IDX_Report_ReporterID ON Report;
DROP INDEX IDX_Report_ReportedMemberID ON Report;
DROP INDEX IDX_Report_ReportedListingID ON Report;
DROP INDEX IDX_Report_SubmittedDate ON Report;

-- ============================================================
-- WISHREQUEST TABLE
-- ============================================================
DROP INDEX IDX_WishRequest_RequesterID ON WishRequest;
DROP INDEX IDX_WishRequest_Status ON WishRequest;

-- ============================================================
-- CATEGORY TABLE
-- ============================================================
DROP INDEX IDX_Category_ParentID ON Category;

-- ============================================================
-- MEMBER TABLE
-- ============================================================
DROP INDEX IDX_Member_Email ON Member;
DROP INDEX IDX_Member_Department ON Member;
DROP INDEX IDX_Member_Hostel ON Member;
DROP INDEX IDX_Member_AccountStatus ON Member;

-- ============================================================
-- LISTINGIMAGE TABLE
-- ============================================================
DROP INDEX IDX_ListingImage_ListingID ON ListingImage;

-- ============================================================
-- NOTE: This script does NOT drop:
-- - Primary key indexes (auto-created)
-- - Foreign key indexes (required for referential integrity)
-- - Unique constraint indexes
-- - Indexes on Auth tables (User, Session, AuditLog)
-- ============================================================
