"""Drift detection — track calibration results over time.

Not just pass/fail, but HOW MUCH results change between calibration runs.
Detects:
- Gradual drift (a value slowly moving away from expected)
- Sudden shifts (a value jumping between runs)
- Precision changes (variability increasing even if mean is OK)
- New failures (a case that was passing now fails)
- Recoveries (a case that was failing now passes)

Stores history as simple JSON files — no database required.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .core import CalibrationReport, CaseResult


@dataclass
class DriftAlert:
    """A single drift detection alert."""

    case_id: str
    package: str
    alert_type: str  # "gradual_drift", "sudden_shift", "new_failure", "recovery", "precision_loss"
    metric_key: str
    detail: str
    severity: str = "warning"  # "warning", "critical"
    current_value: Any = None
    historical_mean: float | None = None
    historical_std: float | None = None


@dataclass
class DriftReport:
    """Summary of drift detection across a calibration run."""

    alerts: list[DriftAlert] = field(default_factory=list)
    cases_analyzed: int = 0
    new_failures: int = 0
    recoveries: int = 0
    drifting: int = 0


def detect_drift(
    current: CalibrationReport,
    history_dir: str | Path | None = None,
    window: int = 10,
    drift_threshold: float = 2.0,
    shift_threshold: float = 3.0,
) -> DriftReport:
    """Compare current calibration results against history to detect drift.

    Args:
        current: The current calibration report.
        history_dir: Directory containing historical result JSON files.
                     If None, drift detection is skipped (no history available).
        window: Number of historical runs to consider.
        drift_threshold: Number of standard deviations for gradual drift alert.
        shift_threshold: Number of standard deviations for sudden shift alert.

    Returns:
        DriftReport with alerts.
    """
    report = DriftReport(cases_analyzed=len(current.results))

    if history_dir is None:
        return report

    history_path = Path(history_dir)
    if not history_path.exists():
        return report

    # Load historical results
    history = _load_history(history_path, window)
    if not history:
        return report

    for case_result in current.results:
        alerts = _analyze_case_drift(case_result, history, drift_threshold, shift_threshold)
        report.alerts.extend(alerts)
        for a in alerts:
            if a.alert_type == "new_failure":
                report.new_failures += 1
            elif a.alert_type == "recovery":
                report.recoveries += 1
            elif a.alert_type in ("gradual_drift", "sudden_shift", "precision_loss"):
                report.drifting += 1

    return report


def save_run(report: CalibrationReport, history_dir: str | Path) -> Path:
    """Save a calibration run to the history directory.

    Returns the path of the saved file.
    """
    history_path = Path(history_dir)
    history_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cal_{timestamp}.json"
    filepath = history_path / filename

    data = {
        "timestamp": datetime.now().isoformat(),
        "total_cases": report.total_cases,
        "pass_rate": report.pass_rate,
        "results": [],
    }

    for cr in report.results:
        case_data = {
            "case_id": cr.case_id,
            "package": cr.package,
            "passed": cr.passed,
            "error": cr.error,
            "checks": [],
        }
        for check in cr.checks:
            case_data["checks"].append({
                "key": check.key,
                "actual": _serialize_value(check.actual),
                "expected": _serialize_value(check.expected),
                "passed": check.passed,
                "deviation": check.deviation,
            })
        data["results"].append(case_data)

    filepath.write_text(json.dumps(data, indent=2, default=str))
    return filepath


def _load_history(history_path: Path, window: int) -> list[dict]:
    """Load the most recent N historical runs."""
    files = sorted(history_path.glob("cal_*.json"), reverse=True)[:window]
    history = []
    for f in files:
        try:
            history.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return history


def _analyze_case_drift(
    current: CaseResult,
    history: list[dict],
    drift_threshold: float,
    shift_threshold: float,
) -> list[DriftAlert]:
    """Analyze a single case for drift against history."""
    alerts = []

    # Find this case in historical runs
    hist_cases = []
    for run in history:
        for hc in run.get("results", []):
            if hc.get("case_id") == current.case_id:
                hist_cases.append(hc)

    if not hist_cases:
        return alerts  # No history for this case

    # ── New failure / recovery ──
    hist_passed = [hc.get("passed", False) for hc in hist_cases]
    was_passing = all(hist_passed[-3:]) if len(hist_passed) >= 3 else all(hist_passed)
    was_failing = not any(hist_passed[-3:]) if len(hist_passed) >= 3 else not any(hist_passed)

    if not current.passed and was_passing:
        alerts.append(DriftAlert(
            case_id=current.case_id,
            package=current.package,
            alert_type="new_failure",
            metric_key="passed",
            detail=f"Case was passing in last {len(hist_passed)} runs, now fails",
            severity="critical",
        ))

    if current.passed and was_failing:
        alerts.append(DriftAlert(
            case_id=current.case_id,
            package=current.package,
            alert_type="recovery",
            metric_key="passed",
            detail=f"Case was failing, now passes",
            severity="warning",
        ))

    # ── Numeric drift on individual checks ──
    for check in current.checks:
        if check.actual is None or check.deviation is None:
            continue

        # Gather historical values for this metric
        hist_values = []
        for hc in hist_cases:
            for hist_check in hc.get("checks", []):
                if hist_check.get("key") == check.key and hist_check.get("actual") is not None:
                    try:
                        hist_values.append(float(hist_check["actual"]))
                    except (TypeError, ValueError):
                        pass

        if len(hist_values) < 3:
            continue  # Not enough history

        mean = statistics.mean(hist_values)
        std = statistics.stdev(hist_values) if len(hist_values) > 1 else 0.0

        if std < 1e-15:
            # Constant historical value — any change is a shift
            try:
                current_f = float(check.actual)
                if abs(current_f - mean) > 1e-10:
                    alerts.append(DriftAlert(
                        case_id=current.case_id,
                        package=current.package,
                        alert_type="sudden_shift",
                        metric_key=check.key,
                        detail=f"Value changed from constant {mean:.6f} to {current_f:.6f}",
                        severity="critical",
                        current_value=current_f,
                        historical_mean=mean,
                        historical_std=0.0,
                    ))
            except (TypeError, ValueError):
                pass
            continue

        try:
            current_f = float(check.actual)
        except (TypeError, ValueError):
            continue

        z_score = abs(current_f - mean) / std

        if z_score > shift_threshold:
            alerts.append(DriftAlert(
                case_id=current.case_id,
                package=current.package,
                alert_type="sudden_shift",
                metric_key=check.key,
                detail=f"Value {current_f:.6f} is {z_score:.1f}σ from historical mean {mean:.6f}",
                severity="critical",
                current_value=current_f,
                historical_mean=mean,
                historical_std=std,
            ))
        elif z_score > drift_threshold:
            alerts.append(DriftAlert(
                case_id=current.case_id,
                package=current.package,
                alert_type="gradual_drift",
                metric_key=check.key,
                detail=f"Value {current_f:.6f} is {z_score:.1f}σ from historical mean {mean:.6f}",
                severity="warning",
                current_value=current_f,
                historical_mean=mean,
                historical_std=std,
            ))

    return alerts


def _serialize_value(v: Any) -> Any:
    """Make a value JSON-serializable."""
    if isinstance(v, float):
        if v != v:  # NaN
            return None
        return v
    if isinstance(v, (int, bool, str, type(None))):
        return v
    return str(v)
