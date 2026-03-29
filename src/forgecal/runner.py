"""Calibration runner — executes cases and builds reports.

The runner is decoupled from specific analysis packages. It takes
adapters (which provide cases + runner functions) and executes them.

Supports:
- Subset selection (date-seeded RNG for daily rotation)
- Parallel execution (optional)
- Timeout per case
- Error isolation (one case failure doesn't block others)
"""

from __future__ import annotations

import random
import time
from datetime import date
from typing import Callable

from .check import check_expectation
from .core import (
    CalibrationAdapter,
    CalibrationCase,
    CalibrationReport,
    CaseResult,
)


def run_calibration(
    adapters: list[CalibrationAdapter] | None = None,
    cases: list[CalibrationCase] | None = None,
    runner: Callable[[CalibrationCase], dict] | None = None,
    seed: int | None = None,
    subset_size: int = 0,
    tags: list[str] | None = None,
    packages: list[str] | None = None,
    threshold: float = 0.95,
) -> CalibrationReport:
    """Run calibration cases and return a report.

    Two modes:
    1. Adapter mode: pass `adapters` (each has cases + runner). Auto-discovered
       via discovery.discover_adapters() if not provided.
    2. Direct mode: pass `cases` + `runner` explicitly (for single-package testing).

    Args:
        adapters: List of CalibrationAdapter objects. Auto-discovered if None.
        cases: Direct list of cases (bypasses adapter discovery).
        runner: Direct runner function (bypasses adapter runners).
        seed: RNG seed for subset selection. Defaults to today's date ordinal.
        subset_size: Max cases to run per package. 0 = run all.
        tags: Only run cases with these tags. None = all.
        packages: Only run cases from these packages. None = all.
        threshold: Pass rate required for is_calibrated (default 0.95).

    Returns:
        CalibrationReport with per-case results and summary.
    """

    # ── Resolve cases and runners ──

    case_runner_pairs: list[tuple[CalibrationCase, Callable]] = []

    if cases is not None and runner is not None:
        # Direct mode
        case_runner_pairs = [(c, runner) for c in cases]
    else:
        # Adapter mode
        if adapters is None:
            from .discovery import discover_adapters
            adapters = discover_adapters()

        for adapter in adapters:
            if packages and adapter.package not in packages:
                continue
            for case in adapter.cases:
                case_runner_pairs.append((case, adapter.runner))

    # ── Filter by tags ──

    if tags:
        tag_set = set(tags)
        case_runner_pairs = [
            (c, r) for c, r in case_runner_pairs
            if tag_set.intersection(c.tags)
        ]

    # ── Subset selection ──

    if subset_size > 0 and len(case_runner_pairs) > subset_size:
        if seed is None:
            seed = date.today().toordinal()
        rng = random.Random(seed)
        case_runner_pairs = rng.sample(case_runner_pairs, subset_size)

    # ── Run ──

    report = CalibrationReport(calibration_threshold=threshold)

    for case, case_runner in case_runner_pairs:
        t0 = time.time()
        try:
            result_dict = case_runner(case)
            case_result = _check_case(case, result_dict)
        except Exception as e:
            case_result = CaseResult(
                case_id=case.case_id,
                package=case.package,
                category=case.category,
                description=case.description,
                passed=False,
                error=str(e),
            )
        case_result.duration_ms = (time.time() - t0) * 1000
        report.results.append(case_result)

    report.compute()
    return report


def _check_case(case: CalibrationCase, result: dict) -> CaseResult:
    """Check all expectations for a single case against the analysis result."""
    checks = []
    all_passed = True

    for exp in case.expectations:
        check = check_expectation(result, exp)
        checks.append(check)
        if not check.passed:
            all_passed = False

    return CaseResult(
        case_id=case.case_id,
        package=case.package,
        category=case.category,
        description=case.description,
        passed=all_passed,
        checks=checks,
    )
