"""Tests for forgecal core types and check engine."""

from forgecal import (
    CalibrationAdapter,
    CalibrationCase,
    Expectation,
    run_calibration,
)
from forgecal.check import check_expectation, extract_nested


# ── extract_nested ──


def test_extract_simple():
    assert extract_nested({"a": 1}, "a") == 1


def test_extract_nested():
    assert extract_nested({"statistics": {"p_value": 0.03}}, "statistics.p_value") == 0.03


def test_extract_deep():
    d = {"a": {"b": {"c": 42}}}
    assert extract_nested(d, "a.b.c") == 42


def test_extract_list_index():
    d = {"plots": [{"title": "Chart 1"}, {"title": "Chart 2"}]}
    assert extract_nested(d, "plots.0.title") == "Chart 1"
    assert extract_nested(d, "plots.1.title") == "Chart 2"


def test_extract_missing():
    assert extract_nested({"a": 1}, "b") is None
    assert extract_nested({"a": {"b": 1}}, "a.c") is None


# ── check_expectation ──


def test_abs_within_pass():
    result = {"statistics": {"p_value": 0.031}}
    exp = Expectation(key="statistics.p_value", expected=0.03, tolerance=0.01)
    check = check_expectation(result, exp)
    assert check.passed


def test_abs_within_fail():
    result = {"statistics": {"p_value": 0.15}}
    exp = Expectation(key="statistics.p_value", expected=0.03, tolerance=0.01)
    check = check_expectation(result, exp)
    assert not check.passed
    assert check.deviation > 0.1


def test_rel_within_pass():
    result = {"statistics": {"effect_size": 0.51}}
    exp = Expectation(key="statistics.effect_size", expected=0.50, tolerance=0.05, comparison="rel_within")
    check = check_expectation(result, exp)
    assert check.passed


def test_greater_than():
    result = {"statistics": {"f_value": 5.2}}
    exp = Expectation(key="statistics.f_value", expected=4.0, comparison="greater_than")
    check = check_expectation(result, exp)
    assert check.passed


def test_less_than():
    result = {"statistics": {"p_value": 0.01}}
    exp = Expectation(key="statistics.p_value", expected=0.05, comparison="less_than")
    check = check_expectation(result, exp)
    assert check.passed


def test_between():
    result = {"statistics": {"cpk": 1.45}}
    exp = Expectation(key="statistics.cpk", expected=[1.2, 1.8], comparison="between")
    check = check_expectation(result, exp)
    assert check.passed


def test_between_fail():
    result = {"statistics": {"cpk": 0.8}}
    exp = Expectation(key="statistics.cpk", expected=[1.2, 1.8], comparison="between")
    check = check_expectation(result, exp)
    assert not check.passed


def test_contains():
    result = {"summary": "The process is IN CONTROL with no alarms."}
    exp = Expectation(key="summary_contains", expected="IN CONTROL")
    check = check_expectation(result, exp)
    assert check.passed


def test_contains_fail():
    result = {"summary": "The process is OUT OF CONTROL."}
    exp = Expectation(key="summary_contains", expected="IN CONTROL")
    check = check_expectation(result, exp)
    assert not check.passed


def test_equals():
    result = {"statistics": {"n": 50}}
    exp = Expectation(key="statistics.n", expected=50, comparison="equals")
    check = check_expectation(result, exp)
    assert check.passed


def test_type_is():
    result = {"statistics": {"p_value": 0.03}}
    exp = Expectation(key="statistics.p_value", expected="float", comparison="type_is")
    check = check_expectation(result, exp)
    assert check.passed


def test_missing_key():
    result = {"statistics": {}}
    exp = Expectation(key="statistics.p_value", expected=0.03)
    check = check_expectation(result, exp)
    assert not check.passed
    assert "not found" in check.detail


def test_plot_count():
    result = {"plots": [{"data": []}, {"data": []}]}
    exp = Expectation(key="plot_count", expected=2, tolerance=0, comparison="abs_within")
    check = check_expectation(result, exp)
    assert check.passed


# ── run_calibration ──


def _mock_runner(case: CalibrationCase) -> dict:
    """Simple mock: return the case data as the 'result'."""
    return {
        "statistics": {"p_value": 0.023, "n": 100, "effect_size": 0.45},
        "summary": "The test is statistically significant.",
        "plots": [{"data": []}],
    }


def test_run_calibration_basic():
    cases = [
        CalibrationCase(
            case_id="TEST-001",
            package="test",
            category="basic",
            analysis_type="stats",
            analysis_id="ttest",
            config={},
            data={},
            expectations=[
                Expectation(key="statistics.p_value", expected=0.023, tolerance=0.001),
                Expectation(key="statistics.n", expected=100, comparison="equals"),
                Expectation(key="summary_contains", expected="significant"),
            ],
            description="Basic mock test",
        ),
    ]

    report = run_calibration(cases=cases, runner=_mock_runner)
    assert report.total_cases == 1
    assert report.passed_cases == 1
    assert report.pass_rate == 1.0
    assert report.is_calibrated


def test_run_calibration_with_failure():
    cases = [
        CalibrationCase(
            case_id="TEST-002",
            package="test",
            category="fail",
            analysis_type="stats",
            analysis_id="ttest",
            config={},
            data={},
            expectations=[
                Expectation(key="statistics.p_value", expected=0.5, tolerance=0.01),  # will fail
            ],
            description="Expected to fail",
        ),
    ]

    report = run_calibration(cases=cases, runner=_mock_runner)
    assert report.total_cases == 1
    assert report.failed_cases == 1
    assert not report.is_calibrated


def test_run_calibration_adapter_mode():
    adapter = CalibrationAdapter(
        package="mockpkg",
        version="1.0.0",
        cases=[
            CalibrationCase(
                case_id="MOCK-001",
                package="mockpkg",
                category="basic",
                analysis_type="test",
                analysis_id="mock",
                config={},
                data={},
                expectations=[
                    Expectation(key="statistics.p_value", expected=0.023, tolerance=0.01),
                ],
            ),
        ],
        runner=_mock_runner,
    )

    report = run_calibration(adapters=[adapter])
    assert report.total_cases == 1
    assert report.passed_cases == 1
    assert "mockpkg" in report.by_package
    assert report.by_package["mockpkg"]["pass_rate"] == 1.0


def test_run_calibration_error_isolation():
    def _failing_runner(case):
        raise ValueError("Analysis crashed")

    cases = [
        CalibrationCase(
            case_id="ERR-001",
            package="test",
            category="error",
            analysis_type="stats",
            analysis_id="crash",
            config={},
            data={},
            expectations=[Expectation(key="anything", expected=1)],
        ),
    ]

    report = run_calibration(cases=cases, runner=_failing_runner)
    assert report.total_cases == 1
    assert report.error_cases == 1
    assert report.results[0].error == "Analysis crashed"
