# Module B - B+tree Track: Multi-user Behaviour and Stress Testing

Implements Assignment 3 stress requirements on top of the custom Module A engine: concurrent usage, race conditions, failure simulation, durability checks, and high-volume load.

## How it works

[`run_experiments.py`](run_experiments.py) executes a batch of scenarios by shelling out to [`../../Module_A/scripts/stress_driver.py`](../../Module_A/scripts/stress_driver.py).

The stress driver uses [`../../Module_A/scripts/stress_engine.py`](../../Module_A/scripts/stress_engine.py), which wraps the Module A transaction engine (`DatabaseManager`, WAL, recovery, and campus workflow).

Batch outputs are written to:

- `Assignment_3/Module_B/B+tree/artifacts/module_b_results.json` (machine-readable summary)
- `Assignment_3/Module_B/B+tree/artifacts/module_b_stdout.txt` (concatenated run logs)

## Experiment set

| Experiment name | Scenario | Purpose |
|---|---|---|
| `concurrent_race_same_listing` | `accept_race` | Many threads compete on one listing; exactly one commit should succeed per iteration. |
| `concurrent_load_separate_listings` | `accept_load` | Parallel accepts on disjoint listings to measure throughput under serialization. |
| `failure_injection_rollback` | `failure_injection` | Inject random mid-transaction failures and verify clean rollback. |
| `crash_recovery_durability` | `crash_recovery` | Commit, simulate restart, replay WAL, and verify durability. |
| `stress_bulk_1000_ops` | `stress_bulk` | 50 x 20 = 1000 accept attempts. |
| `stress_bulk_2500_ops` | `stress_bulk` | 125 x 20 = 2500 accept attempts. |
| `consistency_check` | `consistency_check` | Deep referential-integrity checks after a race scenario. |
| `mixed_concurrent_failure` | `mixed_concurrent_failure` | Mixed successful and failing threads under concurrency. |

## Run

From repo root:

```bash
python Assignment_3/Module_B/B+tree/run_experiments.py
```

Or from this folder:

```bash
python run_experiments.py
```

Exit code:

- `0` -> all experiments passed
- `1` -> one or more experiments failed

## Related docs

- Detailed field-level output guide: [`RESULTS_GUIDE.md`](RESULTS_GUIDE.md)
- Assignment-level summary: [`../MODULE_B_REPORT.md`](../MODULE_B_REPORT.md)
