-- ============================================================
-- FIX PASSWORDS
-- Run this against your existing CampusTrading database to
-- update all User/Member/Administrator password hashes to
-- real bcrypt values that match the credentials below.
--
-- Usage:
--   mysql -u root -p CampusTrading < sql/06_fix_passwords.sql
--
-- Credentials after running:
--   admin          / admin123     (Admin)
--   amal.perera    / password123  (RegularUser)
--   nimali.fernando/ password123  (RegularUser)
--   kavindu.silva  / password123  (RegularUser)
--   vikram.mehta   / password123  (RegularUser)
-- ============================================================

USE CampusTrading;

-- User table
UPDATE `User` SET PasswordHash = '$2b$12$G/xnxD43X/sgVFiOQ4GsCuRZFgNzoPjijmacFqMTJg0rygg0PDZZa'   WHERE Username = 'admin';
UPDATE `User` SET PasswordHash = '$2b$12$BqTRjbiiiMMd.wJW5mT.qegpnOPCl9yOCja5pDvnJXHgtDrNJ0PT6' WHERE Username IN ('amal.perera','nimali.fernando','kavindu.silva','vikram.mehta','ravindu.bandara');

-- Administrator table
UPDATE Administrator SET PasswordHash = '$2b$12$G/xnxD43X/sgVFiOQ4GsCuRZFgNzoPjijmacFqMTJg0rygg0PDZZa' WHERE Email = 'admin@iitgn.ac.in';

-- Member table (bcrypt hash stored here too for legacy reasons)
UPDATE Member SET PasswordHash = '$2b$12$BqTRjbiiiMMd.wJW5mT.qegpnOPCl9yOCja5pDvnJXHgtDrNJ0PT6' WHERE Email LIKE '%@iitgn.ac.in';

-- Confirm
SELECT UserID, Username, Role, LEFT(PasswordHash,20) AS HashStart, IsActive
FROM `User` ORDER BY UserID;

SELECT 'Done! All passwords updated.' AS Status;
