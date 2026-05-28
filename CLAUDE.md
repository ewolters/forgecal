# ForgeCal

Master calibration service for the Forge ecosystem. R is the source of truth — golden reference values are computed by authoritative R packages, and Python must match them.

## Architecture

```
forgecal/
├── R/                        # R calibration scripts (source of truth)
│   ├── helpers.R             # JSON output, expectation builders
│   ├── generate_all.R        # Master: Rscript R/generate_all.R
│   ├── cal_spc.R             # 6 cases via qcc (I-MR, X-bar/R, Cp/Cpk, p, c)
│   ├── cal_stat.R            # 9 cases via base R (t-test, ANOVA, cor, χ², regression)
│   ├── cal_doe.R             # 6 cases via FrF2/rsm/DoE.base (factorial, CCD, BBD, PB)
│   └── cal_rel.R             # 4 cases via WeibullR/survival (Weibull MLE, K-M, MTBF)
├── golden/                   # R-generated JSON (25 cases, 99 expectations)
│   ├── spc/r_reference.json  # 6 cases, 28 checks
│   ├── stat/r_reference.json # 9 cases, 40 checks
│   ├── doe/r_reference.json  # 6 cases, 16 checks
│   └── rel/r_reference.json  # 4 cases, 15 checks
├── src/forgecal/
│   ├── core.py               # Expectation, CalibrationCase, CaseResult dataclasses
│   ├── check.py              # Comparison engine (abs, rel, gt, lt, between, equals)
│   ├── validate.py           # NEW: load R golden → run forge package → compare
│   ├── discovery.py          # Auto-discover installed forge packages
│   ├── runner.py             # Execute cases via adapter pattern
│   └── drift.py              # Track result drift over time
└── tests/
    └── test_core.py          # 22 tests
```

## Regenerating Golden Files

```bash
cd ~/forgecal
Rscript R/generate_all.R
```

Requires: R 4.x with qcc, FrF2, rsm, DoE.base, WeibullR, survival, jsonlite

## Validating Python Against R

```python
from forgecal.validate import validate_all, validate_package

# One package
report = validate_package("forgespc")
print(report.summary())  # "28/28 PASS"

# All packages
reports = validate_all()
for pkg, r in reports.items():
    print(f"{pkg}: {r.passed_checks}/{r.total_checks}")
```

## R Package → Forge Package Mapping

| R Package | What it validates | Forge Package |
|-----------|-------------------|---------------|
| qcc       | Cp/Cpk, I-MR, X-bar/R, p-chart, c-chart | forgespc |
| base R    | t.test, aov, cor.test, chisq.test, wilcox.test, kruskal.test, lm | forgestat |
| FrF2      | Fractional factorials, Plackett-Burman | forgedoe |
| rsm       | CCD, Box-Behnken | forgedoe |
| DoE.base  | Design matrices | forgedoe |
| WeibullR  | 2P MLE (complete + censored) | forgerel |
| survival  | Kaplan-Meier, survreg | forgerel |

## Current Calibration Status

| Package | R Cases | Checks | Status |
|---------|---------|--------|--------|
| forgespc | 6 | 28/28 | **PASS** |
| forgestat | 9 | 40/40 | **PASS** |
| forgedoe | 6 | 8/16 | 3 design size discrepancies (R vs Python algorithms) |
| forgerel | 4 | 13/15 | **87%** — Kaplan-Meier not implemented in forgerel |

## Dependencies

- Core: stdlib only (dataclasses, json, pathlib)
- Validate: imports forge packages being tested
- R scripts: R 4.x + packages listed above
