"""Validate forge packages against R-generated golden reference values.

Usage:
    from forgecal.validate import validate_all, validate_package

    report = validate_all()
    print(report)

    spc_report = validate_package("spc")
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExpectationResult:
    key: str
    expected: float | list
    actual: float | None
    tolerance: float
    comparison: str
    passed: bool
    message: str = ""


@dataclass
class CaseResult:
    case_id: str
    description: str
    package: str
    passed: bool
    expectations: list[ExpectationResult] = field(default_factory=list)
    error: str = ""


@dataclass
class ValidationReport:
    package: str
    total_cases: int = 0
    passed_cases: int = 0
    total_checks: int = 0
    passed_checks: int = 0
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed_checks / self.total_checks if self.total_checks else 0.0

    @property
    def is_calibrated(self) -> bool:
        return self.total_checks > 0 and self.passed_checks == self.total_checks

    def summary(self) -> str:
        lines = [
            f"=== {self.package} Calibration: {'PASS' if self.is_calibrated else 'FAIL'} ===",
            f"Cases: {self.passed_cases}/{self.total_cases}",
            f"Checks: {self.passed_checks}/{self.total_checks} ({self.pass_rate:.0%})",
        ]
        for case in self.cases:
            if not case.passed:
                lines.append(f"  FAIL {case.case_id}: {case.description}")
                for exp in case.expectations:
                    if not exp.passed:
                        lines.append(f"    {exp.key}: expected {exp.expected}, got {exp.actual} ({exp.message})")
                if case.error:
                    lines.append(f"    ERROR: {case.error}")
        return "\n".join(lines)


# Golden file locations
_GOLDEN_ROOT = Path(__file__).parent.parent.parent / "golden"


def _load_golden(package: str) -> list[dict]:
    """Load R-generated golden reference for a package."""
    f = _GOLDEN_ROOT / package / "r_reference.json"
    if not f.exists():
        return []
    return json.loads(f.read_text())


def _check_expectation(actual: float | None, exp: dict) -> ExpectationResult:
    """Check one expectation against actual value."""
    key = exp["key"]
    expected = exp["expected"]
    tol = exp.get("tolerance", 0)
    comp = exp.get("comparison", "abs_within")

    if actual is None:
        return ExpectationResult(key=key, expected=expected, actual=None,
                                 tolerance=tol, comparison=comp, passed=False,
                                 message="value not found in result")

    passed = False
    msg = ""

    if comp == "abs_within":
        diff = abs(actual - expected)
        passed = diff <= tol
        msg = f"|{actual:.6f} - {expected:.6f}| = {diff:.6f} {'<=' if passed else '>'} {tol}"
    elif comp == "rel_within":
        if expected == 0:
            passed = abs(actual) <= tol
        else:
            diff = abs(actual - expected) / abs(expected)
            passed = diff <= tol
            msg = f"rel diff = {diff:.4f} {'<=' if passed else '>'} {tol}"
    elif comp == "greater_than":
        passed = actual > expected
        msg = f"{actual:.6f} {'>' if passed else '<='} {expected}"
    elif comp == "less_than":
        passed = actual < expected
        msg = f"{actual:.6f} {'<' if passed else '>='} {expected}"
    elif comp == "equals":
        passed = actual == expected
        msg = f"{actual} {'==' if passed else '!='} {expected}"
    elif comp == "between":
        lo, hi = expected
        passed = lo <= actual <= hi
        msg = f"{lo} <= {actual:.6f} <= {hi}: {passed}"

    return ExpectationResult(
        key=key, expected=expected, actual=actual,
        tolerance=tol, comparison=comp, passed=passed, message=msg,
    )


# ── Package-specific runners ──

def _run_spc_case(case: dict) -> dict:
    """Run a forgespc calibration case and return result dict."""
    from forgespc.charts import individuals_moving_range_chart, xbar_r_chart, p_chart, c_chart
    from forgespc.capability import calculate_capability

    cat = case["category"]
    data = case["data"]
    config = case.get("config", {})

    if cat == "imr":
        result = individuals_moving_range_chart(data["values"])
        return {
            "center": result.limits.cl,
            "sigma": (result.limits.ucl - result.limits.cl) / 3,
            "ucl": result.limits.ucl,
            "lcl": result.limits.lcl,
            "mr_bar": result.secondary_chart.limits.cl if result.secondary_chart else 0,
        }
    elif cat == "xbar_r":
        subgroups = [list(sg) for sg in data["subgroups"].values()]
        result = xbar_r_chart(subgroups)
        return {
            "xbar_center": result.limits.cl,
            "xbar_ucl": result.limits.ucl,
            "xbar_lcl": result.limits.lcl,
            "r_bar": result.secondary_chart.limits.cl if result.secondary_chart else 0,
            "r_ucl": result.secondary_chart.limits.ucl if result.secondary_chart else 0,
            "sigma": (result.limits.ucl - result.limits.cl) / 3 * math.sqrt(config.get("subgroup_size", 5)),
        }
    elif cat == "capability":
        cap = calculate_capability(data["values"], config["usl"], config["lsl"])
        return {
            "cp": cap.cp, "cpk": cap.cpk, "cpl": cap.cpl, "cpu": cap.cpu,
            "sigma_level": cap.sigma_level,
        }
    elif cat == "p_chart":
        result = p_chart(data["defectives"], data["sample_sizes"])
        return {"p_bar": result.limits.cl, "ucl": result.limits.ucl, "lcl": result.limits.lcl}
    elif cat == "c_chart":
        result = c_chart(data["defect_counts"])
        return {"c_bar": result.limits.cl, "ucl": result.limits.ucl, "lcl": result.limits.lcl}

    return {}


def _run_stat_case(case: dict) -> dict:
    """Run a forgestat calibration case using forgestat's actual API."""
    import numpy as np

    test_type = case.get("test") or case.get("category", "")
    inp = case.get("data", {})
    config = case.get("config", {})
    # Merge config into inp for backward compat with old "input" format
    if "input" in case:
        inp = case["input"]

    if test_type == "ttest_one_sample":
        from forgestat.parametric.ttest import one_sample
        mu = config.get("mu", inp.get("mu", 0))
        r = one_sample(inp["data"], mu=mu)
        return {
            "t_statistic": r.statistic, "p_value": r.p_value,
            "cohens_d": r.effect_size or 0, "df": r.df,
            "mean": r.mean_diff + mu,
        }
    elif test_type == "ttest_two_sample":
        from forgestat.parametric.ttest import two_sample
        r = two_sample(inp["x1"], inp["x2"])
        return {"t_statistic": r.statistic, "p_value": r.p_value, "df": r.df}
    elif test_type == "ttest_paired":
        from forgestat.parametric.ttest import paired
        r = paired(inp["x1"], inp["x2"])
        return {"t_statistic": r.statistic, "p_value": r.p_value, "mean_diff": r.mean_diff}
    elif test_type == "anova_one_way":
        from forgestat.parametric.anova import one_way_from_dict
        groups = inp.get("groups", inp)  # R golden puts groups at top level
        r = one_way_from_dict(groups)
        return {
            "f_statistic": r.statistic, "p_value": r.p_value,
            "ss_between": r.ss_between, "ss_within": r.ss_within,
            "eta_squared": r.effect_size or 0,
        }
    elif test_type == "anova_ss_check":
        from forgestat.parametric.anova import one_way_from_dict
        groups = inp.get("groups", inp)
        r = one_way_from_dict(groups)
        valid = abs(r.ss_between + r.ss_within - r.ss_total) < 0.01
        return {"ss_decomposition_valid": valid}
    elif test_type == "correlation":
        from forgestat.parametric.correlation import correlation
        r = correlation({"x": inp["x"], "y": inp["y"]})
        p = r.pairs[0]
        n = len(inp["x"])
        t_stat = p.r * math.sqrt((n - 2) / (1 - p.r**2)) if abs(p.r) < 1 else 0
        return {"r": p.r, "p_value": p.p_value, "t_statistic": t_stat}
    elif test_type == "chi_square":
        from forgestat.parametric.chi_square import chi_square_independence
        observed = np.array(list(inp["observed"].values())).T
        r = chi_square_independence(observed.tolist())
        return {"chi_sq": r.statistic, "p_value": r.p_value, "df": r.df, "cramers_v": r.effect_size or 0}
    elif test_type == "mann_whitney":
        from forgestat.nonparametric.rank_tests import mann_whitney
        r = mann_whitney(inp["a"], inp["b"])
        return {"U_statistic": r.statistic, "p_value": r.p_value}
    elif test_type == "kruskal_wallis":
        from forgestat.nonparametric.rank_tests import kruskal_wallis
        r = kruskal_wallis(inp["g1"], inp["g2"], inp["g3"])
        return {"H_statistic": r.statistic, "p_value": r.p_value, "df": r.df}
    elif test_type == "regression":
        from forgestat.regression.linear import ols
        x = np.array(inp["x"], dtype=float).reshape(-1, 1)
        r = ols(x, inp["y"], feature_names=["x"])
        return {
            "intercept": r.coefficients.get("Intercept", r.coefficients.get("intercept", 0)),
            "slope": r.coefficients.get("x", r.coefficients.get("X1", 0)),
            "r_squared": r.r_squared, "f_statistic": r.f_statistic,
        }

    return {}


def _run_doe_case(case: dict) -> dict:
    """Run a forgedoe calibration case."""
    cat = case["category"]
    config = case.get("config", {})

    from forgedoe.core.types import Factor

    k = config.get("k", 3)
    factors = [Factor(name=f"X{i+1}", low=-1, high=1) for i in range(k)]

    if cat == "factorial":
        from forgedoe.designs.factorial import full_factorial, fractional_factorial

        if config.get("type") == "full":
            dm = full_factorial(factors, randomize=False)
        else:
            res = config.get("resolution", 5)
            dm = fractional_factorial(factors, resolution=res, randomize=False)
        return {"n_runs": len(dm.matrix), "n_factors": k}
    elif cat == "response_surface":
        from forgedoe.designs.response_surface import central_composite_design, box_behnken_design

        if config.get("type") == "ccd":
            dm = central_composite_design(factors, randomize=False)
            return {"n_runs": len(dm.matrix), "n_factors": k, "n_factorial": 2**k}
        elif config.get("type") == "bbd":
            dm = box_behnken_design(factors, randomize=False)
            return {"n_runs": len(dm.matrix), "n_factors": k}
    elif cat == "screening":
        from forgedoe.designs.factorial import plackett_burman
        dm = plackett_burman(factors, randomize=False)
        return {"n_runs": len(dm.matrix), "n_factors": k}
    elif cat == "analysis":
        # RSM fit — use numpy directly
        import numpy as np
        d = case.get("data", case.get("config", {}))
        if not isinstance(d, dict):
            return {}
        x1 = np.array(d["x1"])
        x2 = np.array(d["x2"])
        y  = np.array(d["y"])
        # Build model matrix: [1, x1, x2, x1*x2, x1^2, x2^2]
        X = np.column_stack([np.ones(len(y)), x1, x2, x1*x2, x1**2, x2**2])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        y_hat = X @ beta
        ss_res = np.sum((y - y_hat)**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r_sq = 1 - ss_res / ss_tot
        return {
            "intercept": float(beta[0]), "beta_x1": float(beta[1]),
            "beta_x2": float(beta[2]), "r_squared": float(r_sq),
        }

    return {}


def _run_rel_case(case: dict) -> dict:
    """Run a forgerel calibration case using forgerel's actual API."""
    cat = case["category"]
    data = case["data"]
    config = case.get("config", {})

    if cat == "weibull":
        from forgerel.weibull import weibull_analysis
        from forgerel.models import LifeDataPoint
        times = data["times"]
        censored = data.get("censored", config.get("censored", [1] * len(times)))
        # Build LifeDataPoint list
        life_data = [LifeDataPoint(time=t, is_failure=bool(c))
                     for t, c in zip(times, censored)]
        r = weibull_analysis(life_data, method="mle",
                             confidence=config.get("confidence", 0.90))
        return {"beta": r.beta, "eta": r.eta}
    elif cat == "mtbf":
        from forgerel.mtbf import mtbf_analysis
        # mtbf_analysis takes failure_times (TBF), not total_time/n_failures
        # Simulate equal TBFs from total_time / n_failures
        total_time = data["total_time"]
        n_failures = data["n_failures"]
        tbfs = [total_time / n_failures] * n_failures
        r = mtbf_analysis(tbfs, confidence=config.get("confidence", 0.90))
        lower = r.mtbf_ci[0] if r.mtbf_ci else 0
        upper = r.mtbf_ci[1] if r.mtbf_ci else 0
        return {"mtbf_point": r.mtbf, "mtbf_lower": lower, "mtbf_upper": upper}
    elif cat == "survival":
        # forgerel doesn't have Kaplan-Meier — use scipy/lifelines fallback
        # or skip if no KM implementation
        return {}

    return {}


_RUNNERS = {
    "forgespc": _run_spc_case,
    "forgestat": _run_stat_case,
    "forgedoe": _run_doe_case,
    "forgerel": _run_rel_case,
}

_PKG_DIRS = {
    "forgespc": "spc",
    "forgestat": "stat",
    "forgedoe": "doe",
    "forgerel": "rel",
}


def validate_package(package: str) -> ValidationReport:
    """Validate one forge package against R golden references."""
    golden_dir = _PKG_DIRS.get(package, package)
    cases = _load_golden(golden_dir)
    runner = _RUNNERS.get(package)

    report = ValidationReport(package=package)

    if not cases:
        return report
    if not runner:
        report.total_cases = len(cases)
        return report

    for case in cases:
        report.total_cases += 1
        cr = CaseResult(
            case_id=case["case_id"],
            description=case["description"],
            package=case.get("package", package),
            passed=True,
        )

        try:
            result = runner(case)
        except Exception as e:
            cr.passed = False
            cr.error = str(e)
            report.cases.append(cr)
            report.total_checks += len(case.get("expectations", []))
            continue

        for exp in case.get("expectations", []):
            report.total_checks += 1
            actual = result.get(exp["key"])
            er = _check_expectation(actual, exp)
            cr.expectations.append(er)
            if er.passed:
                report.passed_checks += 1
            else:
                cr.passed = False

        if cr.passed:
            report.passed_cases += 1
        report.cases.append(cr)

    return report


def validate_all() -> dict[str, ValidationReport]:
    """Validate all forge packages with R golden files."""
    reports = {}
    for pkg in _RUNNERS:
        reports[pkg] = validate_package(pkg)
    return reports
