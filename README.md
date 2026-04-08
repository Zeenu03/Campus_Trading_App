# Campus Trading App

A database-backed campus marketplace for students to buy, sell, and trade items (e.g. books, electronics, furniture) within the campus community.

## Contents

| Folder | Description |
|--------|-------------|
| **[Assignment_1](./Assignment_1/)** | Database design and implementation: schema, sample data, UML diagrams, and documentation. |
| **[Assignment_2](./Assignment_2/)** | Full-stack application: Go backend with MySQL, React frontend, admin audit log, and member seeding and B+ Tree implementation for efficient product search. |
| **[Assignment_3](./Assignment_3/)** | Transaction management and ACID validation: custom transaction engine with WAL recovery (Module A) and concurrency stress experiments (Module B). |
| **[Assignment_4](./Assignment_4/)** | Sharding implementation: modulo-based shard routing, shard migration and verification scripts, and shard-aware backend/frontend deliverables. |

## Quick start

1. Start with **[Assignment_1](./Assignment_1/)** and run **[CampusTrading.sql](./Assignment_1/CampusTrading.sql)** in MySQL 8.0+ to create and seed the schema.
2. Open **[Assignment_2/Module_A/README.md](./Assignment_2/Module_A/README.md)** and **[Assignment_2/Module_B/Readme.md](./Assignment_2/Module_B/Readme.md)** for backend/frontend and Module A instructions.
3. Open **[Assignment_3/README.md](./Assignment_3/README.md)**, then follow **[Assignment_3/Module_A/README.md](./Assignment_3/Module_A/README.md)** and **[Assignment_3/Module_B/MODULE_B_REPORT.md](./Assignment_3/Module_B/MODULE_B_REPORT.md)** for ACID and stress-validation workflows.
4. Open **[Assignment_4/README.md](./Assignment_4/README.md)**, then follow the shard creation, migration, and verification steps for the sharding deliverable.
5. Run components in each assignment using the module-specific steps in their linked documentation.

## Assignment quick links

### Assignment 1

- SQL schema and data: **[Assignment_1/CampusTrading.sql](./Assignment_1/CampusTrading.sql)**
- Assignment 1 report: **[Assignment_1/Report_Team_8.pdf](./Assignment_1/Report_Team_8.pdf)**
- Assignment 1 submission PDF: **[Assignment_1/CS432_Track1_Assignment1.pdf](./Assignment_1/CS432_Track1_Assignment1.pdf)**

### Assignment 2

- Module A guide: **[Assignment_2/Module_A/README.md](./Assignment_2/Module_A/README.md)**
- Module B guide: **[Assignment_2/Module_B/Readme.md](./Assignment_2/Module_B/Readme.md)**
- Assignment 2 submission PDF: **[Assignment_2/Track1_Assignment2.pdf](./Assignment_2/Track1_Assignment2.pdf)**

### Assignment 3

- Overview: **[Assignment_3/README.md](./Assignment_3/README.md)**
- Module A guide: **[Assignment_3/Module_A/README.md](./Assignment_3/Module_A/README.md)**
- Module A report: **[Assignment_3/Module_A/MODULE_A_REPORT.md](./Assignment_3/Module_A/MODULE_A_REPORT.md)**
- Module B report: **[Assignment_3/Module_B/MODULE_B_REPORT.md](./Assignment_3/Module_B/MODULE_B_REPORT.md)**
- Module B (B+ Tree experiments): **[Assignment_3/Module_B/B+tree/README.md](./Assignment_3/Module_B/B+tree/README.md)**
- Module B (MySQL experiments): **[Assignment_3/Module_B/MySQL/RESULTS_GUIDE.md](./Assignment_3/Module_B/MySQL/RESULTS_GUIDE.md)**

### Assignment 4

- Overview: **[Assignment_4/README.md](./Assignment_4/README.md)**
- Sharding report: **[Assignment_4/Report.pdf](./Assignment_4/Report.md)**
- Shard DDL: **[Assignment_4/sql/create_shards.sql](./Assignment_4/sql/create_shards.sql)**
- Shard router: **[Assignment_4/implementation/shard_router.py](./Assignment_4/implementation/shard_router.py)**
- Migration script: **[Assignment_4/scripts/migrate_shards.py](./Assignment_4/scripts/migrate_shards.py)**
- Verification script: **[Assignment_4/scripts/verify_shards.py](./Assignment_4/scripts/verify_shards.py)**
- Backend app: **[Assignment_4/backend](./Assignment_4/backend/)**
- Frontend app: **[Assignment_4/frontend](./Assignment_4/frontend/)**

## Tech

- **DBMS:** MySQL 8.0+ (InnoDB, utf8mb4)
- **Backend:** Go (Assignment 2)
- **Frontend:** React (Assignment 2)
- **Transaction Engine & Stress Testing:** Python (Assignment 3)
- **Sharding:** MySQL, Python, and Go (Assignment 4)
- **Deliverables:** SQL DDL/DML, UML (Mermaid), design doc, full-stack web app, ACID/WAL validation report, stress-test evidence, shard migration/verification, and shard-aware backend/frontend

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
