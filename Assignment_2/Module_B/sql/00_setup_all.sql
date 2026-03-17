-- ============================================================
-- Campus Trading Application - MASTER SETUP SCRIPT
-- Run this single file to set up the entire database from scratch.
-- Usage:
--     mysql -u root -p CampusTrading < sql/00_setup_all.sql
-- ============================================================

USE CampusTrading;

-- Disable FK checks so we can drop/create in any order
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- STEP 1: Drop everything (clean slate)
-- ============================================================
DROP TABLE IF EXISTS AuditLog;
DROP TABLE IF EXISTS UserGroupMapping;
DROP TABLE IF EXISTS UserGroup;
DROP TABLE IF EXISTS Session;
DROP TABLE IF EXISTS `User`;
DROP TABLE IF EXISTS Watchlist;
DROP TABLE IF EXISTS Report;
DROP TABLE IF EXISTS Notification;
DROP TABLE IF EXISTS Message;
DROP TABLE IF EXISTS MessageThread;
DROP TABLE IF EXISTS Rating;
DROP TABLE IF EXISTS `Transaction`;
DROP TABLE IF EXISTS Offer;
DROP TABLE IF EXISTS ListingImage;
DROP TABLE IF EXISTS Listing;
DROP TABLE IF EXISTS WishRequest;
DROP TABLE IF EXISTS Category;
DROP TABLE IF EXISTS Administrator;
DROP TABLE IF EXISTS Member;

-- ============================================================
-- STEP 2: Core domain tables (no foreign key deps)
-- ============================================================

CREATE TABLE Member (
    MemberID            INT             AUTO_INCREMENT PRIMARY KEY,
    Name                VARCHAR(100)    NOT NULL,
    Email               VARCHAR(150)    NOT NULL UNIQUE,
    PasswordHash        VARCHAR(256)    NOT NULL,
    ContactNumber       VARCHAR(20)     NOT NULL,
    Department          VARCHAR(100),
    YearOfStudy         INT,
    Hostel              VARCHAR(100),
    RoomNumber          VARCHAR(20),
    Image               VARCHAR(500),
    Bio                 VARCHAR(500),
    IsVerified          BOOLEAN         NOT NULL DEFAULT FALSE,
    VerificationDate    DATETIME,
    AccountCreationDate DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    AccountStatus       VARCHAR(20)     NOT NULL DEFAULT 'Active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Administrator (
    AdminID             INT             AUTO_INCREMENT PRIMARY KEY,
    Name                VARCHAR(100)    NOT NULL,
    Email               VARCHAR(150)    NOT NULL UNIQUE,
    PasswordHash        VARCHAR(256)    NOT NULL,
    Role                VARCHAR(20)     NOT NULL DEFAULT 'Moderator',
    CreatedDate         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    LastLoginDate       DATETIME,
    IsActive            BOOLEAN         NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Category (
    CategoryID          INT             AUTO_INCREMENT PRIMARY KEY,
    CategoryName        VARCHAR(100)    NOT NULL,
    ParentCategoryID    INT,
    Description         VARCHAR(500),
    IsActive            BOOLEAN         NOT NULL DEFAULT TRUE,
    CONSTRAINT FK_Category_Parent FOREIGN KEY (ParentCategoryID)
        REFERENCES Category(CategoryID) ON DELETE SET NULL,
    CONSTRAINT UQ_Category_Name_Parent UNIQUE (CategoryName, ParentCategoryID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE WishRequest (
    WishRequestID       INT             AUTO_INCREMENT PRIMARY KEY,
    RequesterID         INT             NOT NULL,
    ItemDescription     VARCHAR(500)    NOT NULL,
    MinBudget           DECIMAL(10,2),
    MaxBudget           DECIMAL(10,2),
    PreferredCondition  VARCHAR(20),
    NeededByDate        DATE,
    AdditionalDetails   VARCHAR(1000),
    Status              VARCHAR(20)     NOT NULL DEFAULT 'Active',
    CreatedDate         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FulfilledDate       DATETIME,
    CONSTRAINT FK_WishRequest_Member FOREIGN KEY (RequesterID)
        REFERENCES Member(MemberID) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Listing (
    ListingID                INT             AUTO_INCREMENT PRIMARY KEY,
    SellerID                 INT             NOT NULL,
    CategoryID               INT             NOT NULL,
    Title                    VARCHAR(200)    NOT NULL,
    Description              VARCHAR(2000),
    AskingPrice              DECIMAL(10,2)   NOT NULL,
    IsNegotiable             BOOLEAN         NOT NULL DEFAULT TRUE,
    `Condition`              VARCHAR(20),
    CourseCode               VARCHAR(20),
    Status                   VARCHAR(20)     NOT NULL DEFAULT 'Listed',
    CreatedDate              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    LastModifiedDate         DATETIME        ON UPDATE CURRENT_TIMESTAMP,
    ExpiryDate               DATETIME,
    IsDonation               BOOLEAN         NOT NULL DEFAULT FALSE,
    PreferredMeetingLocation VARCHAR(200),
    WishRequestID            INT,
    CONSTRAINT FK_Listing_Seller   FOREIGN KEY (SellerID)      REFERENCES Member(MemberID)     ON UPDATE CASCADE,
    CONSTRAINT FK_Listing_Category FOREIGN KEY (CategoryID)    REFERENCES Category(CategoryID) ON UPDATE CASCADE,
    CONSTRAINT FK_Listing_Wish     FOREIGN KEY (WishRequestID) REFERENCES WishRequest(WishRequestID) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ListingImage (
    ImageID      INT          AUTO_INCREMENT PRIMARY KEY,
    ListingID    INT          NOT NULL,
    ImageURL     VARCHAR(500) NOT NULL,
    ImageOrder   INT          NOT NULL,
    UploadedDate DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Image_Listing FOREIGN KEY (ListingID)
        REFERENCES Listing(ListingID) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT UQ_Image_Order UNIQUE (ListingID, ImageOrder)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Offer (
    OfferID       INT           AUTO_INCREMENT PRIMARY KEY,
    ListingID     INT           NOT NULL,
    BuyerID       INT           NOT NULL,
    OfferedPrice  DECIMAL(10,2) NOT NULL,
    AgreedPrice   DECIMAL(10,2),
    OfferMessage  VARCHAR(500),
    OfferStatus   VARCHAR(20)   NOT NULL DEFAULT 'Submitted',
    SubmittedDate DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ResponseDate  DATETIME,
    ExpiryDate    DATETIME,
    CONSTRAINT FK_Offer_Listing FOREIGN KEY (ListingID) REFERENCES Listing(ListingID)  ON UPDATE CASCADE,
    CONSTRAINT FK_Offer_Buyer   FOREIGN KEY (BuyerID)   REFERENCES Member(MemberID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `Transaction` (
    TransactionID   INT           AUTO_INCREMENT PRIMARY KEY,
    ListingID       INT           NOT NULL,
    SellerID        INT           NOT NULL,
    BuyerID         INT           NOT NULL,
    OfferID         INT,
    AgreedPrice     DECIMAL(10,2) NOT NULL,
    TransactionDate DATETIME,
    SellerConfirmed BOOLEAN       NOT NULL DEFAULT FALSE,
    BuyerConfirmed  BOOLEAN       NOT NULL DEFAULT FALSE,
    Status          VARCHAR(20)   NOT NULL DEFAULT 'Scheduled',
    CreatedDate     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Tx_Listing FOREIGN KEY (ListingID) REFERENCES Listing(ListingID),
    CONSTRAINT FK_Tx_Seller  FOREIGN KEY (SellerID)  REFERENCES Member(MemberID),
    CONSTRAINT FK_Tx_Buyer   FOREIGN KEY (BuyerID)   REFERENCES Member(MemberID),
    CONSTRAINT FK_Tx_Offer   FOREIGN KEY (OfferID)   REFERENCES Offer(OfferID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Rating (
    RatingID      INT          AUTO_INCREMENT PRIMARY KEY,
    TransactionID INT          NOT NULL,
    RaterID       INT          NOT NULL,
    RatedID       INT          NOT NULL,
    Stars         INT          NOT NULL,
    ReviewText    VARCHAR(1000),
    RatingDate    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Rating_Transaction FOREIGN KEY (TransactionID) REFERENCES `Transaction`(TransactionID) ON UPDATE CASCADE,
    CONSTRAINT FK_Rating_Rater       FOREIGN KEY (RaterID)       REFERENCES Member(MemberID),
    CONSTRAINT FK_Rating_Rated       FOREIGN KEY (RatedID)       REFERENCES Member(MemberID),
    CONSTRAINT UQ_Rating_Tx_Rater    UNIQUE (TransactionID, RaterID),
    CONSTRAINT CHK_Stars             CHECK (Stars BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE MessageThread (
    ThreadID    INT      AUTO_INCREMENT PRIMARY KEY,
    ListingID   INT      NOT NULL,
    BuyerID     INT      NOT NULL,
    OfferID     INT      NOT NULL,
    CreatedDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    IsActive    BOOLEAN  NOT NULL DEFAULT TRUE,
    CONSTRAINT FK_Thread_Listing FOREIGN KEY (ListingID) REFERENCES Listing(ListingID),
    CONSTRAINT FK_Thread_Buyer   FOREIGN KEY (BuyerID)   REFERENCES Member(MemberID),
    CONSTRAINT FK_Thread_Offer   FOREIGN KEY (OfferID)   REFERENCES Offer(OfferID),
    CONSTRAINT UQ_Thread         UNIQUE (ListingID, BuyerID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Message (
    MessageID   INT           AUTO_INCREMENT PRIMARY KEY,
    ThreadID    INT           NOT NULL,
    SenderID    INT           NOT NULL,
    MessageText VARCHAR(2000) NOT NULL,
    SentDate    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Message_Thread FOREIGN KEY (ThreadID) REFERENCES MessageThread(ThreadID) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_Message_Sender FOREIGN KEY (SenderID) REFERENCES Member(MemberID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Notification (
    NotificationID       INT           AUTO_INCREMENT PRIMARY KEY,
    RecipientID          INT           NOT NULL,
    NotificationType     VARCHAR(50)   NOT NULL,
    Title                VARCHAR(200),
    Message              VARCHAR(1000) NOT NULL,
    RelatedListingID     INT,
    RelatedOfferID       INT,
    RelatedTransactionID INT,
    IsRead               BOOLEAN       NOT NULL DEFAULT FALSE,
    CreatedDate          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ReadDate             DATETIME,
    CONSTRAINT FK_Notif_Recipient FOREIGN KEY (RecipientID)          REFERENCES Member(MemberID)       ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_Notif_Listing   FOREIGN KEY (RelatedListingID)     REFERENCES Listing(ListingID),
    CONSTRAINT FK_Notif_Offer     FOREIGN KEY (RelatedOfferID)       REFERENCES Offer(OfferID),
    CONSTRAINT FK_Notif_Tx        FOREIGN KEY (RelatedTransactionID) REFERENCES `Transaction`(TransactionID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Report (
    ReportID          INT           AUTO_INCREMENT PRIMARY KEY,
    ReporterID        INT           NOT NULL,
    ReportedMemberID  INT,
    ReportedListingID INT,
    ReportType        VARCHAR(50)   NOT NULL,
    Description       VARCHAR(2000) NOT NULL,
    Status            VARCHAR(20)   NOT NULL DEFAULT 'Submitted',
    SubmittedDate     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ResolvedDate      DATETIME,
    ResolvedByAdminID INT,
    Resolution        VARCHAR(1000),
    CONSTRAINT FK_Report_Reporter        FOREIGN KEY (ReporterID)        REFERENCES Member(MemberID),
    CONSTRAINT FK_Report_ReportedMember  FOREIGN KEY (ReportedMemberID)  REFERENCES Member(MemberID),
    CONSTRAINT FK_Report_ReportedListing FOREIGN KEY (ReportedListingID) REFERENCES Listing(ListingID),
    CONSTRAINT FK_Report_Admin           FOREIGN KEY (ResolvedByAdminID) REFERENCES Administrator(AdminID) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Watchlist (
    WatchlistID          INT      AUTO_INCREMENT PRIMARY KEY,
    MemberID             INT      NOT NULL,
    ListingID            INT      NOT NULL,
    AddedDate            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    NotifyOnPriceChange  BOOLEAN  NOT NULL DEFAULT TRUE,
    NotifyOnStatusChange BOOLEAN  NOT NULL DEFAULT TRUE,
    CONSTRAINT FK_Watchlist_Member  FOREIGN KEY (MemberID)  REFERENCES Member(MemberID)  ON DELETE CASCADE,
    CONSTRAINT FK_Watchlist_Listing FOREIGN KEY (ListingID) REFERENCES Listing(ListingID) ON DELETE CASCADE,
    CONSTRAINT UQ_Watchlist         UNIQUE (MemberID, ListingID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- STEP 3: Auth tables (depend on Member & Administrator)
-- ============================================================

CREATE TABLE `User` (
    UserID       INT                        AUTO_INCREMENT PRIMARY KEY,
    Username     VARCHAR(50)                NOT NULL UNIQUE,
    Email        VARCHAR(150)               NOT NULL UNIQUE,
    PasswordHash VARCHAR(256)               NOT NULL,
    Role         ENUM('Admin','RegularUser') NOT NULL DEFAULT 'RegularUser',
    IsActive     BOOLEAN                    NOT NULL DEFAULT TRUE,
    CreatedAt    DATETIME                   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt    DATETIME                   NULL ON UPDATE CURRENT_TIMESTAMP,
    LastLoginAt  DATETIME,
    MemberID     INT,
    AdminID      INT,
    CONSTRAINT FK_User_Member FOREIGN KEY (MemberID) REFERENCES Member(MemberID)        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT FK_User_Admin  FOREIGN KEY (AdminID)  REFERENCES Administrator(AdminID)  ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX IDX_User_Username (Username),
    INDEX IDX_User_Email    (Email),
    INDEX IDX_User_Role     (Role),
    INDEX IDX_User_MemberID (MemberID),
    INDEX IDX_User_AdminID  (AdminID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Session (
    SessionID  INT          AUTO_INCREMENT PRIMARY KEY,
    UserID     INT          NOT NULL,
    Token      VARCHAR(512) NOT NULL,
    TokenJTI   VARCHAR(64)  NOT NULL UNIQUE,
    IssuedAt   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ExpiresAt  DATETIME     NOT NULL,
    IsRevoked  BOOLEAN      NOT NULL DEFAULT FALSE,
    RevokedAt  DATETIME,
    IPAddress  VARCHAR(45),
    UserAgent  VARCHAR(512),
    CONSTRAINT FK_Session_User FOREIGN KEY (UserID) REFERENCES `User`(UserID) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX IDX_Session_Token     (Token(255)),
    INDEX IDX_Session_TokenJTI  (TokenJTI),
    INDEX IDX_Session_UserID    (UserID),
    INDEX IDX_Session_ExpiresAt (ExpiresAt),
    INDEX IDX_Session_IsRevoked (IsRevoked)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE UserGroup (
    GroupID     INT          AUTO_INCREMENT PRIMARY KEY,
    GroupName   VARCHAR(50)  NOT NULL UNIQUE,
    Description VARCHAR(256),
    Permissions JSON,
    IsActive    BOOLEAN      NOT NULL DEFAULT TRUE,
    CreatedAt   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt   DATETIME     NULL ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE UserGroupMapping (
    MappingID  INT      AUTO_INCREMENT PRIMARY KEY,
    UserID     INT      NOT NULL,
    GroupID    INT      NOT NULL,
    AssignedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    AssignedBy INT,
    CONSTRAINT FK_UGM_User       FOREIGN KEY (UserID)     REFERENCES `User`(UserID)      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_UGM_Group      FOREIGN KEY (GroupID)    REFERENCES UserGroup(GroupID)  ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_UGM_AssignedBy FOREIGN KEY (AssignedBy) REFERENCES `User`(UserID)      ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT UQ_UserGroup      UNIQUE (UserID, GroupID),
    INDEX IDX_UGM_UserID  (UserID),
    INDEX IDX_UGM_GroupID (GroupID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE AuditLog (
    LogID          INT          AUTO_INCREMENT PRIMARY KEY,
    Timestamp      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UserID         INT,
    Username       VARCHAR(50),
    Action         VARCHAR(20)  NOT NULL,
    TableName      VARCHAR(50),
    RecordID       INT,
    OldValues      JSON,
    NewValues      JSON,
    IPAddress      VARCHAR(45),
    UserAgent      VARCHAR(512),
    APIEndpoint    VARCHAR(200),
    HTTPMethod     VARCHAR(10),
    ResponseStatus INT,
    ResponseTime   INT,
    IsAuthorized   BOOLEAN      NOT NULL DEFAULT TRUE,
    ErrorMessage   VARCHAR(500),
    INDEX IDX_AuditLog_Timestamp    (Timestamp),
    INDEX IDX_AuditLog_UserID       (UserID),
    INDEX IDX_AuditLog_TableName    (TableName),
    INDEX IDX_AuditLog_Action       (Action),
    INDEX IDX_AuditLog_IsAuthorized (IsAuthorized),
    INDEX IDX_AuditLog_User_Action  (UserID, Action),
    INDEX IDX_AuditLog_Table_Action (TableName, Action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- STEP 4: Seed default data
-- ============================================================

-- Default groups
INSERT INTO UserGroup (GroupID, GroupName, Description, Permissions) VALUES
(1, 'Administrators', 'Full system access',         '["*"]'),
(2, 'Moderators',     'Content moderation',         '["reports:*","listings:*","members:read"]'),
(3, 'Support',        'Customer support access',    '["reports:read","members:read"]'),
(4, 'Members',        'Regular campus members',     '["listings:*:own","offers:*:own","profile:*:own"]');

-- Admin user in Administrator table
INSERT INTO Administrator (AdminID, Name, Email, PasswordHash, Role, IsActive)
VALUES (1, 'System Admin', 'admin@iitgn.ac.in', '$2b$12$placeholder_change_me', 'SuperAdmin', TRUE);

-- Members
INSERT INTO Member (MemberID, Name, Email, PasswordHash, ContactNumber, Department, YearOfStudy, Hostel, RoomNumber, Bio, IsVerified, AccountStatus) VALUES
(1, 'Amal Perera',     'amal.perera@iitgn.ac.in',    '$2b$12$placeholder_change_me', '9876543210', 'Computer Science', 3, 'Hostel A', 'A-101', 'CS student, selling textbooks',       TRUE,  'Active'),
(2, 'Nimali Fernando', 'nimali.fernando@iitgn.ac.in', '$2b$12$placeholder_change_me', '9876543211', 'Electrical Engg',  2, 'Hostel B', 'B-204', 'Looking for circuit analysis books',  FALSE, 'Active'),
(3, 'Kavindu Silva',   'kavindu.silva@iitgn.ac.in',   '$2b$12$placeholder_change_me', '9876543212', 'Mechanical Engg',  4, 'Hostel A', 'A-305', 'Final year, selling everything!',     TRUE,  'Active'),
(4, 'Priya Nair',      'priya.nair@iitgn.ac.in',      '$2b$12$placeholder_change_me', '9876543213', 'Mathematics',      1, 'Hostel C', 'C-108', 'First year, need study materials',    FALSE, 'Active'),
(5, 'Ravindu Bandara', 'ravindu.bandara@iitgn.ac.in', '$2b$12$placeholder_change_me', '9876543214', 'Physics',          3, 'Hostel B', 'B-110', 'Physics tutor',                       TRUE,  'Active'),
(6, 'Anjali Sharma',   'anjali.sharma@iitgn.ac.in',   '$2b$12$placeholder_change_me', '9876543215', 'Chemistry',        2, 'Hostel C', 'C-212', 'Chem enthusiast',                     FALSE, 'Active'),
(7, 'Vikram Mehta',    'vikram.mehta@iitgn.ac.in',    '$2b$12$placeholder_change_me', '9876543216', 'Computer Science', 4, 'Hostel A', 'A-410', 'Graduating, selling everything',      TRUE,  'Active'),
(8, 'Sana Ahmed',      'sana.ahmed@iitgn.ac.in',      '$2b$12$placeholder_change_me', '9876543217', 'Biotechnology',    2, 'Hostel D', 'D-105', 'Bio student',                         FALSE, 'Active');

-- Auth users (plain text passwords shown below — hashes must be regenerated via seed_passwords.py)
-- admin / admin123   |   amal.perera / password123   |   etc.
INSERT INTO `User` (UserID, Username, Email, PasswordHash, Role, IsActive, AdminID) VALUES
(1, 'admin', 'admin@iitgn.ac.in', '$2b$12$placeholder_change_me', 'Admin', TRUE, 1);

INSERT INTO `User` (UserID, Username, Email, PasswordHash, Role, IsActive, MemberID) VALUES
(2, 'amal.perera',    'amal.perera@iitgn.ac.in',    '$2b$12$placeholder_change_me', 'RegularUser', TRUE, 1),
(3, 'nimali.fernando','nimali.fernando@iitgn.ac.in', '$2b$12$placeholder_change_me', 'RegularUser', TRUE, 2),
(4, 'kavindu.silva',  'kavindu.silva@iitgn.ac.in',   '$2b$12$placeholder_change_me', 'RegularUser', TRUE, 3),
(5, 'ravindu.bandara','ravindu.bandara@iitgn.ac.in', '$2b$12$placeholder_change_me', 'RegularUser', TRUE, 5);

-- Group assignments
INSERT INTO UserGroupMapping (UserID, GroupID, AssignedBy) VALUES
(1, 1, 1), (2, 4, 1), (3, 4, 1), (4, 4, 1), (5, 4, 1);

-- Categories
INSERT INTO Category (CategoryID, CategoryName, ParentCategoryID, Description, IsActive) VALUES
(1,  'Books & Notes',     NULL, 'Textbooks, notebooks, study materials', TRUE),
(2,  'Textbooks',         1,    'Course textbooks',                       TRUE),
(3,  'Notes & Guides',    1,    'Handwritten notes and study guides',     TRUE),
(4,  'Electronics',       NULL, 'Gadgets, components, devices',           TRUE),
(5,  'Calculators',       4,    'Scientific and graphing calculators',    TRUE),
(6,  'Laptops & Tablets', 4,    'Portable computing devices',             TRUE),
(7,  'Lab Equipment',     4,    'Lab instruments and tools',              TRUE),
(8,  'Stationery',        NULL, 'Pens, rulers, drawing tools',            TRUE),
(9,  'Clothing',          NULL, 'Clothes, uniforms, sportswear',          TRUE),
(10, 'Sports & Fitness',  NULL, 'Sports equipment and gear',              TRUE),
(11, 'Furniture',         NULL, 'Desks, chairs, shelves',                 TRUE),
(12, 'Misc / Other',      NULL, 'Anything else',                          TRUE);

-- Listings
INSERT INTO Listing (ListingID, SellerID, CategoryID, Title, Description, AskingPrice, IsNegotiable, `Condition`, CourseCode, Status, IsDonation, PreferredMeetingLocation) VALUES
(1,  1, 2, 'Calculus – Stewart 8th Ed',        'Very good condition. Used one semester.',    450.00, TRUE,  'Good',     'MA101', 'Listed',  FALSE, 'Library'),
(2,  1, 2, 'Data Structures – Cormen (CLRS)',  'Some highlights.',                            600.00, TRUE,  'Good',     'CS201', 'Listed',  FALSE, 'CSE Dept'),
(3,  3, 5, 'Casio FX-991EX Calculator',        'Works perfectly.',                            500.00, FALSE, 'Like New', NULL,    'Listed',  FALSE, 'Hostel A Gate'),
(4,  7, 6, 'Lenovo ThinkPad (i5, 8GB)',        'Used 2 years. Battery 4 hrs.',             18000.00, TRUE,  'Good',     NULL,    'Listed',  FALSE, 'Main Gate'),
(5,  5, 7, 'Digital Multimeter VC830L',         'Accurate, 2 years old.',                      800.00, TRUE,  'Good',     NULL,    'Listed',  FALSE, 'Physics Lab'),
(6,  2, 3, 'Circuit Analysis Notes – Year 2',  'Handwritten, very neat.',                     150.00, FALSE, 'Like New', 'EE201', 'Listed',  FALSE, 'EE Dept'),
(7,  6, 2, 'Atkins Physical Chemistry 10th',   'Few annotations.',                             700.00, TRUE,  'Good',     'CH101', 'Listed',  FALSE, 'Library'),
(8,  1, 2, 'Linear Algebra – Gilbert Strang',  'Perfect condition, never used.',              350.00, TRUE,  'New',      'MA201', 'Listed',  FALSE, 'Library'),
(9,  3, 9, 'IITGN Sports T-Shirt (XL)',        'Worn once.',                                   80.00, FALSE, 'Like New', NULL,    'Listed',  FALSE, 'Hostel A Gate'),
(10, 4, 2, 'Introduction to Algorithms',        'Donating – no longer needed.',                  0.00, FALSE, 'Fair',     'CS201', 'Listed',  TRUE,  'Library'),
(11, 7, 6, 'Dell XPS 13 (i7, 16GB)',           'Minor scratch.',                            32000.00, TRUE,  'Good',     NULL,    'Sold',    FALSE, 'Main Gate'),
(12, 5, 7, 'Oscilloscope DS1054Z',              'Fully functional.',                         12000.00, TRUE,  'Good',     NULL,    'Pending', FALSE, 'Physics Lab'),
(13, 3, 11,'IKEA Study Table',                  'Needs disassembly.',                          2500.00, TRUE,  'Good',     NULL,    'Listed',  FALSE, 'Hostel A'),
(14, 8, 2, 'Molecular Biology – Lewin 9th Ed', 'Excellent condition.',                         550.00, TRUE,  'Like New', 'BT301', 'Listed',  FALSE, 'Bio Lab');

-- Offers
INSERT INTO Offer (OfferID, ListingID, BuyerID, OfferedPrice, AgreedPrice, OfferMessage, OfferStatus, ExpiryDate) VALUES
(1, 1, 2, 400.00,    NULL,     'Would you take 400?',   'Submitted', DATE_ADD(NOW(), INTERVAL 3 DAY)),
(2, 1, 4, 420.00,    NULL,     'Best I can do.',        'Submitted', DATE_ADD(NOW(), INTERVAL 3 DAY)),
(3, 3, 1, 450.00,    NULL,     'Is 450 okay?',          'Submitted', DATE_ADD(NOW(), INTERVAL 2 DAY)),
(4, 4, 5, 16000.00,  NULL,     'Negotiable further?',   'Submitted', DATE_ADD(NOW(), INTERVAL 5 DAY)),
(5, 12,1, 10000.00,  10000.00, 'Deal!',                 'Accepted',  DATE_ADD(NOW(), INTERVAL 7 DAY)),
(6, 11,2, 30000.00,  30000.00, 'Accepted.',             'Accepted',  DATE_ADD(NOW(), INTERVAL 7 DAY));

-- Transactions
INSERT INTO `Transaction` (TransactionID, ListingID, SellerID, BuyerID, OfferID, AgreedPrice, TransactionDate, SellerConfirmed, BuyerConfirmed, Status) VALUES
(1, 11, 7, 2, 6, 30000.00, DATE_SUB(NOW(), INTERVAL 5 DAY), TRUE,  TRUE,  'Completed'),
(2, 12, 5, 1, 5, 10000.00, DATE_ADD(NOW(), INTERVAL 2 DAY), FALSE, FALSE, 'Scheduled');

-- Ratings
INSERT INTO Rating (RatingID, TransactionID, RaterID, RatedID, Stars, ReviewText) VALUES
(1, 1, 2, 7, 5, 'Great seller! Laptop exactly as described.'),
(2, 1, 7, 2, 4, 'Good buyer, paid promptly.');

-- Notifications
INSERT INTO Notification (NotificationID, RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID, IsRead) VALUES
(1, 1, 'OfferReceived',       'New Offer on Calculus',  'You received ₹400 on your Calculus textbook.',  1, 1, FALSE),
(2, 1, 'OfferReceived',       'New Offer on Calculus',  'You received ₹420 on your Calculus textbook.',  1, 2, FALSE),
(3, 5, 'TransactionCompleted','Sale Scheduled',         'Oscilloscope transaction is scheduled.',        12, 5, TRUE),
(4, 2, 'TransactionCompleted','Purchase Confirmed',     'Dell XPS 13 purchase complete!',                11, 6, FALSE);

-- ============================================================
-- STEP 5: Triggers (detect direct DB modifications)
-- ============================================================

DROP TRIGGER IF EXISTS trg_Member_Update_Audit;
DROP TRIGGER IF EXISTS trg_Listing_Update_Audit;
DROP TRIGGER IF EXISTS trg_Member_Delete_Audit;

DELIMITER //

CREATE TRIGGER trg_Member_Update_Audit
AFTER UPDATE ON Member FOR EACH ROW
BEGIN
    IF @api_call IS NULL OR @api_call != 1 THEN
        INSERT INTO AuditLog (Action, TableName, RecordID, OldValues, NewValues, IsAuthorized)
        VALUES ('UPDATE', 'Member', NEW.MemberID,
            JSON_OBJECT('Name', OLD.Name, 'Email', OLD.Email, 'AccountStatus', OLD.AccountStatus),
            JSON_OBJECT('Name', NEW.Name, 'Email', NEW.Email, 'AccountStatus', NEW.AccountStatus),
            FALSE);
    END IF;
END//

CREATE TRIGGER trg_Listing_Update_Audit
AFTER UPDATE ON Listing FOR EACH ROW
BEGIN
    IF @api_call IS NULL OR @api_call != 1 THEN
        INSERT INTO AuditLog (Action, TableName, RecordID, OldValues, NewValues, IsAuthorized)
        VALUES ('UPDATE', 'Listing', NEW.ListingID,
            JSON_OBJECT('Title', OLD.Title, 'AskingPrice', OLD.AskingPrice, 'Status', OLD.Status),
            JSON_OBJECT('Title', NEW.Title, 'AskingPrice', NEW.AskingPrice, 'Status', NEW.Status),
            FALSE);
    END IF;
END//

CREATE TRIGGER trg_Member_Delete_Audit
AFTER DELETE ON Member FOR EACH ROW
BEGIN
    IF @api_call IS NULL OR @api_call != 1 THEN
        INSERT INTO AuditLog (Action, TableName, RecordID, OldValues, IsAuthorized)
        VALUES ('DELETE', 'Member', OLD.MemberID,
            JSON_OBJECT('Name', OLD.Name, 'Email', OLD.Email),
            FALSE);
    END IF;
END//

DELIMITER ;

-- ============================================================
-- STEP 6: Re-enable FK checks
-- ============================================================
SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- Done! Summary:
--   Tables: Member, Administrator, Category, WishRequest,
--           Listing, ListingImage, Offer, Transaction, Rating,
--           MessageThread, Message, Notification, Report, Watchlist,
--           User, Session, UserGroup, UserGroupMapping, AuditLog
--   Seed data: 8 members, 1 admin, 12 categories, 14 listings,
--              6 offers, 2 transactions, 2 ratings, 4 notifications
--   Triggers: 3 (detect direct DB modifications)
-- ============================================================
SELECT 'Setup complete! All tables created and seeded.' AS Status;
