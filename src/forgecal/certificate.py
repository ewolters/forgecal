"""Calibration certificate generator.

Runs validation against R golden references, outputs structured JSON
suitable for rendering as an HTML certificate or storing in task_queue.

Tempora handler: 'forgecal.certificate.run_calibration_certificate'
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .validate import validate_all, validate_package, ValidationReport


def _json_safe(obj):
    """Recursively convert numpy/non-standard types to JSON-safe Python types."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float, str, type(None))):
        return obj
    # numpy scalars, etc.
    try:
        if hasattr(obj, 'item'):
            return obj.item()
    except Exception:
        pass
    return str(obj)


def _report_to_dict(report: ValidationReport) -> dict:
    """Convert a ValidationReport to a serializable dict."""
    cases = []
    for c in report.cases:
        expectations = []
        for e in c.expectations:
            expectations.append({
                "key": e.key,
                "expected": e.expected,
                "actual": e.actual,
                "tolerance": e.tolerance,
                "passed": e.passed,
                "message": e.message,
            })
        cases.append({
            "case_id": c.case_id,
            "description": c.description,
            "passed": c.passed,
            "error": c.error,
            "expectations": expectations,
        })

    return {
        "package": report.package,
        "total_cases": report.total_cases,
        "passed_cases": report.passed_cases,
        "total_checks": report.total_checks,
        "passed_checks": report.passed_checks,
        "pass_rate": round(report.pass_rate, 4),
        "is_calibrated": report.is_calibrated,
        "cases": cases,
    }


def generate_certificate(packages: list[str] | None = None) -> dict:
    """Generate a full calibration certificate.

    Args:
        packages: Specific packages to validate. None = all.

    Returns:
        Structured dict with certificate metadata + per-package results.
    """
    now = datetime.now(timezone.utc)

    if packages:
        reports = {pkg: validate_package(pkg) for pkg in packages}
    else:
        reports = validate_all()

    total_checks = sum(r.total_checks for r in reports.values())
    passed_checks = sum(r.passed_checks for r in reports.values())
    all_calibrated = all(r.is_calibrated for r in reports.values() if r.total_checks > 0)

    package_results = {}
    for pkg, report in reports.items():
        package_results[pkg] = _report_to_dict(report)

    certificate = {
        "certificate_id": f"CAL-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}",
        "issued_at": now.isoformat(),
        "issued_by": "ForgeCal R Calibration Service",
        "authority": "R Statistical Computing Environment",
        "r_packages": {
            "forgespc": "qcc",
            "forgestat": "base R (t.test, aov, cor.test, chisq.test, lm)",
            "forgedoe": "FrF2, rsm, DoE.base",
            "forgerel": "WeibullR, survival",
        },
        "verdict": "CALIBRATED" if all_calibrated else "NOT CALIBRATED",
        "summary": {
            "total_packages": len(reports),
            "calibrated_packages": sum(1 for r in reports.values() if r.is_calibrated),
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "pass_rate": round(passed_checks / total_checks, 4) if total_checks else 0,
        },
        "packages": package_results,
    }

    return certificate


def run_calibration_certificate(payload: dict | None = None) -> dict:
    """Tempora task handler. Generates certificate and returns it.

    Register in task_schedule as:
        task_name: 'forgecal.certificate.run_calibration_certificate'
        cron: '0 6 * * 1'  (weekly Monday 6am)
    """
    payload = payload or {}
    packages = payload.get("packages")
    cert = _json_safe(generate_certificate(packages=packages))

    # Write to golden dir as latest certificate
    out = Path(__file__).parent.parent.parent / "golden" / "latest_certificate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cert, indent=2, default=str))

    return cert
