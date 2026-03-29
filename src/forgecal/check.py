"""Comparison engine for calibration checks.

Handles numeric, string, structural, and distributional comparisons.
Pure Python — no dependencies beyond stdlib.
"""

from __future__ import annotations

from typing import Any

from .core import CheckResult, Expectation


def extract_nested(d: dict, key: str) -> Any:
    """Extract a value from a nested dict using dot notation.

    >>> extract_nested({"statistics": {"p_value": 0.03}}, "statistics.p_value")
    0.03
    >>> extract_nested({"plots": [{"title": "Chart"}]}, "plots.0.title")
    'Chart'
    """
    parts = key.split(".")
    current = d
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (IndexError, ValueError):
                return None
        else:
            return None
    return current


def check_expectation(result: dict, expectation: Expectation) -> CheckResult:
    """Check a single expectation against an analysis result.

    Supports comparison types:
    - abs_within: |actual - expected| <= tolerance
    - rel_within: |actual - expected| / |expected| <= tolerance
    - greater_than: actual > expected
    - less_than: actual < expected
    - between: expected[0] <= actual <= expected[1]
    - contains: expected substring in actual string
    - equals: actual == expected
    - type_is: type(actual).__name__ == expected
    - plot_count: len(result.get("plots", [])) compared
    """
    exp = expectation
    base = CheckResult(
        key=exp.key,
        expected=exp.expected,
        actual=None,
        tolerance=exp.tolerance,
        comparison=exp.comparison,
        passed=False,
    )

    # ── Special keys ──

    if exp.key == "guide_observation_contains":
        actual = result.get("guide_observation", "")
        base.actual = actual[:200] if isinstance(actual, str) else str(actual)[:200]
        base.passed = str(exp.expected).lower() in str(actual).lower()
        if not base.passed:
            base.detail = f"'{exp.expected}' not found in guide_observation"
        return base

    if exp.key == "summary_contains":
        actual = result.get("summary", "")
        base.actual = actual[:200] if isinstance(actual, str) else str(actual)[:200]
        base.passed = str(exp.expected).lower() in str(actual).lower()
        if not base.passed:
            base.detail = f"'{exp.expected}' not found in summary"
        return base

    if exp.key == "plot_count":
        actual = len(result.get("plots", []))
        base.actual = actual
        return _numeric_check(base, float(actual), float(exp.expected), exp)

    # ── Standard extraction ──

    actual = extract_nested(result, exp.key)
    base.actual = actual

    if actual is None:
        base.detail = f"Key '{exp.key}' not found in result"
        return base

    # ── Type check ──

    if exp.comparison == "type_is":
        actual_type = type(actual).__name__
        base.actual = actual_type
        base.passed = actual_type == exp.expected
        base.detail = f"type is {actual_type}, expected {exp.expected}"
        return base

    # ── Equals (exact) ──

    if exp.comparison == "equals":
        base.passed = actual == exp.expected
        base.detail = f"{actual} {'==' if base.passed else '!='} {exp.expected}"
        return base

    # ── Contains (string) ──

    if exp.comparison == "contains":
        base.passed = str(exp.expected) in str(actual)
        base.detail = f"'{exp.expected}' {'found' if base.passed else 'not found'} in '{actual}'"
        return base

    # ── Between (range) ──

    if exp.comparison == "between":
        try:
            lo, hi = float(exp.expected[0]), float(exp.expected[1])
            actual_f = float(actual)
            base.passed = lo <= actual_f <= hi
            base.deviation = min(abs(actual_f - lo), abs(actual_f - hi)) if not base.passed else 0.0
            base.detail = f"{actual_f:.6f} {'in' if base.passed else 'outside'} [{lo}, {hi}]"
        except (TypeError, ValueError, IndexError) as e:
            base.detail = f"Cannot check 'between': {e}"
        return base

    # ── Numeric comparisons ──

    try:
        actual_f = float(actual)
        expected_f = float(exp.expected)
    except (TypeError, ValueError):
        base.detail = f"Cannot compare: actual={actual}, expected={exp.expected}"
        return base

    return _numeric_check(base, actual_f, expected_f, exp)


def _numeric_check(
    base: CheckResult, actual_f: float, expected_f: float, exp: Expectation
) -> CheckResult:
    """Perform numeric comparison."""

    if exp.comparison == "greater_than":
        base.passed = actual_f > expected_f
        base.deviation = expected_f - actual_f if not base.passed else 0.0
        base.detail = f"{actual_f:.6f} {'>' if base.passed else '<='} {expected_f}"

    elif exp.comparison == "less_than":
        base.passed = actual_f < expected_f
        base.deviation = actual_f - expected_f if not base.passed else 0.0
        base.detail = f"{actual_f:.6f} {'<' if base.passed else '>='} {expected_f}"

    elif exp.comparison == "abs_within":
        deviation = abs(actual_f - expected_f)
        base.deviation = deviation
        base.passed = deviation <= exp.tolerance
        base.detail = (
            f"|{actual_f:.6f} - {expected_f}| = {deviation:.6f}"
            f" {'<=' if base.passed else '>'} {exp.tolerance}"
        )

    elif exp.comparison == "rel_within":
        if abs(expected_f) < 1e-15:
            base.detail = "Cannot compute relative deviation: expected ≈ 0"
            base.passed = abs(actual_f) < 1e-10
        else:
            rel_dev = abs(actual_f - expected_f) / abs(expected_f)
            base.deviation = rel_dev
            base.passed = rel_dev <= exp.tolerance
            base.detail = (
                f"|{actual_f:.6f} - {expected_f}| / |{expected_f}| = {rel_dev:.6f}"
                f" {'<=' if base.passed else '>'} {exp.tolerance}"
            )

    else:
        base.detail = f"Unknown comparison: {exp.comparison}"

    return base
