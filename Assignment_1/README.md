# Assignment 1 — Campus Trading Database

Database design and implementation for the Campus Trading application (MySQL).

## Files

| File | Purpose |
|------|---------|
| **CampusTrading.sql** | Single script: DROP → CREATE (14 tables) → INSERT sample data. Run this to build the database. |
| **Project.md** | Design document: table descriptions, attributes, constraints, and relationships. |
| **UML_Diagrams_Mermaid.md** | UML class and state-machine diagrams.|
| **ER_Diagrams_Mermaid.md** | Complete marketplace ER diagram and functionality-specific ER module breakdowns. |
| **Project.txt** / **Idea.txt** | Project idea and notes. |


## How to run

**Prerequisites:** MySQL 8.0.16+ (for `CHECK` constraints).

```bash
mysql -u your_user -p your_database < CampusTrading.sql
```

Or open `CampusTrading.sql` in MySQL Workbench / another client and execute the full script.

## Schema at a glance

- **14 tables:** Member, Administrator, Category, WishRequest, Listing, ListingImage, Offer, Transaction, Rating, Watchlist, Report, Notification, MessageThread, Message.
- **Features:** Listings & categories, offers & transactions, ratings, wish requests, watchlist, messaging threads, reports, notifications.
- **Integrity:** Primary keys on all tables, foreign keys with appropriate `ON UPDATE`/`ON DELETE`, `CHECK` and `UNIQUE` constraints; sample data (10–20 rows per table) included.

For full details, see **Project.md** and **UML_Diagrams_Mermaid.md**.
