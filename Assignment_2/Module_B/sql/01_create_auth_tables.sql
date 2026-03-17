-- ============================================================
-- Campus Trading Application - Authentication Tables
-- Module B: Local API Development, RBAC, Database Optimization
-- ============================================================
-- NOTE: Run this file AFTER 02_campus_trading.sql
--       so that Member and Administrator tables exist first.
-- ============================================================

USE CampusTrading;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS AuditLog;
DROP TABLE IF EXISTS UserGroupMapping;
DROP TABLE IF EXISTS UserGroup;
DROP TABLE IF EXISTS Session;
DROP TABLE IF EXISTS `User`;

-- ============================================================
-- 1. User Table (Core Authentication)
-- ============================================================
-- MemberID / AdminID FKs are added via ALTER TABLE at the end
-- of this script (after Member + Administrator already exist).

CREATE TABLE `User` (
    UserID          INT             AUTO_INCREMENT PRIMARY KEY,
    Username        VARCHAR(50)     NOT NULL UNIQUE,
    Email           VARCHAR(150)    NOT NULL UNIQUE,
    PasswordHash    VARCHAR(256)    NOT NULL,
    Role            ENUM('Admin', 'RegularUser') NOT NULL DEFAULT 'RegularUser',
    IsActive        BOOLEAN         NOT NULL DEFAULT TRUE,
    CreatedAt       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt       DATETIME        NULL ON UPDATE CURRENT_TIMESTAMP,
    LastLoginAt     DATETIME        NULL,

    -- Nullable links to Member / Administrator profiles
    MemberID        INT             NULL,
    AdminID         INT             NULL,

    INDEX IDX_User_Username (Username),
    INDEX IDX_User_Email    (Email),
    INDEX IDX_User_Role     (Role),
    INDEX IDX_User_MemberID (MemberID),
    INDEX IDX_User_AdminID  (AdminID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
-- 2. Session Table (JWT Token Tracking)
-- ============================================================
CREATE TABLE Session (
    SessionID   INT             AUTO_INCREMENT PRIMARY KEY,
    UserID      INT             NOT NULL,
    Token       VARCHAR(512)    NOT NULL,
    TokenJTI    VARCHAR(64)     NOT NULL UNIQUE,
    IssuedAt    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ExpiresAt   DATETIME        NOT NULL,
    IsRevoked   BOOLEAN         NOT NULL DEFAULT FALSE,
    RevokedAt   DATETIME        NULL,
    IPAddress   VARCHAR(45)     NULL,
    UserAgent   VARCHAR(512)    NULL,

    CONSTRAINT FK_Session_User FOREIGN KEY (UserID)
        REFERENCES `User`(UserID) ON DELETE CASCADE ON UPDATE CASCADE,

    INDEX IDX_Session_Token     (Token(255)),
    INDEX IDX_Session_TokenJTI  (TokenJTI),
    INDEX IDX_Session_UserID    (UserID),
    INDEX IDX_Session_ExpiresAt (ExpiresAt),
    INDEX IDX_Session_IsRevoked (IsRevoked)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
-- 3. UserGroup Table
-- ============================================================
CREATE TABLE UserGroup (
    GroupID     INT             AUTO_INCREMENT PRIMARY KEY,
    GroupName   VARCHAR(50)     NOT NULL UNIQUE,
    Description VARCHAR(256)    NULL,
    Permissions JSON            NULL,
    IsActive    BOOLEAN         NOT NULL DEFAULT TRUE,
    CreatedAt   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt   DATETIME        NULL ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
-- 4. UserGroupMapping Table
-- ============================================================
CREATE TABLE UserGroupMapping (
    MappingID   INT     AUTO_INCREMENT PRIMARY KEY,
    UserID      INT     NOT NULL,
    GroupID     INT     NOT NULL,
    AssignedAt  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    AssignedBy  INT     NULL,

    CONSTRAINT FK_UGM_User       FOREIGN KEY (UserID)      REFERENCES `User`(UserID)      ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_UGM_Group      FOREIGN KEY (GroupID)     REFERENCES UserGroup(GroupID)  ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_UGM_AssignedBy FOREIGN KEY (AssignedBy)  REFERENCES `User`(UserID)      ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT UQ_UserGroup      UNIQUE (UserID, GroupID),

    INDEX IDX_UGM_UserID  (UserID),
    INDEX IDX_UGM_GroupID (GroupID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
-- 5. AuditLog Table
-- ============================================================
CREATE TABLE AuditLog (
    LogID           INT             AUTO_INCREMENT PRIMARY KEY,
    Timestamp       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UserID          INT             NULL,
    Username        VARCHAR(50)     NULL,
    Action          VARCHAR(20)     NOT NULL,
    TableName       VARCHAR(50)     NULL,
    RecordID        INT             NULL,
    OldValues       JSON            NULL,
    NewValues       JSON            NULL,
    IPAddress       VARCHAR(45)     NULL,
    UserAgent       VARCHAR(512)    NULL,
    APIEndpoint     VARCHAR(200)    NULL,
    HTTPMethod      VARCHAR(10)     NULL,
    ResponseStatus  INT             NULL,
    ResponseTime    INT             NULL,
    IsAuthorized    BOOLEAN         NOT NULL DEFAULT TRUE,
    ErrorMessage    VARCHAR(500)    NULL,

    INDEX IDX_AuditLog_Timestamp      (Timestamp),
    INDEX IDX_AuditLog_UserID         (UserID),
    INDEX IDX_AuditLog_TableName      (TableName),
    INDEX IDX_AuditLog_Action         (Action),
    INDEX IDX_AuditLog_IsAuthorized   (IsAuthorized),
    INDEX IDX_AuditLog_User_Action    (UserID, Action),
    INDEX IDX_AuditLog_Table_Action   (TableName, Action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
-- 6. Add FK links from User → Member / Administrator
--    (safe only after 02_campus_trading.sql has been run)
-- ============================================================
ALTER TABLE `User`
    ADD CONSTRAINT FK_User_Member
        FOREIGN KEY (MemberID) REFERENCES Member(MemberID)
        ON DELETE SET NULL ON UPDATE CASCADE,
    ADD CONSTRAINT FK_User_Admin
        FOREIGN KEY (AdminID)  REFERENCES Administrator(AdminID)
        ON DELETE SET NULL ON UPDATE CASCADE;


-- ============================================================
-- 7. Default User Groups
-- ============================================================
INSERT INTO UserGroup (GroupID, GroupName, Description, Permissions) VALUES
(1, 'Administrators', 'Full system access',          '["*"]'),
(2, 'Moderators',     'Content moderation access',   '["reports:*","listings:read","listings:update","members:read"]'),
(3, 'Support',        'Customer support access',     '["reports:read","members:read","transactions:read"]'),
(4, 'Members',        'Regular campus trading members','["listings:*:own","offers:*:own","profile:*:own"]');


-- ============================================================
-- 8. Triggers — detect direct DB modifications (bypass API)
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
-- 9. Stored Procedures
-- ============================================================
DROP PROCEDURE IF EXISTS sp_CleanupExpiredSessions;
DROP PROCEDURE IF EXISTS sp_CleanupOldAuditLogs;

DELIMITER //

CREATE PROCEDURE sp_CleanupExpiredSessions()
BEGIN
    DELETE FROM Session
    WHERE ExpiresAt < NOW()
       OR (IsRevoked = TRUE AND RevokedAt < DATE_SUB(NOW(), INTERVAL 7 DAY));
END//

CREATE PROCEDURE sp_CleanupOldAuditLogs()
BEGIN
    DELETE FROM AuditLog
    WHERE Timestamp < DATE_SUB(NOW(), INTERVAL 90 DAY);
END//

DELIMITER ;
