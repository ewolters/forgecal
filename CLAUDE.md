# ForgeCal

Master calibration service for the Forge ecosystem. Treats every analysis function as a measurement instrument that requires periodic verification against known-correct references.

## What This Is

A standalone Python package that:
1. Defines what a calibration case IS (structured golden reference with expectations)
2. Discovers calibration cases from installed forge packages automatically
3. Runs cases against analysis functions via adapter pattern
4. Detects drift — not just pass/fail, but HOW MUCH results change over time
5. Generates calibration certificates (via forgedoc if installed)

## Architecture

```
forgecal/
├── core.py          # Expectation, CalibrationCase, CaseResult dataclasses
├── check.py         # Comparison engine (numeric, string, distribution)
├── discovery.py     # Auto-discover golden refs from installed packages
├── runner.py        # Execute cases via adapter functions
├── drift.py         # Track result changes over time, detect statistical drift
├── report.py        # Generate calibration reports
├── golden/          # ForgeCal's own meta-calibration cases
└── adapters/        # Built-in adapters for forge packages
    ├── __init__.py
    └── registry.py  # Package → adapter mapping
```

## Key Design: The Adapter Pattern

Each forge package exposes a calibration adapter:

```python
# In forgespc/calibration.py:
def get_calibration_adapter():
    return {
        "package": "forgespc",
        "version": forgespc.__version__,
        "cases": load_golden_cases(),      # list[CalibrationCase]
        "runner": run_spc_case,            # callable(CalibrationCase) → dict
    }
```

ForgeCal discovers these automatically:
```python
# forgecal.discovery finds all installed packages with calibration adapters
adapters = discover_adapters()  # finds forgespc, forgestats, etc.
results = run_calibration(adapters)
```

## Dependencies

- Core: stdlib only (dataclasses, json, pathlib, importlib)
- Optional: numpy (for drift detection statistics), forgedoc (for certificate generation)

## No Django. No web framework. No I/O except reading golden JSON files.
