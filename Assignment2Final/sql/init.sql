-- ============================================================
-- Campus Trading Application - Module B - Database Init Script
-- ============================================================
-- Run: mysql -u root -p < sql/init.sql
-- After running this, execute: go run ./backend/cmd/seed
-- to create the SuperAdmin account.
-- ============================================================

CREATE DATABASE IF NOT EXISTS CampusTradingB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE CampusTradingB;

-- Drop triggers before tables
DROP TRIGGER IF EXISTS trg_message_ai;

DROP TRIGGER IF EXISTS trg_message_bu;

DROP TRIGGER IF EXISTS trg_message_bd;

DROP TRIGGER IF EXISTS trg_msgthread_ai;

DROP TRIGGER IF EXISTS trg_msgthread_bu;

DROP TRIGGER IF EXISTS trg_msgthread_bd;

DROP TRIGGER IF EXISTS trg_notification_ai;

DROP TRIGGER IF EXISTS trg_notification_bu;

DROP TRIGGER IF EXISTS trg_notification_bd;

DROP TRIGGER IF EXISTS trg_report_ai;

DROP TRIGGER IF EXISTS trg_report_bu;

DROP TRIGGER IF EXISTS trg_report_bd;

DROP TRIGGER IF EXISTS trg_watchlist_ai;

DROP TRIGGER IF EXISTS trg_watchlist_bu;

DROP TRIGGER IF EXISTS trg_watchlist_bd;

DROP TRIGGER IF EXISTS trg_rating_ai;

DROP TRIGGER IF EXISTS trg_rating_bu;

DROP TRIGGER IF EXISTS trg_rating_bd;

DROP TRIGGER IF EXISTS trg_transaction_ai;

DROP TRIGGER IF EXISTS trg_transaction_bu;

DROP TRIGGER IF EXISTS trg_transaction_bd;

DROP TRIGGER IF EXISTS trg_offer_ai;

DROP TRIGGER IF EXISTS trg_offer_bu;

DROP TRIGGER IF EXISTS trg_offer_bd;

DROP TRIGGER IF EXISTS trg_listingimage_ai;

DROP TRIGGER IF EXISTS trg_listingimage_bu;

DROP TRIGGER IF EXISTS trg_listingimage_bd;

DROP TRIGGER IF EXISTS trg_listing_ai;

DROP TRIGGER IF EXISTS trg_listing_bu;

DROP TRIGGER IF EXISTS trg_listing_bd;

DROP TRIGGER IF EXISTS trg_wishrequest_ai;

DROP TRIGGER IF EXISTS trg_wishrequest_bu;

DROP TRIGGER IF EXISTS trg_wishrequest_bd;

DROP TRIGGER IF EXISTS trg_administrator_ai;

DROP TRIGGER IF EXISTS trg_administrator_bu;

DROP TRIGGER IF EXISTS trg_administrator_bd;

DROP TRIGGER IF EXISTS trg_member_ai;

DROP TRIGGER IF EXISTS trg_member_bu;

DROP TRIGGER IF EXISTS trg_member_bd;

DROP TRIGGER IF EXISTS trg_category_ai;

DROP TRIGGER IF EXISTS trg_category_bu;

DROP TRIGGER IF EXISTS trg_category_bd;

DROP PROCEDURE IF EXISTS sp_audit_log;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS Message;

DROP TABLE IF EXISTS MessageThread;

DROP TABLE IF EXISTS Notification;

DROP TABLE IF EXISTS Report;

DROP TABLE IF EXISTS Watchlist;

DROP TABLE IF EXISTS Rating;

DROP TABLE IF EXISTS `Transaction`;

DROP TABLE IF EXISTS Offer;

DROP TABLE IF EXISTS ListingImage;

DROP TABLE IF EXISTS Listing;

DROP TABLE IF EXISTS WishRequest;

DROP TABLE IF EXISTS Administrator;

DROP TABLE IF EXISTS Member;

DROP TABLE IF EXISTS Category;

DROP TABLE IF EXISTS sys_user_role;

DROP TABLE IF EXISTS sys_session;

DROP TABLE IF EXISTS sys_role;

DROP TABLE IF EXISTS audit_log;

DROP TABLE IF EXISTS sys_user;

-- ============================================================
-- CORE SYSTEM TABLES
-- ============================================================

CREATE TABLE sys_user (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT CHK_email_iitgn CHECK (email LIKE '%@iitgn.ac.in')
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE sys_role (
    role_id INT PRIMARY KEY AUTO_INCREMENT,
    role_name VARCHAR(40) NOT NULL UNIQUE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE sys_session (
    session_id CHAR(64) PRIMARY KEY,
    user_id INT NOT NULL,
    expires_at DATETIME NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_session_user FOREIGN KEY (user_id) REFERENCES sys_user (user_id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE sys_user_role (
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT FK_user_role_user FOREIGN KEY (user_id) REFERENCES sys_user (user_id) ON DELETE CASCADE,
    CONSTRAINT FK_user_role_role FOREIGN KEY (role_id) REFERENCES sys_role (role_id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE audit_log (
    log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    timestamp DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    session_id CHAR(64),
    user_id INT,
    action VARCHAR(20) NOT NULL,
    target_table VARCHAR(60) NOT NULL,
    target_id VARCHAR(40),
    ip_address VARCHAR(45),
    status ENUM('success', 'fail') NOT NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ============================================================
-- PROJECT TABLES
-- ============================================================

CREATE TABLE Category (
    CategoryID INT AUTO_INCREMENT PRIMARY KEY,
    CategoryName VARCHAR(100) NOT NULL,
    Description VARCHAR(500) NULL,
    IsActive BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT UQ_Category_Name UNIQUE (CategoryName)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- Member: user_id links to sys_user; Email/PasswordHash removed (in sys_user)
CREATE TABLE Member (
    MemberID INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    Name VARCHAR(100) NOT NULL,
    ContactNumber VARCHAR(20) NOT NULL,
    Department VARCHAR(100) NULL,
    YearOfStudy INT NULL,
    Hostel VARCHAR(100) NULL,
    RoomNumber VARCHAR(20) NULL,
    Image VARCHAR(500) NULL,
    Bio VARCHAR(500) NULL,
    IsVerified BOOLEAN DEFAULT FALSE,
    VerificationDate DATETIME NULL,
    AccountCreationDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Member_User FOREIGN KEY (user_id) REFERENCES sys_user (user_id) ON UPDATE CASCADE,
    CONSTRAINT CHK_Member_YearOfStudy CHECK (YearOfStudy BETWEEN 1 AND 5)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- Administrator: user_id links to sys_user; Email/PasswordHash removed
CREATE TABLE Administrator (
    AdminID INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    Name VARCHAR(100) NOT NULL,
    Role VARCHAR(20) NOT NULL DEFAULT 'Moderator',
    CreatedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    LastLoginDate DATETIME NULL,
    IsActive BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT FK_Admin_User FOREIGN KEY (user_id) REFERENCES sys_user (user_id) ON UPDATE CASCADE,
    CONSTRAINT CHK_Admin_Role CHECK (
        Role IN (
            'SuperAdmin',
            'Moderator',
            'Support'
        )
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE WishRequest (
    WishRequestID INT AUTO_INCREMENT PRIMARY KEY,
    RequesterID INT NOT NULL,
    ItemDescription VARCHAR(500) NOT NULL,
    MinBudget DECIMAL(10, 2) NULL,
    MaxBudget DECIMAL(10, 2) NULL,
    PreferredCondition VARCHAR(20) NULL,
    NeededByDate DATE NULL,
    AdditionalDetails VARCHAR(1000) NULL,
    Status VARCHAR(20) NOT NULL DEFAULT 'Active',
    CreatedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FulfilledDate DATETIME NULL,
    CONSTRAINT FK_WishRequest_Member FOREIGN KEY (RequesterID) REFERENCES Member (MemberID) ON UPDATE CASCADE,
    CONSTRAINT CHK_WishRequest_Status CHECK (
        Status IN (
            'Active',
            'Fulfilled',
            'Expired',
            'Cancelled'
        )
    ),
    CONSTRAINT CHK_WishRequest_Budget CHECK (
        MaxBudget >= MinBudget
        OR MinBudget IS NULL
    ),
    CONSTRAINT CHK_WishRequest_Condition CHECK (
        PreferredCondition IN (
            'New',
            'Like New',
            'Good',
            'Fair',
            'Poor'
        )
        OR PreferredCondition IS NULL
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE Listing (
    ListingID INT AUTO_INCREMENT PRIMARY KEY,
    SellerID INT NOT NULL,
    CategoryID INT NOT NULL,
    Title VARCHAR(200) NOT NULL,
    Description VARCHAR(2000) NULL,
    AskingPrice DECIMAL(10, 2) NOT NULL,
    IsNegotiable BOOLEAN NOT NULL DEFAULT TRUE,
    `Condition` VARCHAR(20) NULL,
    Status VARCHAR(20) NOT NULL DEFAULT 'Listed',
    CreatedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    LastModifiedDate DATETIME NULL,
    ExpiryDate DATETIME NULL,
    IsDonation BOOLEAN NOT NULL DEFAULT FALSE,
    WishRequestID INT NULL,
    CONSTRAINT FK_Listing_Seller FOREIGN KEY (SellerID) REFERENCES Member (MemberID) ON UPDATE CASCADE,
    CONSTRAINT FK_Listing_Category FOREIGN KEY (CategoryID) REFERENCES Category (CategoryID) ON UPDATE CASCADE,
    CONSTRAINT FK_Listing_WishRequest FOREIGN KEY (WishRequestID) REFERENCES WishRequest (WishRequestID) ON DELETE SET NULL,
    CONSTRAINT CHK_Listing_Status CHECK (
        Status IN (
            'Listed',
            'Pending',
            'Reserved',
            'Completed',
            'Sold',
            'Expired',
            'Withdrawn'
        )
    ),
    CONSTRAINT CHK_Listing_Condition CHECK (
        `Condition` IN (
            'New',
            'Like New',
            'Good',
            'Fair',
            'Poor'
        )
        OR `Condition` IS NULL
    ),
    CONSTRAINT CHK_Listing_Price CHECK (AskingPrice >= 0),
    CONSTRAINT CHK_Listing_Donation CHECK (
        (
            IsDonation = TRUE
            AND AskingPrice = 0
        )
        OR IsDonation = FALSE
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE ListingImage (
    ImageID INT AUTO_INCREMENT PRIMARY KEY,
    ListingID INT NOT NULL,
    ImageURL VARCHAR(500) NOT NULL,
    ImageOrder INT NOT NULL,
    UploadedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_ListingImage_Listing FOREIGN KEY (ListingID) REFERENCES Listing (ListingID) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT CHK_ListingImage_Order CHECK (ImageOrder >= 1),
    CONSTRAINT UQ_ListingImage_Order UNIQUE (ListingID, ImageOrder)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE Offer (
    OfferID INT AUTO_INCREMENT PRIMARY KEY,
    ListingID INT NOT NULL,
    BuyerID INT NOT NULL,
    OfferedPrice DECIMAL(10, 2) NOT NULL,
    AgreedPrice DECIMAL(10, 2) NULL,
    OfferMessage VARCHAR(500) NULL,
    OfferStatus VARCHAR(20) NOT NULL DEFAULT 'Submitted',
    SubmittedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ResponseDate DATETIME NULL,
    ExpiryDate DATETIME NULL,
    CONSTRAINT FK_Offer_Listing FOREIGN KEY (ListingID) REFERENCES Listing (ListingID) ON UPDATE CASCADE,
    CONSTRAINT FK_Offer_Buyer FOREIGN KEY (BuyerID) REFERENCES Member (MemberID),
    CONSTRAINT CHK_Offer_Status CHECK (
        OfferStatus IN (
            'Submitted',
            'Accepted',
            'Declined',
            'Withdrawn',
            'Expired'
        )
    ),
    CONSTRAINT CHK_Offer_Price CHECK (OfferedPrice > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE `Transaction` (
    TransactionID INT AUTO_INCREMENT PRIMARY KEY,
    ListingID INT NOT NULL,
    SellerID INT NOT NULL,
    BuyerID INT NOT NULL,
    OfferID INT NULL,
    AgreedPrice DECIMAL(10, 2) NOT NULL,
    TransactionDate DATETIME NULL,
    SellerConfirmed BOOLEAN NOT NULL DEFAULT FALSE,
    BuyerConfirmed BOOLEAN NOT NULL DEFAULT FALSE,
    Status VARCHAR(20) NOT NULL DEFAULT 'Scheduled',
    CreatedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Transaction_Listing FOREIGN KEY (ListingID) REFERENCES Listing (ListingID),
    CONSTRAINT FK_Transaction_Seller FOREIGN KEY (SellerID) REFERENCES Member (MemberID),
    CONSTRAINT FK_Transaction_Buyer FOREIGN KEY (BuyerID) REFERENCES Member (MemberID),
    CONSTRAINT FK_Transaction_Offer FOREIGN KEY (OfferID) REFERENCES Offer (OfferID),
    CONSTRAINT CHK_Transaction_Status CHECK (
        Status IN (
            'Scheduled',
            'Completed',
            'Cancelled'
        )
    ),
    CONSTRAINT CHK_Transaction_Price CHECK (AgreedPrice >= 0),
    CONSTRAINT CHK_Transaction_Parties CHECK (BuyerID <> SellerID)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE Rating (
    RatingID INT AUTO_INCREMENT PRIMARY KEY,
    TransactionID INT NOT NULL,
    RaterID INT NOT NULL,
    RatedID INT NOT NULL,
    Stars INT NOT NULL,
    ReviewText VARCHAR(1000) NULL,
    RatingDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Rating_Transaction FOREIGN KEY (TransactionID) REFERENCES `Transaction` (TransactionID) ON UPDATE CASCADE,
    CONSTRAINT FK_Rating_Rater FOREIGN KEY (RaterID) REFERENCES Member (MemberID),
    CONSTRAINT FK_Rating_Rated FOREIGN KEY (RatedID) REFERENCES Member (MemberID),
    CONSTRAINT CHK_Rating_Stars CHECK (Stars BETWEEN 1 AND 5),
    CONSTRAINT CHK_Rating_Members CHECK (RaterID <> RatedID),
    CONSTRAINT UQ_Rating_TX_Rater UNIQUE (TransactionID, RaterID)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE Watchlist (
    WatchlistID INT AUTO_INCREMENT PRIMARY KEY,
    MemberID INT NOT NULL,
    ListingID INT NOT NULL,
    AddedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    NotifyOnPriceChange BOOLEAN NOT NULL DEFAULT TRUE,
    NotifyOnStatusChange BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT FK_Watchlist_Member FOREIGN KEY (MemberID) REFERENCES Member (MemberID) ON DELETE CASCADE,
    CONSTRAINT FK_Watchlist_Listing FOREIGN KEY (ListingID) REFERENCES Listing (ListingID) ON DELETE CASCADE,
    CONSTRAINT UQ_Watchlist_Member_Listing UNIQUE (MemberID, ListingID)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE Report (
    ReportID INT AUTO_INCREMENT PRIMARY KEY,
    ReporterID INT NOT NULL,
    ReportedMemberID INT NULL,
    ReportedListingID INT NULL,
    ReportType VARCHAR(50) NOT NULL,
    Description VARCHAR(2000) NOT NULL,
    Status VARCHAR(20) NOT NULL DEFAULT 'Submitted',
    SubmittedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ResolvedDate DATETIME NULL,
    ResolvedByAdminID INT NULL,
    Resolution VARCHAR(1000) NULL,
    CONSTRAINT FK_Report_Reporter FOREIGN KEY (ReporterID) REFERENCES Member (MemberID),
    CONSTRAINT FK_Report_ReportedMember FOREIGN KEY (ReportedMemberID) REFERENCES Member (MemberID),
    CONSTRAINT FK_Report_ReportedListing FOREIGN KEY (ReportedListingID) REFERENCES Listing (ListingID),
    CONSTRAINT FK_Report_Admin FOREIGN KEY (ResolvedByAdminID) REFERENCES Administrator (AdminID) ON DELETE SET NULL,
    CONSTRAINT CHK_Report_Status CHECK (
        Status IN (
            'Submitted',
            'UnderReview',
            'Resolved',
            'Dismissed'
        )
    ),
    CONSTRAINT CHK_Report_Target CHECK (
        ReportedMemberID IS NOT NULL
        OR ReportedListingID IS NOT NULL
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE Notification (
    NotificationID INT AUTO_INCREMENT PRIMARY KEY,
    RecipientID INT NOT NULL,
    NotificationType VARCHAR(50) NOT NULL,
    Title VARCHAR(200) NULL,
    Message VARCHAR(1000) NOT NULL,
    RelatedListingID INT NULL,
    RelatedOfferID INT NULL,
    RelatedTransactionID INT NULL,
    IsRead BOOLEAN NOT NULL DEFAULT FALSE,
    CreatedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ReadDate DATETIME NULL,
    CONSTRAINT FK_Notif_Recipient FOREIGN KEY (RecipientID) REFERENCES Member (MemberID) ON DELETE CASCADE,
    CONSTRAINT FK_Notif_Listing FOREIGN KEY (RelatedListingID) REFERENCES Listing (ListingID),
    CONSTRAINT FK_Notif_Offer FOREIGN KEY (RelatedOfferID) REFERENCES Offer (OfferID),
    CONSTRAINT FK_Notif_Transaction FOREIGN KEY (RelatedTransactionID) REFERENCES `Transaction` (TransactionID),
    CONSTRAINT CHK_Notif_Type CHECK (
        NotificationType IN (
            'OfferReceived',
            'OfferAccepted',
            'OfferDeclined',
            'OfferWithdrawn',
            'OfferExpired',
            'PriceDropped',
            'StatusChanged',
            'MeetingReminder',
            'TransactionCompleted',
            'RatingReceived',
            'WishRequestMatched',
            'ListingExpiring',
            'General'
        )
    )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE MessageThread (
    ThreadID INT AUTO_INCREMENT PRIMARY KEY,
    ListingID INT NOT NULL,
    BuyerID INT NOT NULL,
    OfferID INT NOT NULL,
    CreatedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    IsActive BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT FK_Thread_Listing FOREIGN KEY (ListingID) REFERENCES Listing (ListingID),
    CONSTRAINT FK_Thread_Buyer FOREIGN KEY (BuyerID) REFERENCES Member (MemberID),
    CONSTRAINT FK_Thread_Offer FOREIGN KEY (OfferID) REFERENCES Offer (OfferID),
    CONSTRAINT UQ_Thread_Listing_Buyer UNIQUE (ListingID, BuyerID)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE Message (
    MessageID INT AUTO_INCREMENT PRIMARY KEY,
    ThreadID INT NOT NULL,
    SenderID INT NOT NULL,
    MessageText VARCHAR(2000) NOT NULL,
    SentDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Message_Thread FOREIGN KEY (ThreadID) REFERENCES MessageThread (ThreadID) ON DELETE CASCADE,
    CONSTRAINT FK_Message_Sender FOREIGN KEY (SenderID) REFERENCES Member (MemberID)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ============================================================
-- AUDIT STORED PROCEDURE
-- Called by all triggers to write to audit_log
-- @session_id and @current_user_id are set by API middleware before writes
-- NULL session_id signals a direct (unauthorized) DB write
-- ============================================================

DELIMITER //

CREATE PROCEDURE sp_audit_log(
    IN p_action    VARCHAR(20),
    IN p_table     VARCHAR(60),
    IN p_target_id VARCHAR(40)
)
BEGIN
    INSERT INTO audit_log (session_id, user_id, action, target_table, target_id, status)
    VALUES (@session_id, @current_user_id, p_action, p_table, p_target_id, 'success');
END //

DELIMITER ;

-- ============================================================
-- AUDIT TRIGGERS - All 14 project tables
-- AFTER INSERT (to capture auto-generated ID),
-- BEFORE UPDATE, BEFORE DELETE
-- ============================================================

DELIMITER //

-- Category triggers
CREATE TRIGGER trg_category_ai AFTER INSERT ON Category FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Category', NEW.CategoryID); END //

CREATE TRIGGER trg_category_bu BEFORE UPDATE ON Category FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Category', OLD.CategoryID); END //

CREATE TRIGGER trg_category_bd BEFORE DELETE ON Category FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Category', OLD.CategoryID); END //

-- Member triggers
CREATE TRIGGER trg_member_ai AFTER INSERT ON Member FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Member', NEW.MemberID); END //

CREATE TRIGGER trg_member_bu BEFORE UPDATE ON Member FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Member', OLD.MemberID); END //

CREATE TRIGGER trg_member_bd BEFORE DELETE ON Member FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Member', OLD.MemberID); END //

-- Administrator triggers
CREATE TRIGGER trg_administrator_ai AFTER INSERT ON Administrator FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Administrator', NEW.AdminID); END //

CREATE TRIGGER trg_administrator_bu BEFORE UPDATE ON Administrator FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Administrator', OLD.AdminID); END //

CREATE TRIGGER trg_administrator_bd BEFORE DELETE ON Administrator FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Administrator', OLD.AdminID); END //

-- WishRequest triggers
CREATE TRIGGER trg_wishrequest_ai AFTER INSERT ON WishRequest FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'WishRequest', NEW.WishRequestID); END //

CREATE TRIGGER trg_wishrequest_bu BEFORE UPDATE ON WishRequest FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'WishRequest', OLD.WishRequestID); END //

CREATE TRIGGER trg_wishrequest_bd BEFORE DELETE ON WishRequest FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'WishRequest', OLD.WishRequestID); END //

-- Listing triggers
CREATE TRIGGER trg_listing_ai AFTER INSERT ON Listing FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Listing', NEW.ListingID); END //

CREATE TRIGGER trg_listing_bu BEFORE UPDATE ON Listing FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Listing', OLD.ListingID); END //

CREATE TRIGGER trg_listing_bd BEFORE DELETE ON Listing FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Listing', OLD.ListingID); END //

-- ListingImage triggers
CREATE TRIGGER trg_listingimage_ai AFTER INSERT ON ListingImage FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'ListingImage', NEW.ImageID); END //

CREATE TRIGGER trg_listingimage_bu BEFORE UPDATE ON ListingImage FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'ListingImage', OLD.ImageID); END //

CREATE TRIGGER trg_listingimage_bd BEFORE DELETE ON ListingImage FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'ListingImage', OLD.ImageID); END //

-- Offer triggers
CREATE TRIGGER trg_offer_ai AFTER INSERT ON Offer FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Offer', NEW.OfferID); END //

CREATE TRIGGER trg_offer_bu BEFORE UPDATE ON Offer FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Offer', OLD.OfferID); END //

CREATE TRIGGER trg_offer_bd BEFORE DELETE ON Offer FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Offer', OLD.OfferID); END //

-- Transaction triggers
CREATE TRIGGER trg_transaction_ai AFTER INSERT ON `Transaction` FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Transaction', NEW.TransactionID); END //

CREATE TRIGGER trg_transaction_bu BEFORE UPDATE ON `Transaction` FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Transaction', OLD.TransactionID); END //

CREATE TRIGGER trg_transaction_bd BEFORE DELETE ON `Transaction` FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Transaction', OLD.TransactionID); END //

-- Rating triggers
CREATE TRIGGER trg_rating_ai AFTER INSERT ON Rating FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Rating', NEW.RatingID); END //

CREATE TRIGGER trg_rating_bu BEFORE UPDATE ON Rating FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Rating', OLD.RatingID); END //

CREATE TRIGGER trg_rating_bd BEFORE DELETE ON Rating FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Rating', OLD.RatingID); END //

-- Watchlist triggers
CREATE TRIGGER trg_watchlist_ai AFTER INSERT ON Watchlist FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Watchlist', NEW.WatchlistID); END //

CREATE TRIGGER trg_watchlist_bu BEFORE UPDATE ON Watchlist FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Watchlist', OLD.WatchlistID); END //

CREATE TRIGGER trg_watchlist_bd BEFORE DELETE ON Watchlist FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Watchlist', OLD.WatchlistID); END //

-- Report triggers
CREATE TRIGGER trg_report_ai AFTER INSERT ON Report FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Report', NEW.ReportID); END //

CREATE TRIGGER trg_report_bu BEFORE UPDATE ON Report FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Report', OLD.ReportID); END //

CREATE TRIGGER trg_report_bd BEFORE DELETE ON Report FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Report', OLD.ReportID); END //

-- Notification triggers
CREATE TRIGGER trg_notification_ai AFTER INSERT ON Notification FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Notification', NEW.NotificationID); END //

CREATE TRIGGER trg_notification_bu BEFORE UPDATE ON Notification FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Notification', OLD.NotificationID); END //

CREATE TRIGGER trg_notification_bd BEFORE DELETE ON Notification FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Notification', OLD.NotificationID); END //

-- MessageThread triggers
CREATE TRIGGER trg_msgthread_ai AFTER INSERT ON MessageThread FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'MessageThread', NEW.ThreadID); END //

CREATE TRIGGER trg_msgthread_bu BEFORE UPDATE ON MessageThread FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'MessageThread', OLD.ThreadID); END //

CREATE TRIGGER trg_msgthread_bd BEFORE DELETE ON MessageThread FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'MessageThread', OLD.ThreadID); END //

-- Message triggers
CREATE TRIGGER trg_message_ai AFTER INSERT ON Message FOR EACH ROW
BEGIN CALL sp_audit_log('INSERT', 'Message', NEW.MessageID); END //

CREATE TRIGGER trg_message_bu BEFORE UPDATE ON Message FOR EACH ROW
BEGIN CALL sp_audit_log('UPDATE', 'Message', OLD.MessageID); END //

CREATE TRIGGER trg_message_bd BEFORE DELETE ON Message FOR EACH ROW
BEGIN CALL sp_audit_log('DELETE', 'Message', OLD.MessageID); END //

DELIMITER ;

-- ============================================================
-- SEED DATA
-- ============================================================

-- System roles
INSERT INTO sys_role (role_name) VALUES ('admin'), ('member');

-- Categories (15)
INSERT INTO
    Category (
        CategoryID,
        CategoryName,
        Description,
        IsActive
    )
VALUES (
        1,
        'Books & Textbooks',
        'Academic and general books',
        1
    ),
    (
        2,
        'Electronics',
        'Electronic devices and accessories',
        1
    ),
    (
        3,
        'Furniture',
        'Room and study furniture',
        1
    ),
    (
        4,
        'Sports & Fitness',
        'Sports equipment and fitness gear',
        1
    ),
    (
        5,
        'Clothing',
        'Clothes and accessories',
        1
    ),
    (
        6,
        'Engineering Books',
        'Engineering textbooks and references',
        1
    ),
    (
        7,
        'Science Books',
        'Science and math textbooks',
        1
    ),
    (
        8,
        'Computing',
        'Laptops, tablets, and accessories',
        1
    ),
    (
        9,
        'Mobile Phones',
        'Smartphones and accessories',
        1
    ),
    (
        10,
        'Calculators',
        'Scientific and graphing calculators',
        1
    ),
    (
        11,
        'Study Furniture',
        'Desks, chairs, and shelves',
        1
    ),
    (
        12,
        'Room Essentials',
        'Lamps, fans, and room items',
        1
    ),
    (
        13,
        'Gym Equipment',
        'Dumbbells, mats, and gear',
        1
    ),
    (
        14,
        'Racket Sports',
        'Badminton, tennis equipment',
        1
    ),
    (
        15,
        'Donations',
        'Free items given away',
        1
    );

-- NOTE: SuperAdmin account is created by running:
--   go run ./backend/cmd/seed
-- Default credentials: superadmin@iitgn.ac.in / Admin@iitgn2025