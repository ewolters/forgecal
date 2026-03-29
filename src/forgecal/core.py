"""Core dataclasses for the calibration system.

These define the contract between ForgeCal and any package that
provides calibration cases. Pure Python — no dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Expectation:
    """A single expected outcome from a calibration case.

    key: Dot-notation path into the result dict (e.g. "statistics.p_value").
         Special keys:
         - "summary_contains" — check substring in summary
         - "guide_observation_contains" — check substring
         - "plot_count" — check number of plots returned
    expected: The expected value.
    tolerance: Acceptable deviation for numeric comparisons.
    comparison: How to compare actual vs expected:
        "abs_within" — |actual - expected| <= tolerance (DEFAULT)
        "rel_within" — |actual - expected| / |expected| <= tolerance
        "greater_than" — actual > expected
        "less_than" — actual < expected
        "between" — expected[0] <= actual <= expected[1]
        "contains" — expected substring found in actual string
        "equals" — actual == expected (exact match)
        "type_is" — type(actual).__name__ == expected
    """

    key: str
    expected: Any
    tolerance: float = 0.0
    comparison: str = "abs_within"


@dataclass
class CalibrationCase:
    """A reference case with known correct answer.

    This is the universal case format. Every forge package converts
    its golden files into these before ForgeCal runs them.

    case_id: Unique identifier (e.g. "CAL-SPC-001", "CAL-STATS-042").
    package: Which forge package owns this case (e.g. "forgespc").
    category: Grouping within the package (e.g. "imr", "capability", "anova").
    analysis_type: Dispatch key (e.g. "stats", "spc", "bayesian").
    analysis_id: Specific analysis (e.g. "ttest", "imr", "regression").
    config: Configuration dict passed to the analysis function.
    data: Dict of column_name → list of values (used to build DataFrame).
    expectations: List of Expectation objects to verify.
    description: Human-readable description of what this case tests.
    tags: Optional tags for filtering (e.g. ["regression", "critical"]).
    """

    case_id: str
    package: str
    category: str
    analysis_type: str
    analysis_id: str
    config: dict
    data: dict
    expectations: list[Expectation]
    description: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    """Result of checking a single expectation."""

    key: str
    expected: Any
    actual: Any
    tolerance: float
    comparison: str
    passed: bool
    detail: str = ""
    deviation: float | None = None  # for numeric: how far off


@dataclass
class CaseResult:
    """Result of running a single calibration case."""

    case_id: str
    package: str
    category: str
    description: str
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class CalibrationReport:
    """Full calibration report across all packages."""

    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    error_cases: int = 0
    pass_rate: float = 0.0
    results: list[CaseResult] = field(default_factory=list)
    failures: list[CaseResult] = field(default_factory=list)
    by_package: dict[str, dict] = field(default_factory=dict)
    drift_alerts: list[dict] = field(default_factory=list)
    is_calibrated: bool = False
    calibration_threshold: float = 0.95  # pass rate required

    def compute(self):
        """Compute summary stats from results."""
        self.total_cases = len(self.results)
        self.passed_cases = sum(1 for r in self.results if r.passed)
        self.failed_cases = sum(1 for r in self.results if not r.passed and not r.error)
        self.error_cases = sum(1 for r in self.results if r.error)
        self.pass_rate = self.passed_cases / self.total_cases if self.total_cases else 0.0
        self.failures = [r for r in self.results if not r.passed]
        self.is_calibrated = self.pass_rate >= self.calibration_threshold

        # Per-package breakdown
        packages = set(r.package for r in self.results)
        self.by_package = {}
        for pkg in packages:
            pkg_results = [r for r in self.results if r.package == pkg]
            pkg_passed = sum(1 for r in pkg_results if r.passed)
            self.by_package[pkg] = {
                "total": len(pkg_results),
                "passed": pkg_passed,
                "pass_rate": pkg_passed / len(pkg_results) if pkg_results else 0.0,
            }


@dataclass
class CalibrationAdapter:
    """Interface a forge package exposes for calibration.

    package: Package name (e.g. "forgespc").
    version: Package version string.
    cases: List of CalibrationCase objects.
    runner: Callable that takes a CalibrationCase and returns a result dict.
            The result dict is whatever the analysis function returns —
            ForgeCal checks expectations against it.
    """

    package: str
    version: str
    cases: list[CalibrationCase]
    runner: Callable[[CalibrationCase], dict]
