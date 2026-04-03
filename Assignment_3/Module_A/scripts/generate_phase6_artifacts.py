"""Generate Phase 6 report artifacts for Assignment 3 Module A.

This script runs:
1) Full unittest suite for phases 1-5.
2) Deterministic ACID demo scenarios (multi-table commit/rollback, recovery undo/redo).
3) Explicit manual API: BEGIN → tx_insert → COMMIT, and BEGIN → tx_insert → ROLLBACK.

Outputs are written to Module_A/artifacts:
- phase6_summary.json
- phase6_summary.md
- unittest_output.txt
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import DatabaseManager, RecoveryManager  # noqa: E402
from database.campus_workflow import accept_offer_atomic  # noqa: E402

TEST_MODULES = [
    "tests/test_phase1_transactions.py",
    "tests/test_phase2_accept_offer.py",
    "tests/test_phase3_wal_recovery.py",
    "tests/test_phase4_recovery_replay.py",
    "tests/test_phase5_concurrency.py",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fresh_wal(wal_path: Path) -> None:
    """Remove stale WAL so each demo run produces a clean, readable log."""
    if wal_path.exists():
        wal_path.unlink()


def _create_core_tables(dbm: DatabaseManager) -> None:
    ok, msg = dbm.create_database("campus")
    if not ok and "already exists" not in msg:
        raise RuntimeError(msg)

    offer_schema = {
        "OfferID": int,
        "ListingID": int,
        "BuyerID": int,
        "OfferedPrice": float,
        "AgreedPrice": float,
        "OfferStatus": str,
        "Reason": str,
        "ResponseDate": str,
    }
    listing_schema = {
        "ListingID": int,
        "SellerID": int,
        "Status": str,
        "LastModifiedDate": str,
    }
    transaction_schema = {
        "TransactionID": int,
        "ListingID": int,
        "SellerID": int,
        "BuyerID": int,
        "OfferID": int,
        "AgreedPrice": float,
        "Status": str,
        "CreatedDate": str,
    }
    notification_schema = {
        "NotificationID": int,
        "RecipientID": int,
        "NotificationType": str,
        "Title": str,
        "Message": str,
        "RelatedListingID": int,
        "RelatedOfferID": int,
        "RelatedTransactionID": int,
        "CreatedDate": str,
    }

    specs = [
        ("Offer", offer_schema, "OfferID"),
        ("Listing", listing_schema, "ListingID"),
        ("Transaction", transaction_schema, "TransactionID"),
        ("Notification", notification_schema, "NotificationID"),
    ]

    for table_name, schema, key in specs:
        ok, msg = dbm.create_table("campus", table_name, schema, search_key=key)
        if not ok and "already exists" not in msg:
            raise RuntimeError(msg)


def _seed_listing_and_offers(dbm: DatabaseManager) -> None:
    listing_table, _ = dbm.get_table("campus", "Listing")
    offer_table, _ = dbm.get_table("campus", "Offer")

    ok, msg = listing_table.insert(
        {
            "ListingID": 1000,
            "SellerID": 9001,
            "Status": "Listed",
            "LastModifiedDate": "",
        }
    )
    if not ok:
        raise RuntimeError(msg)

    offers = [
        {
            "OfferID": 501,
            "ListingID": 1000,
            "BuyerID": 7001,
            "OfferedPrice": 210.0,
            "AgreedPrice": 0.0,
            "OfferStatus": "Submitted",
            "Reason": "",
            "ResponseDate": "",
        },
        {
            "OfferID": 502,
            "ListingID": 1000,
            "BuyerID": 7002,
            "OfferedPrice": 205.0,
            "AgreedPrice": 0.0,
            "OfferStatus": "Submitted",
            "Reason": "",
            "ResponseDate": "",
        },
    ]

    for row in offers:
        ok, msg = offer_table.insert(row)
        if not ok:
            raise RuntimeError(msg)


def _run_unittest_suite() -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "unittest", *TEST_MODULES]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
    }


def _scenario_atomic_success(base_dir: Path) -> Dict[str, Any]:
    wal_path = base_dir / "atomic_success_wal.log"
    _fresh_wal(wal_path)
    dbm = DatabaseManager(wal_path=str(wal_path))
    _create_core_tables(dbm)
    _seed_listing_and_offers(dbm)

    ok, msg = accept_offer_atomic(
        dbm,
        db_name="campus",
        offer_id=501,
        acting_seller_id=9001,
        include_notifications=True,
        create_declined_transactions=True,
    )

    offer_table, _ = dbm.get_table("campus", "Offer")
    listing_table, _ = dbm.get_table("campus", "Listing")
    transaction_table, _ = dbm.get_table("campus", "Transaction")
    notification_table, _ = dbm.get_table("campus", "Notification")

    offer_rows = [row for _, row in offer_table.get_all()]
    accepted = sum(1 for r in offer_rows if r["OfferStatus"] == "Accepted")
    declined = sum(1 for r in offer_rows if r["OfferStatus"] == "Declined")

    return {
        "ok": ok,
        "message": msg,
        "invariants": {
            "one_accepted_offer": accepted == 1,
            "one_declined_offer": declined == 1,
            "listing_sold": listing_table.get(1000)["Status"] == "Sold",
            "transaction_rows": len(transaction_table.get_all()),
            "notification_rows": len(notification_table.get_all()),
        },
    }


def _scenario_atomic_failure_rollback(base_dir: Path) -> Dict[str, Any]:
    wal_path = base_dir / "atomic_failure_wal.log"
    _fresh_wal(wal_path)
    dbm = DatabaseManager(wal_path=str(wal_path))
    _create_core_tables(dbm)
    _seed_listing_and_offers(dbm)

    ok, msg = accept_offer_atomic(
        dbm,
        db_name="campus",
        offer_id=501,
        acting_seller_id=9001,
        include_notifications=True,
        create_declined_transactions=True,
        fail_after_step=3,
    )

    offer_table, _ = dbm.get_table("campus", "Offer")
    listing_table, _ = dbm.get_table("campus", "Listing")
    transaction_table, _ = dbm.get_table("campus", "Transaction")
    notification_table, _ = dbm.get_table("campus", "Notification")

    offer_rows = [row for _, row in offer_table.get_all()]
    submitted = sum(1 for r in offer_rows if r["OfferStatus"] == "Submitted")

    return {
        "ok": ok,
        "message": msg,
        "invariants": {
            "all_offers_reverted_to_submitted": submitted == 2,
            "listing_reverted_to_listed": listing_table.get(1000)["Status"] == "Listed",
            "no_transactions_written": len(transaction_table.get_all()) == 0,
            "no_notifications_written": len(notification_table.get_all()) == 0,
        },
    }


def _create_offer_only_db(wal_path: Path) -> DatabaseManager:
    dbm = DatabaseManager(wal_path=str(wal_path))
    ok, _ = dbm.create_database("campus")
    if not ok:
        pass
    schema = {
        "OfferID": int,
        "ListingID": int,
        "BuyerID": int,
        "OfferStatus": str,
        "AgreedPrice": float,
    }
    ok, msg = dbm.create_table("campus", "Offer", schema, search_key="OfferID")
    if not ok and "already exists" not in msg:
        raise RuntimeError(msg)
    return dbm


def _scenario_recovery_undo(base_dir: Path) -> Dict[str, Any]:
    wal_path = base_dir / "recovery_undo_wal.log"
    _fresh_wal(wal_path)
    dbm = _create_offer_only_db(wal_path)

    tx_id = dbm.begin_transaction()
    ok, msg = dbm.tx_insert(
        tx_id,
        "campus",
        "Offer",
        {
            "OfferID": 801,
            "ListingID": 123,
            "BuyerID": 45,
            "OfferStatus": "Submitted",
            "AgreedPrice": 0.0,
        },
    )
    if not ok:
        raise RuntimeError(msg)

    table, _ = dbm.get_table("campus", "Offer")
    pre_recover_present = table.get(801) is not None

    rec = RecoveryManager(dbm.wal)
    result = rec.recover_into(dbm)

    post_recover_present = table.get(801) is not None
    return {
        "tx_id": tx_id,
        "pre_recover_present": pre_recover_present,
        "post_recover_present": post_recover_present,
        "recovery": result,
        "invariants": {
            "undo_applied": result["applied_undo"] >= 1,
            "uncommitted_row_removed": not post_recover_present,
        },
    }


def _scenario_explicit_commit(base_dir: Path) -> Dict[str, Any]:
    """Demonstrate BEGIN → change → COMMIT (normal commit path, manual API)."""
    wal_path = base_dir / "explicit_commit_wal.log"
    _fresh_wal(wal_path)
    dbm = _create_offer_only_db(wal_path)

    tx_id = dbm.begin_transaction()
    ok, msg = dbm.tx_insert(
        tx_id,
        "campus",
        "Offer",
        {
            "OfferID": 601,
            "ListingID": 1,
            "BuyerID": 99,
            "OfferStatus": "Submitted",
            "AgreedPrice": 0.0,
        },
    )
    if not ok:
        raise RuntimeError(msg)
    c_ok, c_msg = dbm.commit_transaction(tx_id)
    table, _ = dbm.get_table("campus", "Offer")
    row = table.get(601)
    return {
        "tx_id": tx_id,
        "commit_ok": c_ok,
        "commit_message": c_msg,
        "row_present_after_commit": row is not None,
        "wal_tail_types": [e.get("type") for e in dbm.wal.read_entries()[-5:]],
        "invariants": {
            "commit_succeeded": c_ok,
            "row_visible_after_commit": row is not None,
        },
    }


def _scenario_explicit_manual_rollback(base_dir: Path) -> Dict[str, Any]:
    """Demonstrate BEGIN → change → ROLLBACK (manual rollback; row must not persist)."""
    wal_path = base_dir / "explicit_rollback_wal.log"
    _fresh_wal(wal_path)
    dbm = _create_offer_only_db(wal_path)

    tx_id = dbm.begin_transaction()
    ok, msg = dbm.tx_insert(
        tx_id,
        "campus",
        "Offer",
        {
            "OfferID": 602,
            "ListingID": 2,
            "BuyerID": 88,
            "OfferStatus": "Submitted",
            "AgreedPrice": 0.0,
        },
    )
    if not ok:
        raise RuntimeError(msg)
    table, _ = dbm.get_table("campus", "Offer")
    visible_mid_tx = table.get(602) is not None

    r_ok, r_msg = dbm.rollback_transaction(tx_id)
    row_after = table.get(602)

    return {
        "tx_id": tx_id,
        "visible_mid_transaction": visible_mid_tx,
        "rollback_ok": r_ok,
        "rollback_message": r_msg,
        "row_absent_after_rollback": row_after is None,
        "wal_tail_types": [e.get("type") for e in dbm.wal.read_entries()[-5:]],
        "invariants": {
            "rollback_succeeded": r_ok,
            "no_partial_row_after_rollback": row_after is None,
        },
    }


def _scenario_recovery_redo(base_dir: Path) -> Dict[str, Any]:
    wal_path = base_dir / "recovery_redo_wal.log"
    _fresh_wal(wal_path)

    writer = _create_offer_only_db(wal_path)
    tx_id = writer.begin_transaction()
    ok, msg = writer.tx_insert(
        tx_id,
        "campus",
        "Offer",
        {
            "OfferID": 901,
            "ListingID": 124,
            "BuyerID": 46,
            "OfferStatus": "Submitted",
            "AgreedPrice": 0.0,
        },
    )
    if not ok:
        raise RuntimeError(msg)

    ok, msg = writer.commit_transaction(tx_id)
    if not ok:
        raise RuntimeError(msg)

    restarted = _create_offer_only_db(wal_path)
    table, _ = restarted.get_table("campus", "Offer")
    pre_recover_present = table.get(901) is not None

    rec = RecoveryManager(restarted.wal)
    result = rec.recover_into(restarted)

    post_recover_present = table.get(901) is not None
    return {
        "tx_id": tx_id,
        "pre_recover_present": pre_recover_present,
        "post_recover_present": post_recover_present,
        "recovery": result,
        "invariants": {
            "redo_applied": result["applied_redo"] >= 1,
            "committed_row_restored": post_recover_present,
        },
    }


def _write_markdown(summary: Dict[str, Any], md_path: Path) -> None:
    tests = summary["tests"]
    demos = summary["demos"]

    lines = [
        "# Assignment 3 Module A - Phase 6 Artifacts",
        "",
        f"Generated at (UTC): {summary['generated_at_utc']}",
        "",
        "## Test Suite",
        f"- Command: `{tests['command']}`",
        f"- Exit code: `{tests['exit_code']}`",
        f"- Passed: `{tests['passed']}`",
        "",
        "## Scenario Results",
        "",
        "### Atomic Success",
        f"- Result: `{demos['atomic_success']['ok']}`",
        f"- Message: {demos['atomic_success']['message']}",
        f"- Invariants: `{demos['atomic_success']['invariants']}`",
        "",
        "### Atomic Failure Rollback",
        f"- Result: `{demos['atomic_failure_rollback']['ok']}`",
        f"- Message: {demos['atomic_failure_rollback']['message']}",
        f"- Invariants: `{demos['atomic_failure_rollback']['invariants']}`",
        "",
        "### Recovery Undo (Crash Before Commit)",
        f"- Recovery summary: `{demos['recovery_undo']['recovery']}`",
        f"- Invariants: `{demos['recovery_undo']['invariants']}`",
        "",
        "### Recovery Redo (Crash After Commit)",
        f"- Recovery summary: `{demos['recovery_redo']['recovery']}`",
        f"- Invariants: `{demos['recovery_redo']['invariants']}`",
        "",
        "### Explicit BEGIN / COMMIT (Manual API)",
        f"- Commit ok: `{demos['explicit_commit']['commit_ok']}`",
        f"- WAL tail (last types): `{demos['explicit_commit']['wal_tail_types']}`",
        f"- Invariants: `{demos['explicit_commit']['invariants']}`",
        "",
        "### Explicit BEGIN / ROLLBACK (Manual API)",
        f"- Rollback ok: `{demos['explicit_manual_rollback']['rollback_ok']}`",
        f"- WAL tail (last types): `{demos['explicit_manual_rollback']['wal_tail_types']}`",
        f"- Invariants: `{demos['explicit_manual_rollback']['invariants']}`",
        "",
        "## Files",
        "- `artifacts/phase6_summary.json`",
        "- `artifacts/phase6_summary.md`",
        "- `artifacts/unittest_output.txt`",
        "- `artifacts/*_wal.log` (scenario WAL traces, including `explicit_commit_wal.log` and `explicit_rollback_wal.log`)",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    artifacts_dir = ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    unittest_result = _run_unittest_suite()
    (artifacts_dir / "unittest_output.txt").write_text(
        unittest_result["stdout"] + ("\n" + unittest_result["stderr"] if unittest_result["stderr"] else ""),
        encoding="utf-8",
    )

    demos = {
        "atomic_success": _scenario_atomic_success(artifacts_dir),
        "atomic_failure_rollback": _scenario_atomic_failure_rollback(artifacts_dir),
        "recovery_undo": _scenario_recovery_undo(artifacts_dir),
        "recovery_redo": _scenario_recovery_redo(artifacts_dir),
        "explicit_commit": _scenario_explicit_commit(artifacts_dir),
        "explicit_manual_rollback": _scenario_explicit_manual_rollback(artifacts_dir),
    }

    summary = {
        "generated_at_utc": _now(),
        "tests": {
            "command": unittest_result["command"],
            "exit_code": unittest_result["exit_code"],
            "passed": unittest_result["passed"],
        },
        "demos": demos,
    }

    json_path = artifacts_dir / "phase6_summary.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_path = artifacts_dir / "phase6_summary.md"
    _write_markdown(summary, md_path)

    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Wrote: {artifacts_dir / 'unittest_output.txt'}")

    return 0 if unittest_result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
