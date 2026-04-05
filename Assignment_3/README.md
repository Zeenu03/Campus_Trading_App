# Assignment 3 — Transaction Management, Concurrency, and ACID Validation

This folder contains the Assignment 3 deliverables for:

- **Module A:** custom B+ Tree transaction engine, WAL logging, and crash recovery
- **Module B:** concurrent and stress-testing workflows (B+ Tree engine and MySQL backend tracks)

## Structure at a glance

| Component | Purpose | Primary doc |
|---|---|---|
| `Module_A/` | ACID transactions, WAL, REDO/UNDO recovery, stress driver | [`Module_A/README.md`](Module_A/README.md) |
| `Module_B/B+tree/` | Stress experiments against custom Module A engine | [`Module_B/B+tree/README.md`](Module_B/B+tree/README.md) |
| `Module_B/MySQL/` | Stress suite against Go + MySQL stack | [`Module_B/MySQL/RESULTS_GUIDE.md`](Module_B/MySQL/RESULTS_GUIDE.md) |

## Quick links

| Deliverable | Location |
|---|---|
| Assignment specification | [`ASSIGNMENT_SPECIFICATION.md`](ASSIGNMENT_SPECIFICATION.md) |
| Final report PDF | [`FinalReport.pdf`](FinalReport.pdf) |
| Assignment submission PDF | [`Track1_Assignment3.pdf`](Track1_Assignment3.pdf) |
| Module A guide | [`Module_A/README.md`](Module_A/README.md) |
| Module A detailed report | [`Module_A/MODULE_A_REPORT.md`](Module_A/MODULE_A_REPORT.md) |
| Module A notebook demo | [`Module_A/acid_properties_demo.ipynb`](Module_A/acid_properties_demo.ipynb) |
| Module B report | [`Module_B/MODULE_B_REPORT.md`](Module_B/MODULE_B_REPORT.md) |
| Module B (B+tree) runner | [`Module_B/B+tree/run_experiments.py`](Module_B/B+tree/run_experiments.py) |
| Module B (B+tree) results guide | [`Module_B/B+tree/RESULTS_GUIDE.md`](Module_B/B+tree/RESULTS_GUIDE.md) |
| Module B (MySQL) runner | [`Module_B/MySQL/run_stress.py`](Module_B/MySQL/run_stress.py) |
| Module B (MySQL) results guide | [`Module_B/MySQL/RESULTS_GUIDE.md`](Module_B/MySQL/RESULTS_GUIDE.md) |

## How to run

### Module A

From `Assignment_3/Module_A`:

```bash
python -m pip install -r requirements.txt
python scripts/stress_driver.py --scenario mixed_concurrent_failure --threads 10 --iterations 5
```

### Module B — B+tree track

From `Assignment_3`:

```bash
python Module_B/B+tree/run_experiments.py
```

### Module B — MySQL track

From `Assignment_3/Module_B/MySQL`:

```bash
python -m pip install -r requirements.txt
python run_stress.py
```

## Output locations

- Module A generated WAL/demo logs: `Module_A/artifacts/`
- Module B B+tree experiment outputs: `Module_B/B+tree/artifacts/`
- Module B MySQL experiment outputs and charts: `Module_B/MySQL/artifacts/`

## Requirements

- Python 3.10+ (3.13 recommended)
- Docker Desktop (required for MySQL track)
- Go 1.21+ (required for MySQL track backend integration)
