# Assignment 3 — Transaction Management, Concurrency, and ACID Validation

This folder contains **Module A** (custom B+ Tree transaction engine + WAL recovery) and **Module B** (multi-threaded stress experiments), plus generated evidence for the written report and video.

## Quick links

| Deliverable | Location |
|-------------|----------|
| **Combined report** (spec §6 + §8) | [`ASSIGNMENT_3_COMBINED_REPORT.md`](ASSIGNMENT_3_COMBINED_REPORT.md) |
| Module A implementation | [`Module_A/`](Module_A/) |
| Module A deep-dive write-up | [`Module_A/ASSIGNMENT_3_IMPLEMENTATION_EXPLAINED.md`](Module_A/ASSIGNMENT_3_IMPLEMENTATION_EXPLAINED.md) |
| Module B experiment runner | [`Module_B/run_experiments.py`](Module_B/run_experiments.py) |
| Module B JSON results | [`artifacts/module_b_results.json`](artifacts/module_b_results.json) |
| Module A test + demo summary | [`Module_A/artifacts/phase6_summary.json`](Module_A/artifacts/phase6_summary.json) |
| Assignment specification | [`ASSIGNMENT_SPECIFICATION.md`](ASSIGNMENT_SPECIFICATION.md) |

## Regenerate all evidence + report

From **`Assignment_3`**:

```bash
python3 scripts/build_assignment3_evidence.py
```

This runs the full Module A unittest suite and phase-6 demos (including explicit `BEGIN`/`COMMIT` and `BEGIN`/`ROLLBACK`), executes the Module B batch (races, load, failures, crash recovery, **1000+** and **2500+** operation stress runs), and rewrites `ASSIGNMENT_3_COMBINED_REPORT.md`.

**Python 3.10+** required (3.13 recommended).
