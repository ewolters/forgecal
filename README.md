# ForgeCal

Master calibration service for the Forge ecosystem. Treats every analysis function as a measurement instrument that requires periodic verification against known-correct references.

## Install

```bash
pip install forgecal              # Core (stdlib only)
pip install forgecal[drift]       # Add drift detection (numpy)
pip install forgecal[docs]        # Add certificate generation (forgedoc)
```

## Quick Start

```python
from forgecal import run_calibration, discover_adapters

# Auto-discover all installed forge packages with calibration cases
adapters = discover_adapters()
report = run_calibration(adapters)

print(f"Calibrated: {report.is_calibrated} ({report.pass_rate:.0%})")
print(f"Packages: {list(report.by_package.keys())}")

for failure in report.failures:
    print(f"  FAIL: {failure.case_id} — {failure.checks[0].detail}")
```

## How It Works

ForgeCal defines a universal calibration protocol. Any Python package can participate by exposing a calibration adapter:

```python
# In your_package/calibration.py:
from forgecal import CalibrationAdapter, CalibrationCase, Expectation

def get_calibration_adapter():
    return CalibrationAdapter(
        package="your_package",
        version="1.0.0",
        cases=[
            CalibrationCase(
                case_id="CAL-001",
                package="your_package",
                category="basic",
                analysis_type="stats",
                analysis_id="ttest",
                config={"alternative": "two-sided"},
                data={"group_a": [2.1, 2.4, 2.3], "group_b": [2.8, 3.0, 2.9]},
                expectations=[
                    Expectation(key="statistics.p_value", expected=0.005, tolerance=0.01),
                    Expectation(key="statistics.significant", expected=True, comparison="equals"),
                ],
                description="Two-sample t-test on clearly separated groups",
            ),
        ],
        runner=run_my_analysis,
    )

def run_my_analysis(case):
    """Execute the analysis and return the result dict."""
    from your_package import analyze
    import pandas as pd
    df = pd.DataFrame(case.data)
    return analyze(df, case.analysis_id, case.config)
```

ForgeCal discovers this automatically when `your_package` is installed:

```python
adapters = discover_adapters()  # finds your_package
report = run_calibration(adapters)
```

## Comparison Types

| Type | Usage | Example |
|------|-------|---------|
| `abs_within` | \|actual - expected\| ≤ tolerance | p-value within 0.01 |
| `rel_within` | \|actual - expected\| / \|expected\| ≤ tolerance | Effect size within 5% |
| `greater_than` | actual > expected | F-statistic above threshold |
| `less_than` | actual < expected | p-value below significance |
| `between` | expected[0] ≤ actual ≤ expected[1] | Cpk in range [1.2, 1.8] |
| `contains` | substring in string | "significant" in summary |
| `equals` | exact match | sample size == 50 |
| `type_is` | type name check | result is float |

Special keys: `summary_contains`, `guide_observation_contains`, `plot_count`

Nested key extraction with dot notation: `statistics.p_value`, `plots.0.title`

## Drift Detection

Not just pass/fail — track HOW MUCH results change over time:

```python
from forgecal import run_calibration
from forgecal.drift import detect_drift, save_run

report = run_calibration()

# Save this run to history
save_run(report, history_dir="./cal_history")

# Compare against historical runs
drift = detect_drift(report, history_dir="./cal_history")

for alert in drift.alerts:
    print(f"  {alert.severity}: {alert.case_id} — {alert.alert_type}")
    print(f"    {alert.detail}")
```

Drift detection types:

| Alert | What It Means |
|-------|---------------|
| `gradual_drift` | Value moving slowly away from historical mean (>2σ) |
| `sudden_shift` | Value jumped significantly from historical mean (>3σ) |
| `new_failure` | Case was passing, now fails |
| `recovery` | Case was failing, now passes |

Thresholds are configurable:

```python
drift = detect_drift(
    report,
    history_dir="./cal_history",
    window=10,              # last 10 runs
    drift_threshold=2.0,    # σ for gradual drift
    shift_threshold=3.0,    # σ for sudden shift
)
```

## Subset Selection

For large reference pools, select a rotating daily subset:

```python
report = run_calibration(
    adapters,
    subset_size=8,    # run 8 cases per package
    seed=None,        # defaults to today's date (deterministic daily rotation)
)
```

Same seed = same subset. Different day = different cases. Full pool coverage over time.

## Filtering

```python
# Only specific packages
report = run_calibration(adapters, packages=["forgespc", "forgestats"])

# Only specific tags
report = run_calibration(adapters, tags=["regression", "critical"])

# Custom pass threshold
report = run_calibration(adapters, threshold=0.90)  # 90% required
```

## Per-Package Reports

```python
report = run_calibration()

for pkg, stats in report.by_package.items():
    print(f"{pkg}: {stats['passed']}/{stats['total']} ({stats['pass_rate']:.0%})")
```

## Architecture

```
forgecal/
├── core.py          # Universal types (Expectation, Case, Result, Report, Adapter)
├── check.py         # Comparison engine (8 comparison types + nested extraction)
├── discovery.py     # Auto-discover adapters from installed packages
├── runner.py        # Execute cases, build reports, error isolation
└── drift.py         # Track changes over time, detect statistical drift
```

**The adapter pattern** — ForgeCal is the framework. Each forge package brings its own golden references and runner function. ForgeCal discovers, orchestrates, and reports.

```
forgecal (framework)      ← you are here
  ├── forgespc (adapter)  ← SPC golden refs + SPC runner
  ├── forgestats (adapter)← stats golden refs + stats runner
  ├── forgeml (adapter)   ← ML golden refs + ML runner
  └── ...                 ← any package with get_calibration_adapter()
```

## Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| (none) | Core is stdlib only | — |
| numpy | Drift detection statistics | Optional (`[drift]`) |
| forgedoc | Certificate generation | Optional (`[docs]`) |

Zero system dependencies. `pip install` and go.

## License

MIT
