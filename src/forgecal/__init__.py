"""ForgeCal — Master calibration service for the Forge ecosystem.

Treats every analysis function as a measurement instrument that requires
periodic verification against known-correct references.

Usage:
    from forgecal import run_calibration, discover_adapters

    # Auto-discover all installed forge packages with calibration cases
    adapters = discover_adapters()
    report = run_calibration(adapters)
    print(f"Calibrated: {report.is_calibrated} ({report.pass_rate:.0%})")

    # Or run a specific package
    report = run_calibration(packages=["forgespc"])

    # With drift detection
    from forgecal.drift import detect_drift, save_run
    drift = detect_drift(report, history_dir="./cal_history")
    save_run(report, history_dir="./cal_history")
"""

from .core import (
    CalibrationAdapter,
    CalibrationCase,
    CalibrationReport,
    CaseResult,
    CheckResult,
    Expectation,
)
from .discovery import discover_adapters
from .runner import run_calibration

__version__ = "0.1.0"

__all__ = [
    "CalibrationAdapter",
    "CalibrationCase",
    "CalibrationReport",
    "CaseResult",
    "CheckResult",
    "Expectation",
    "discover_adapters",
    "run_calibration",
]
