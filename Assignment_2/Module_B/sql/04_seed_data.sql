-- ============================================================
-- Campus Trading Application - Seed Data
-- Module B: Sample data for testing and demonstration
-- ============================================================

USE CampusTrading;

-- ============================================================
-- Members
-- ============================================================
INSERT IGNORE INTO Member
  (MemberID, Name, Email, PasswordHash, ContactNumber, Department, YearOfStudy, Hostel, RoomNumber, Bio, IsVerified, AccountStatus)
VALUES
  (1,  'Amal Perera',    'amal.perera@iitgn.ac.in',     '$2b$12$BqTRjbiiiMMd.wJW5mT.qegpnOPCl9yOCja5pDvnJXHgtDrNJ0PT6', '9876543210', 'Computer Science',   3, 'Hostel A', 'A-101', 'CS student, selling old textbooks', TRUE,  'Active'),
  (2,  'Nimali Fernando','nimali.fernando@iitgn.ac.in',  '$2b$12$BqTRjbiiiMMd.wJW5mT.qegpnOPCl9yOCja5pDvnJXHgtDrNJ0PT6', '9876543211', 'Electrical Engg',    2, 'Hostel B', 'B-204', 'Looking for circuit analysis books', FALSE, 'Active'),
  (3,  'Kavindu Silva',  'kavindu.silva@iitgn.ac.in',    '$2b$12$BqTRjbiiiMMd.wJW5mT.qegpnOPCl9yOCja5pDvnJXHgtDrNJ0PT6', '9876543212', 'Mechanical Engg',    4, 'Hostel A', 'A-305', 'Final year, selling everything!',  TRUE,  'Active'),
  (4,  'Priya Nair',     'priya.nair@iitgn.ac.in',       '$2b$12$BqTRjbiiiMMd.wJW5mT.qegpnOPCl9yOCja5pDvnJXHgtDrNJ0PT6', '9876543213', 'Mathematics',        1, 'Hostel C', 'C-108', 'First year, need study materials',  FALSE, 'Active'),
  (5,  'Ravindu Bandara','ravindu.bandara@iitgn.ac.in',  '$2b$12$BqTRjbiiiMMd.wJW5mT.qegpnOPCl9yOCja5pDvnJXHgtDrNJ0PT6', '9876543214', 'Physics',            3, 'Hostel B', 'B-110', 'Physics tutor, selling lab equipment', TRUE, 'Active'),
  (6,  'Anjali Sharma',  'anjali.sharma@iitgn.ac.in',    '$2b$12$BqTRjbiiiMMd.wJW5mT.qegpnOPCl9yOCja5pDvnJXHgtDrNJ0PT6', '9876543215', 'Chemistry',          2, 'Hostel C', 'C-212', 'Chem enthusiast',                   FALSE, 'Active'),
  (7,  'Vikram Mehta',   'vikram.mehta@iitgn.ac.in',     '$2b$12$BqTRjbiiiMMd.wJW5mT.qegpnOPCl9yOCja5pDvnJXHgtDrNJ0PT6', '9876543216', 'Computer Science',   4, 'Hostel A', 'A-410', 'Graduating, selling everything',    TRUE,  'Active'),
  (8,  'Sana Ahmed',     'sana.ahmed@iitgn.ac.in',       '$2b$12$BqTRjbiiiMMd.wJW5mT.qegpnOPCl9yOCja5pDvnJXHgtDrNJ0PT6', '9876543217', 'Biotechnology',      2, 'Hostel D', 'D-105', 'Bio student',                       FALSE, 'Active');

-- ============================================================
-- Administrator
-- ============================================================
INSERT IGNORE INTO Administrator (AdminID, Name, Email, PasswordHash, Role, IsActive)
VALUES (1, 'System Admin', 'admin@iitgn.ac.in', '$2b$12$G/xnxD43X/sgVFiOQ4GsCuRZFgNzoPjijmacFqMTJg0rygg0PDZZa', 'SuperAdmin', TRUE);

-- ============================================================
-- Categories
-- ============================================================
INSERT IGNORE INTO Category (CategoryID, CategoryName, ParentCategoryID, Description, IsActive)
VALUES
  (1,  'Books & Notes',      NULL, 'Textbooks, notebooks, study materials', TRUE),
  (2,  'Textbooks',          1,    'Course textbooks',                       TRUE),
  (3,  'Notes & Guides',     1,    'Handwritten notes and study guides',     TRUE),
  (4,  'Electronics',        NULL, 'Gadgets, components, devices',          TRUE),
  (5,  'Calculators',        4,    'Scientific and graphing calculators',    TRUE),
  (6,  'Laptops & Tablets',  4,    'Portable computing devices',             TRUE),
  (7,  'Lab Equipment',      4,    'Lab instruments and tools',              TRUE),
  (8,  'Stationery',         NULL, 'Pens, rulers, drawing tools',           TRUE),
  (9,  'Clothing',           NULL, 'Clothes, uniforms, sportswear',         TRUE),
  (10, 'Sports & Fitness',   NULL, 'Sports equipment and gear',             TRUE),
  (11, 'Furniture',          NULL, 'Desks, chairs, shelves',                TRUE),
  (12, 'Misc / Other',       NULL, 'Anything else',                         TRUE);

-- ============================================================
-- Listings  (mix of statuses for testing)
-- ============================================================
INSERT IGNORE INTO Listing
  (ListingID, SellerID, CategoryID, Title, Description, AskingPrice, IsNegotiable, `Condition`, CourseCode, Status, IsDonation, PreferredMeetingLocation)
VALUES
  (1,  1, 2, 'Calculus – Stewart 8th Ed',         'Very good condition. Used one semester only.', 450.00, TRUE,  'Good',     'MA101', 'Listed',  FALSE, 'Library'),
  (2,  1, 2, 'Data Structures – Cormen (CLRS)',   'Highlights on some pages.',                    600.00, TRUE,  'Good',     'CS201', 'Listed',  FALSE, 'CSE Dept'),
  (3,  3, 5, 'Casio FX-991EX Calculator',         'Works perfectly, bought 2022.',                500.00, FALSE, 'Like New', NULL,    'Listed',  FALSE, 'Hostel A Gate'),
  (4,  7, 6, 'Lenovo ThinkPad (i5, 8GB)',         'Used for 2 years. Battery life 4 hrs.',      18000.00, TRUE,  'Good',     NULL,    'Listed',  FALSE, 'Main Gate'),
  (5,  5, 7, 'Digital Multimeter VC830L',          'Accurate, 2 years old.',                       800.00, TRUE,  'Good',     NULL,    'Listed',  FALSE, 'Physics Lab'),
  (6,  2, 3, 'Circuit Analysis Notes – Year 2',   'Handwritten, very neat.',                      150.00, FALSE, 'Like New', 'EE201', 'Listed',  FALSE, 'EE Dept'),
  (7,  6, 2, 'Atkins Physical Chemistry 10th Ed', 'Good condition, few annotations.',              700.00, TRUE,  'Good',     'CH101', 'Listed',  FALSE, 'Library'),
  (8,  1, 2, 'Linear Algebra – Gilbert Strang',   'Perfect condition, never used.',               350.00, TRUE,  'New',      'MA201', 'Listed',  FALSE, 'Library'),
  (9,  3, 9, 'IITGN Sports T-Shirt (XL)',         'Worn once.',                                    80.00, FALSE, 'Like New', NULL,    'Listed',  FALSE, 'Hostel A Gate'),
  (10, 4, 2, 'Introduction to Algorithms',         'Donating – no longer needed.',                   0.00, FALSE, 'Fair',     'CS201', 'Listed',  TRUE,  'Library'),
  (11, 7, 6, 'Dell XPS 13 (i7, 16GB)',            'Great laptop, minor scratch.',                32000.00, TRUE,  'Good',     NULL,    'Sold',    FALSE, 'Main Gate'),
  (12, 5, 7, 'Oscilloscope DS1054Z',              'Fully functional.',                           12000.00, TRUE,  'Good',     NULL,    'Pending', FALSE, 'Physics Lab'),
  (13, 3, 11,'IKEA Study Table',                   'Disassembly required.',                       2500.00, TRUE,  'Good',     NULL,    'Listed',  FALSE, 'Hostel A'),
  (14, 8, 2, 'Molecular Biology – Lewin 9th Ed',  'Excellent condition.',                         550.00, TRUE,  'Like New', 'BT301', 'Listed',  FALSE, 'Bio Lab');

-- ============================================================
-- Offers
-- ============================================================
INSERT IGNORE INTO Offer
  (OfferID, ListingID, BuyerID, OfferedPrice, AgreedPrice, OfferMessage, OfferStatus, ExpiryDate)
VALUES
  (1, 1, 2, 400.00, NULL,   'Would you take 400?',      'Submitted', DATE_ADD(NOW(), INTERVAL 3 DAY)),
  (2, 1, 4, 420.00, NULL,   'Best I can do is 420.',    'Submitted', DATE_ADD(NOW(), INTERVAL 3 DAY)),
  (3, 3, 1, 450.00, NULL,   'Is 450 okay?',             'Submitted', DATE_ADD(NOW(), INTERVAL 2 DAY)),
  (4, 4, 5, 16000.00, NULL, 'Negotiable further?',      'Submitted', DATE_ADD(NOW(), INTERVAL 5 DAY)),
  (5, 12,1, 10000.00, 10000.00, 'Deal!',                'Accepted',  DATE_ADD(NOW(), INTERVAL 7 DAY)),
  (6, 11,2, 30000.00, 30000.00, 'Accepted offer',       'Accepted',  DATE_ADD(NOW(), INTERVAL 7 DAY));

-- ============================================================
-- Transactions
-- ============================================================
INSERT IGNORE INTO `Transaction`
  (TransactionID, ListingID, SellerID, BuyerID, OfferID, AgreedPrice, TransactionDate, SellerConfirmed, BuyerConfirmed, Status)
VALUES
  (1, 11, 7, 2, 6, 30000.00, DATE_SUB(NOW(), INTERVAL 5 DAY),  TRUE, TRUE,  'Completed'),
  (2, 12, 5, 1, 5, 10000.00, DATE_ADD(NOW(), INTERVAL 2 DAY),  FALSE, FALSE, 'Scheduled');

-- ============================================================
-- Ratings
-- ============================================================
INSERT IGNORE INTO Rating (RatingID, TransactionID, RaterID, RatedID, Stars, ReviewText)
VALUES
  (1, 1, 2, 7, 5, 'Great seller! Laptop exactly as described. Very smooth transaction.'),
  (2, 1, 7, 2, 4, 'Good buyer, punctual and paid promptly.');

-- ============================================================
-- Notifications
-- ============================================================
INSERT IGNORE INTO Notification
  (NotificationID, RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID, IsRead)
VALUES
  (1, 1, 'OfferReceived',      'New Offer on Calculus',     'You received an offer of ₹400 on your Calculus textbook.',  1, 1, FALSE),
  (2, 1, 'OfferReceived',      'New Offer on Calculus',     'You received an offer of ₹420 on your Calculus textbook.',  1, 2, FALSE),
  (3, 5, 'TransactionCompleted','Sale Complete!',           'Your transaction for the Oscilloscope has been scheduled.', 12, 5, TRUE),
  (4, 2, 'TransactionCompleted','Purchase Confirmed',       'Your purchase of Dell XPS 13 is complete!',                 11, 6, FALSE);

-- ============================================================
-- Summary
-- ============================================================
-- Members:      8 (various departments)
-- Admins:       1
-- Categories:   12 (nested hierarchy)
-- Listings:     14 (mix of Listed, Sold, Pending)
-- Offers:       6  (mix of Submitted, Accepted)
-- Transactions: 2  (1 Completed, 1 Scheduled)
-- Ratings:      2
-- Notifications:4
