-- ============================================================
-- Campus Trading Application - Core Tables
-- Module B: All 14 domain tables
-- ============================================================

USE CampusTrading;

-- ============================================================
-- Core tables
-- ============================================================

CREATE TABLE IF NOT EXISTS Member (
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
    AccountStatus       VARCHAR(20)     NOT NULL DEFAULT 'Active',
    INDEX IDX_Member_Email (Email),
    INDEX IDX_Member_AccountStatus (AccountStatus)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Administrator (
    AdminID             INT             AUTO_INCREMENT PRIMARY KEY,
    Name                VARCHAR(100)    NOT NULL,
    Email               VARCHAR(150)    NOT NULL UNIQUE,
    PasswordHash        VARCHAR(256)    NOT NULL,
    Role                VARCHAR(20)     NOT NULL DEFAULT 'Moderator',
    CreatedDate         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    LastLoginDate       DATETIME,
    IsActive            BOOLEAN         NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Category (
    CategoryID          INT             AUTO_INCREMENT PRIMARY KEY,
    CategoryName        VARCHAR(100)    NOT NULL,
    ParentCategoryID    INT,
    Description         VARCHAR(500),
    IsActive            BOOLEAN         NOT NULL DEFAULT TRUE,
    CONSTRAINT FK_Category_Parent FOREIGN KEY (ParentCategoryID) REFERENCES Category(CategoryID) ON DELETE SET NULL,
    CONSTRAINT UQ_Category_Name_Parent UNIQUE (CategoryName, ParentCategoryID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS WishRequest (
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
    CONSTRAINT FK_WishRequest_Member FOREIGN KEY (RequesterID) REFERENCES Member(MemberID) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Listing (
    ListingID               INT             AUTO_INCREMENT PRIMARY KEY,
    SellerID                INT             NOT NULL,
    CategoryID              INT             NOT NULL,
    Title                   VARCHAR(200)    NOT NULL,
    Description             VARCHAR(2000),
    AskingPrice             DECIMAL(10,2)   NOT NULL,
    IsNegotiable            BOOLEAN         NOT NULL DEFAULT TRUE,
    `Condition`             VARCHAR(20),
    CourseCode              VARCHAR(20),
    Status                  VARCHAR(20)     NOT NULL DEFAULT 'Listed',
    CreatedDate             DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    LastModifiedDate        DATETIME        ON UPDATE CURRENT_TIMESTAMP,
    ExpiryDate              DATETIME,
    IsDonation              BOOLEAN         NOT NULL DEFAULT FALSE,
    PreferredMeetingLocation VARCHAR(200),
    WishRequestID           INT,
    CONSTRAINT FK_Listing_Seller   FOREIGN KEY (SellerID)     REFERENCES Member(MemberID)     ON UPDATE CASCADE,
    CONSTRAINT FK_Listing_Category FOREIGN KEY (CategoryID)   REFERENCES Category(CategoryID) ON UPDATE CASCADE,
    CONSTRAINT FK_Listing_Wish     FOREIGN KEY (WishRequestID) REFERENCES WishRequest(WishRequestID) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ListingImage (
    ImageID     INT             AUTO_INCREMENT PRIMARY KEY,
    ListingID   INT             NOT NULL,
    ImageURL    VARCHAR(500)    NOT NULL,
    ImageOrder  INT             NOT NULL,
    UploadedDate DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Image_Listing FOREIGN KEY (ListingID) REFERENCES Listing(ListingID) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT UQ_Image_Order UNIQUE (ListingID, ImageOrder)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Offer (
    OfferID         INT             AUTO_INCREMENT PRIMARY KEY,
    ListingID       INT             NOT NULL,
    BuyerID         INT             NOT NULL,
    OfferedPrice    DECIMAL(10,2)   NOT NULL,
    AgreedPrice     DECIMAL(10,2),
    OfferMessage    VARCHAR(500),
    OfferStatus     VARCHAR(20)     NOT NULL DEFAULT 'Submitted',
    SubmittedDate   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ResponseDate    DATETIME,
    ExpiryDate      DATETIME,
    CONSTRAINT FK_Offer_Listing FOREIGN KEY (ListingID) REFERENCES Listing(ListingID) ON UPDATE CASCADE,
    CONSTRAINT FK_Offer_Buyer   FOREIGN KEY (BuyerID)   REFERENCES Member(MemberID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `Transaction` (
    TransactionID   INT             AUTO_INCREMENT PRIMARY KEY,
    ListingID       INT             NOT NULL,
    SellerID        INT             NOT NULL,
    BuyerID         INT             NOT NULL,
    OfferID         INT,
    AgreedPrice     DECIMAL(10,2)   NOT NULL,
    TransactionDate DATETIME,
    SellerConfirmed BOOLEAN         NOT NULL DEFAULT FALSE,
    BuyerConfirmed  BOOLEAN         NOT NULL DEFAULT FALSE,
    Status          VARCHAR(20)     NOT NULL DEFAULT 'Scheduled',
    CreatedDate     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Tx_Listing FOREIGN KEY (ListingID) REFERENCES Listing(ListingID),
    CONSTRAINT FK_Tx_Seller  FOREIGN KEY (SellerID)  REFERENCES Member(MemberID),
    CONSTRAINT FK_Tx_Buyer   FOREIGN KEY (BuyerID)   REFERENCES Member(MemberID),
    CONSTRAINT FK_Tx_Offer   FOREIGN KEY (OfferID)   REFERENCES Offer(OfferID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Rating (
    RatingID        INT             AUTO_INCREMENT PRIMARY KEY,
    TransactionID   INT             NOT NULL,
    RaterID         INT             NOT NULL,
    RatedID         INT             NOT NULL,
    Stars           INT             NOT NULL,
    ReviewText      VARCHAR(1000),
    RatingDate      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Rating_Transaction FOREIGN KEY (TransactionID) REFERENCES `Transaction`(TransactionID) ON UPDATE CASCADE,
    CONSTRAINT FK_Rating_Rater       FOREIGN KEY (RaterID)       REFERENCES Member(MemberID),
    CONSTRAINT FK_Rating_Rated       FOREIGN KEY (RatedID)       REFERENCES Member(MemberID),
    CONSTRAINT UQ_Rating_Tx_Rater    UNIQUE (TransactionID, RaterID),
    CONSTRAINT CHK_Stars             CHECK (Stars BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS MessageThread (
    ThreadID    INT             AUTO_INCREMENT PRIMARY KEY,
    ListingID   INT             NOT NULL,
    BuyerID     INT             NOT NULL,
    OfferID     INT             NOT NULL,
    CreatedDate DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    IsActive    BOOLEAN         NOT NULL DEFAULT TRUE,
    CONSTRAINT FK_Thread_Listing FOREIGN KEY (ListingID) REFERENCES Listing(ListingID),
    CONSTRAINT FK_Thread_Buyer   FOREIGN KEY (BuyerID)   REFERENCES Member(MemberID),
    CONSTRAINT FK_Thread_Offer   FOREIGN KEY (OfferID)   REFERENCES Offer(OfferID),
    CONSTRAINT UQ_Thread         UNIQUE (ListingID, BuyerID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Message (
    MessageID   INT             AUTO_INCREMENT PRIMARY KEY,
    ThreadID    INT             NOT NULL,
    SenderID    INT             NOT NULL,
    MessageText VARCHAR(2000)   NOT NULL,
    SentDate    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FK_Message_Thread FOREIGN KEY (ThreadID) REFERENCES MessageThread(ThreadID) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_Message_Sender FOREIGN KEY (SenderID) REFERENCES Member(MemberID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Notification (
    NotificationID      INT             AUTO_INCREMENT PRIMARY KEY,
    RecipientID         INT             NOT NULL,
    NotificationType    VARCHAR(50)     NOT NULL,
    Title               VARCHAR(200),
    Message             VARCHAR(1000)   NOT NULL,
    RelatedListingID    INT,
    RelatedOfferID      INT,
    RelatedTransactionID INT,
    IsRead              BOOLEAN         NOT NULL DEFAULT FALSE,
    CreatedDate         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ReadDate            DATETIME,
    CONSTRAINT FK_Notif_Recipient FOREIGN KEY (RecipientID)          REFERENCES Member(MemberID) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_Notif_Listing   FOREIGN KEY (RelatedListingID)     REFERENCES Listing(ListingID),
    CONSTRAINT FK_Notif_Offer     FOREIGN KEY (RelatedOfferID)       REFERENCES Offer(OfferID),
    CONSTRAINT FK_Notif_Tx        FOREIGN KEY (RelatedTransactionID) REFERENCES `Transaction`(TransactionID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Report (
    ReportID            INT             AUTO_INCREMENT PRIMARY KEY,
    ReporterID          INT             NOT NULL,
    ReportedMemberID    INT,
    ReportedListingID   INT,
    ReportType          VARCHAR(50)     NOT NULL,
    Description         VARCHAR(2000)   NOT NULL,
    Status              VARCHAR(20)     NOT NULL DEFAULT 'Submitted',
    SubmittedDate       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ResolvedDate        DATETIME,
    ResolvedByAdminID   INT,
    Resolution          VARCHAR(1000),
    CONSTRAINT FK_Report_Reporter        FOREIGN KEY (ReporterID)         REFERENCES Member(MemberID),
    CONSTRAINT FK_Report_ReportedMember  FOREIGN KEY (ReportedMemberID)   REFERENCES Member(MemberID),
    CONSTRAINT FK_Report_ReportedListing FOREIGN KEY (ReportedListingID)  REFERENCES Listing(ListingID),
    CONSTRAINT FK_Report_Admin           FOREIGN KEY (ResolvedByAdminID)  REFERENCES Administrator(AdminID) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS Watchlist (
    WatchlistID         INT             AUTO_INCREMENT PRIMARY KEY,
    MemberID            INT             NOT NULL,
    ListingID           INT             NOT NULL,
    AddedDate           DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    NotifyOnPriceChange BOOLEAN         NOT NULL DEFAULT TRUE,
    NotifyOnStatusChange BOOLEAN        NOT NULL DEFAULT TRUE,
    CONSTRAINT FK_Watchlist_Member  FOREIGN KEY (MemberID)  REFERENCES Member(MemberID)  ON DELETE CASCADE,
    CONSTRAINT FK_Watchlist_Listing FOREIGN KEY (ListingID) REFERENCES Listing(ListingID) ON DELETE CASCADE,
    CONSTRAINT UQ_Watchlist         UNIQUE (MemberID, ListingID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
