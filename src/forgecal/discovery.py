"""Auto-discover calibration adapters from installed forge packages.

Scans installed packages for a `get_calibration_adapter()` function
in their calibration module. This is the plugin system — any package
that exposes the right interface gets discovered automatically.

Protocol:
    A package is discoverable if it has:
    1. A module named `<package>.calibration`
    2. A function `get_calibration_adapter()` in that module
    3. That function returns a CalibrationAdapter (or compatible dict)

No Django, no web framework. Uses importlib for discovery.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import CalibrationAdapter

logger = logging.getLogger("forgecal.discovery")

# Known forge packages to scan. Add new packages here.
KNOWN_PACKAGES = [
    "forgespc",
    "forgestats",
    "forgeeda",
    "forgeml",
    "forgebay",
    "forgeviz",
    "forgerel",
    "forgesim",
    "forgepbs",
    "forgedoe",
    "forgecausal",
    "forgeanytime",
    "forgeeco",
    "forgesia",
    "forgesiop",
]


def discover_adapters(
    packages: list[str] | None = None,
    include_unknown: bool = False,
) -> list[CalibrationAdapter]:
    """Discover calibration adapters from installed forge packages.

    Args:
        packages: Specific packages to scan. Defaults to KNOWN_PACKAGES.
        include_unknown: If True, scan ALL installed packages matching forge* pattern.

    Returns:
        List of CalibrationAdapter objects from discovered packages.
    """
    from .core import CalibrationAdapter

    scan_list = packages or KNOWN_PACKAGES
    adapters = []

    for pkg_name in scan_list:
        try:
            cal_module = importlib.import_module(f"{pkg_name}.calibration")
        except ImportError:
            continue  # Package not installed or has no calibration module

        get_adapter = getattr(cal_module, "get_calibration_adapter", None)
        if not callable(get_adapter):
            logger.debug("Package %s has calibration module but no get_calibration_adapter()", pkg_name)
            continue

        try:
            adapter = get_adapter()

            # Accept both CalibrationAdapter instances and dicts
            if isinstance(adapter, dict):
                adapter = CalibrationAdapter(
                    package=adapter.get("package", pkg_name),
                    version=adapter.get("version", "unknown"),
                    cases=adapter.get("cases", []),
                    runner=adapter.get("runner"),
                )

            if adapter.runner is None:
                logger.warning("Package %s adapter has no runner — skipping", pkg_name)
                continue

            adapters.append(adapter)
            logger.info(
                "Discovered %s v%s: %d calibration cases",
                adapter.package,
                adapter.version,
                len(adapter.cases),
            )

        except Exception as e:
            logger.warning("Failed to load adapter from %s: %s", pkg_name, e)

    return adapters
