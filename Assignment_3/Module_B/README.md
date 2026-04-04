# Module B — Multi-user behaviour and stress testing

Implements the requirements in **Assignment 3 §4**: concurrent users, race conditions on shared data, failure simulation, and high-volume stress (hundreds/thousands of operations).

## How it works

[`run_experiments.py`](run_experiments.py) drives [`Module_A/scripts/stress_driver.py`](../Module_A/scripts/stress_driver.py), which uses [`EngineFacade`](../Module_A/database/engine_facade.py) over the same B+ Tree engine as Module A. Results are written to:

- `Assignment_3/artifacts/module_b_results.json` — machine-readable batch summary  
- `Assignment_3/artifacts/module_b_stdout.txt` — concatenated JSON per experiment  

## Experiments

| Name | Scenario | Role |
|------|----------|------|
| `concurrent_race_same_listing` | `accept_race` | Many threads compete on one listing; exactly one commit succeeds per iteration. |
| `concurrent_load_separate_listings` | `accept_load` | Parallel work on disjoint listings (throughput under global serialization). |
| `failure_injection_rollback` | `failure_injection` | Random mid-flow failures; rollbacks leave no inconsistent multi-table state. |
| `crash_recovery_durability` | `crash_recovery` | Commit then WAL replay; listing stays `Sold`. |
| `stress_bulk_1000_ops` | `stress_bulk` | 50 × 20 = **1000** `accept_offer` attempts. |
| `stress_bulk_2500_ops` | `stress_bulk` | 125 × 20 = **2500** attempts. |

## Run

From `Assignment_3`:

```bash
python3 Module_B/run_experiments.py
```

Exit code `0` means every experiment reported `passed` and exited cleanly.
