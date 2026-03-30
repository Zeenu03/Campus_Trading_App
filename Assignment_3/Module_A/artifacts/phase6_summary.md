# Assignment 3 Module A - Phase 6 Artifacts

Generated at (UTC): 2026-03-29T13:30:11.012823+00:00

## Test Suite
- Command: `D:\Courses\Databases\Project\.venv\Scripts\python.exe -m unittest tests/test_phase1_transactions.py tests/test_phase2_accept_offer.py tests/test_phase3_wal_recovery.py tests/test_phase4_recovery_replay.py tests/test_phase5_concurrency.py`
- Exit code: `0`
- Passed: `True`

## Scenario Results

### Atomic Success
- Result: `True`
- Message: Offer '501' accepted atomically
- Invariants: `{'one_accepted_offer': True, 'one_declined_offer': True, 'listing_sold': True, 'transaction_rows': 2, 'notification_rows': 3}`

### Atomic Failure Rollback
- Result: `False`
- Message: Injected failure after step 3
- Invariants: `{'all_offers_reverted_to_submitted': True, 'listing_reverted_to_listed': True, 'no_transactions_written': True, 'no_notifications_written': True}`

### Recovery Undo (Crash Before Commit)
- Recovery summary: `{'status': 'ok', 'total_records': 6, 'redo_transactions': [], 'undo_transactions': ['T-2c60fe2f83ec', 'T-31b515102e45', 'T-4e5db239e8b5'], 'rolled_back_transactions': [], 'applied_redo': 0, 'applied_undo': 3, 'note': 'REDO/UNDO replay applied.'}`
- Invariants: `{'undo_applied': True, 'uncommitted_row_removed': True}`

### Recovery Redo (Crash After Commit)
- Recovery summary: `{'status': 'ok', 'total_records': 9, 'redo_transactions': ['T-ae3b20918c1b', 'T-dc69670d079d', 'T-dda0b6618167'], 'undo_transactions': [], 'rolled_back_transactions': [], 'applied_redo': 3, 'applied_undo': 0, 'note': 'REDO/UNDO replay applied.'}`
- Invariants: `{'redo_applied': True, 'committed_row_restored': True}`

## Files
- `artifacts/phase6_summary.json`
- `artifacts/unittest_output.txt`