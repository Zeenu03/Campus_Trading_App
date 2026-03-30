# Assignment 3 - Module A Plan

This document is a practical implementation plan for **Assignment 3 / Module A** using the existing Assignment 2 Python engine:
- `database/bplustree.py`
- `database/table.py`
- `database/db_manager.py`

Goal: add transaction management, concurrency control, and crash recovery with ACID validation while keeping B+ Tree as the only storage path.

---

## 1. Current Baseline (What You Already Have)

From Assignment 2 Module A:
- Each table is backed by one B+ Tree (`Table.data = BPlusTree(...)`).
- CRUD operations exist (`insert`, `get`, `update`, `delete`, `range_query`).
- `DatabaseManager` can create databases/tables and fetch table handles.
- Data is in-memory only right now (no transaction log, no restart recovery).

From Assignment 1 schema:
- You have many real relations (Member, Listing, Offer, Transaction, etc.).
- Module A requires at least 3 relations participating in one transaction.

---

## 2. Required Module A Outcome

You must demonstrate:
- `BEGIN`, `COMMIT`, `ROLLBACK` transaction lifecycle.
- Multi-relation atomic transaction (minimum 3 tables in one unit of work).
- Isolation under concurrent transactions (basic locking or serialized execution is enough).
- Durability and crash recovery (undo incomplete transactions, preserve committed ones).
- Consistency checks after every transaction.

Important interpretation for this project:
- B+ Tree is your table storage and index.
- Do not keep an alternative primary copy of table data.
- Any logs/snapshots are recovery metadata, not a second user-facing database.

---

## 3. Architecture to Add (Minimal and Defensible)

Add these components under `Assignment_2/Module_A/database/`:

1. `transaction.py`
- `TransactionManager`
- Transaction states: `ACTIVE`, `COMMITTED`, `ABORTED`
- Public API:
  - `begin() -> tx_id`
  - `commit(tx_id)`
  - `rollback(tx_id)`
  - wrappers for `insert/update/delete/get` that include `tx_id`

2. `lock_manager.py`
- Start with table-level or key-level exclusive locks.
- Keep it simple: strict 2PL for write operations.
- Provide timeout/deadlock prevention by deterministic lock ordering.

3. `wal.py`
- Write-ahead logging to JSONL file (append-only).
- Log records:
  - `BEGIN`
  - `UPDATE` / `INSERT` / `DELETE` (with before-image and after-image)
  - `COMMIT`
  - optional `ROLLBACK`, `CHECKPOINT`

4. `recovery.py`
- On startup, scan WAL.
- REDO committed transactions.
- UNDO uncommitted transactions (using before-images).

5. `storage.py` (optional helper)
- Persist and load each table B+ Tree content to disk (e.g., JSON snapshots).
- Needed to prove restart durability in a straightforward way.

Recommendation for implementation size:
- Start with serialized transaction execution (global mutex).
- Then move to per-table/per-key locks if needed for stronger isolation demo.

---

## 4. Data Model for Module A Demo (Schema-Accurate Relations)

Use the exact Assignment 1 schema table names and keys. For ACID demonstration, use at least these three core relations:

1. `Offer`
- key: `OfferID`
- fields used in tx: `OfferID`, `ListingID`, `BuyerID`, `OfferedPrice`, `AgreedPrice`, `OfferStatus`, `SubmittedDate`, `ResponseDate`

2. `Listing`
- key: `ListingID`
- fields used in tx: `ListingID`, `SellerID`, `AskingPrice`, `Status`, `LastModifiedDate`

3. `Transaction`
- key: `TransactionID`
- fields used in tx: `TransactionID`, `ListingID`, `SellerID`, `BuyerID`, `OfferID`, `AgreedPrice`, `Status`, `CreatedDate`

Optional but recommended 4th relation for stronger realism:

4. `Notification`
- key: `NotificationID`
- fields used in tx: `RecipientID`, `NotificationType`, `Message`, `RelatedOfferID`, `RelatedTransactionID`, `CreatedDate`

`Member` remains important for foreign-key and business-rule validation (`BuyerID`, `SellerID` existence), even if not updated directly in the core transaction.

---

## 5. Transaction Flow (Canonical Operation)

### Use case: accept offer and create transaction
One transaction performs:
1. Update `Offer` row: set `OfferStatus='Accepted'`, set `AgreedPrice`, set `ResponseDate`.
2. Update `Listing` row: set `Status='Sold'`, set `LastModifiedDate`.
3. Insert `Transaction` row with `ListingID`, `SellerID`, `BuyerID`, `OfferID`, `AgreedPrice`.
4. (Optional) Insert notification rows for buyer and seller in `Notification`.

If any step fails, rollback all steps.

### Consistency checks in transaction
- offer exists and is in `OfferStatus='Submitted'`.
- listing exists and `Offer.ListingID == Listing.ListingID`.
- listing status allows acceptance (for example `Listed`/`Pending` only).
- seller performing accept matches `Listing.SellerID`.
- buyer and seller exist in `Member` and satisfy `BuyerID <> SellerID`.
- accepted price is valid (`AgreedPrice > 0`) and consistent with your app rule.
- prevent double-accept race: only one accepted offer/active transaction path per listing.

## 5.1 Module B-aligned Concrete Behavior (Use This as Ground Truth)

Your Module B backend already implements a rich transactional flow that Module A should mirror semantically:

1. Accept-offer flow (from `handlers/offers.go`)
- Accept chosen offer (`OfferStatus='Accepted'`, set `AgreedPrice`, `ResponseDate`).
- Auto-decline all other submitted offers on same listing (`OfferStatus='Declined'` with reason).
- Mark listing as `Sold` and set `LastModifiedDate`.
- Clear watchlist rows for that listing.
- Insert one `Transaction` row for accepted offer.
- Insert additional `Transaction` rows for auto-declined offers (audit trail style used by your app).
- Insert notifications for winner, losing buyers, and seller.

2. Decline-offer flow
- Set offer to `Declined` with reason and `ResponseDate`.
- Insert `Transaction` row linked to that offer.
- Insert decline notification.

3. Withdraw-offer flow (buyer side)
- Set offer to `Withdrawn` with reason and `ResponseDate`.
- Insert `Transaction` row linked to that offer.
- Notify seller.

4. Withdraw-listing flow (seller side, from `handlers/listings.go`)
- Set listing to `Withdrawn`.
- Set all submitted offers on that listing to `Withdrawn`.
- Create transaction entries for affected offers.
- Notify affected buyers.

For Assignment 3 Module A, use a reduced subset of these operations first (Accept-offer path), then optionally add Decline/Withdraw as extra validation scenarios.

---

## 6. Logging and Recovery Design

## 6.1 WAL format (JSONL)
Each line one JSON object, example:

```json
{"lsn":1,"tx_id":"T1","type":"BEGIN","ts":"..."}
{"lsn":2,"tx_id":"T1","type":"UPDATE","table":"Offer","key":15,"before":{"OfferStatus":"Submitted","AgreedPrice":null},"after":{"OfferStatus":"Accepted","AgreedPrice":12.0}}
{"lsn":3,"tx_id":"T1","type":"UPDATE","table":"Listing","key":11,"before":{"Status":"Listed"},"after":{"Status":"Reserved"}}
{"lsn":4,"tx_id":"T1","type":"INSERT","table":"Transaction","key":101,"before":null,"after":{"ListingID":11,"SellerID":15,"BuyerID":5,"OfferID":15,"AgreedPrice":12.0,"Status":"Scheduled"}}
{"lsn":5,"tx_id":"T1","type":"INSERT","table":"Notification","key":8801,"before":null,"after":{"RecipientID":5,"NotificationType":"OfferAccepted","RelatedOfferID":15,"RelatedTransactionID":101}}
{"lsn":6,"tx_id":"T1","type":"COMMIT","ts":"..."}
```

Rules:
- WAL append must happen before applying in-memory change.
- Flush WAL on `COMMIT`.

## 6.2 Recovery algorithm (startup)
1. Read WAL sequentially.
2. Build sets:
- committed transactions
- active/uncommitted transactions
3. REDO phase:
- replay all actions for committed txns (idempotent replay logic).
4. UNDO phase:
- reverse actions of uncommitted txns in reverse LSN order.
5. Optional: write `CHECKPOINT` + truncate old WAL after snapshot.

---

## 7. Isolation Strategy

Implement one of these (both acceptable):

Option A (fastest to finish)
- Serialized transaction execution with one global lock.
- Guarantees isolation, simplest correctness proof.

Option B (better concurrency)
- Strict 2PL:
  - Acquire X lock on each `(table, key)` for write.
  - Hold locks until commit/rollback.
  - Acquire locks in deterministic sorted order to reduce deadlocks.

For Assignment 3 grading, Option A is usually enough if clearly justified and tested.

---

## 8. Implementation Plan by Phases

## Phase 0 - Branch and scaffold
- Create files: `transaction.py`, `lock_manager.py`, `wal.py`, `recovery.py`.
- Add exports in `database/__init__.py`.

## Phase 1 - Transaction manager (without recovery)
- Add tx lifecycle states.
- Add undo log in-memory (before-images).
- `rollback` reverts applied changes.
- Add `with transaction` helper or explicit API.

## Phase 2 - Multi-table atomic operation
- Implement `accept_offer(tx_id, offer_id, seller_id, agreed_price, transaction_id)` service.
- Enforce all consistency checks.
- Add failure injection switch after each step.
- Mirror Module B side effects in deterministic order:
  - update accepted offer
  - collect and decline competing submitted offers
  - update listing status
  - write transaction row(s)
  - write notification row(s)

## Phase 3 - WAL persistence + durability
- Implement append-only WAL file in `data/wal.log`.
- Log BEGIN/data-change/COMMIT.
- Flush commit records.

## Phase 4 - Crash recovery
- Implement startup `recover()` that replays WAL.
- Add tests for crash-before-commit and crash-after-commit.

## Phase 5 - Concurrency validation
- Add threaded test script for concurrent acceptance/competing updates on the same listing/offer set.
- Verify no more than one accepted offer path per listing and no conflicting `Transaction` rows for the same listing lifecycle.

## Phase 6 - Report artifacts
- Collect logs, output tables, and pass/fail matrix.
- Add screenshots/snippets for report/video.

---

## 9. Test Matrix for ACID Validation

Create a test script and record outputs for each case.

1. Atomicity
- Start tx touching all 3 tables.
- Inject failure after step 2.
- Expect all changes rolled back.
- Include side-effect rollback check: no partial auto-declines, no orphan notifications, no partial transaction rows.

2. Consistency
- Try invalid accept cases (wrong seller, non-submitted offer, listing already completed/sold).
- Expect transaction abort with no state change.
- Verify constraints still true.

3. Isolation
- Run N threads trying to accept competing offers on the same listing.
- Expect one success path, others rollback/fail cleanly.
- Verify final state invariants:
  - exactly one accepted offer for target listing
  - listing state transitions once (for example to `Sold`)
  - no duplicate winner transaction for same accepted offer

4. Durability
- Commit transaction.
- Simulate restart.
- Recover from WAL.
- Verify committed row/state still present.

5. Recovery correctness
- Crash after BEGIN and one UPDATE but before COMMIT.
- After restart, update must be undone.
- Also test crash after accepted-offer update but before listing/transaction updates to ensure no split-brain state.

---

## 10. Suggested File Layout After Module A Work

```text
Assignment_2/Module_A/
  database/
    transaction.py
    lock_manager.py
    wal.py
    recovery.py
    db_manager.py          (integrate tx manager)
    table.py               (tx-aware CRUD hooks)
    bplustree.py           (minimal/no major redesign)
  tests/
    test_transactions.py
    test_recovery.py
    test_concurrency.py
  data/
    wal.log
    snapshots/
```

---

## 11. Execution Plan (Day-wise)

Day 1
- Phase 0 + Phase 1 complete.
- Local rollback test passing.

Day 2
- Phase 2 + Phase 3 complete.
- Multi-table transaction + WAL commit path passing.

Day 3
- Phase 4 complete.
- Crash/restart demo passing.

Day 4
- Phase 5 complete.
- Concurrency stress test and observations captured.

Day 5
- Report and video preparation with evidence.

---

## 12. What to Show in Demo/Report

Minimum demo script sequence:
1. Initialize 3 tables with seed data.
2. Run successful multi-table transaction.
3. Run failure-injected transaction and show full rollback.
4. Run concurrent transaction test on same listing.
5. Simulate crash and restart; run recovery; show final state.

Report evidence to include:
- Transaction logs (WAL snippets).
- Before/after table snapshots.
- Concurrency test stats (success/failure counts, correctness assertions).
- Limitations and future improvements.

---

## 13. Risks and Mitigations

1. Risk: lock complexity and deadlocks.
- Mitigation: start with global serialization lock.

2. Risk: non-idempotent recovery replays.
- Mitigation: design replay logic to check current key state before apply.

3. Risk: schema mismatch in before/after images.
- Mitigation: always log full record image for update/delete/insert.

4. Risk: too much redesign near deadline.
- Mitigation: wrap existing Table/B+Tree instead of rewriting internals.

---

## 14. Definition of Done for Module A

Module A is done only if all are true:
- BEGIN/COMMIT/ROLLBACK implemented and used in code.
- At least one transaction updates 3 relations atomically.
- Failure injection demonstrates clean rollback.
- Concurrent test shows no corruption.
- Crash + restart recovery works (committed kept, incomplete undone).
- Reproducible scripts and logs exist for report/video.

---

## 15. Immediate Next Coding Task

Start implementation in this order:
1. `wal.py`
2. `transaction.py`
3. Integrate tx-aware CRUD wrappers in `db_manager.py`
4. Add one end-to-end script: `tests/test_transactions.py`

This order gives early evidence for Atomicity and Durability with minimal refactor risk.
