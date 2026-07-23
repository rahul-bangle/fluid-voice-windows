"""
FluidVoice Windows — Standalone Test Runner & Coverage Summary Generator
-----------------------------------------------------------------------
Discovers and executes all Pytest suites in `tests/`:
- Categorizes test execution and results into Tiers 1-4.
- Formats a clean ASCII summary table printing total passed, total failed, pass rate, and coverage per tier.
- Exits with status code 0 on success, or non-zero on failure.
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, List

import pytest

# Ensure QT operates headlessly during standalone test runs
os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TierCoverageCollectorPlugin:
    """
    Pytest plugin tracking test execution metrics across Tier 1 to Tier 4 test suites.
    """

    def __init__(self):
        self._item_tiers: Dict[str, str] = {}
        self.stats: Dict[str, Dict[str, int]] = {
            "Tier 1": {"passed": 0, "failed": 0, "skipped": 0},
            "Tier 2": {"passed": 0, "failed": 0, "skipped": 0},
            "Tier 3": {"passed": 0, "failed": 0, "skipped": 0},
            "Tier 4": {"passed": 0, "failed": 0, "skipped": 0},
        }
        self.test_details: List[Dict[str, str]] = []
        self.start_time: float = time.time()
        self.duration: float = 0.0

    def _determine_tier_from_nodeid(self, nodeid: str) -> str:
        """Classifies a test nodeid into Tier 1, 2, 3, or 4 based on path and test function name."""
        nodeid_norm = nodeid.replace("\\", "/")
        node_name = nodeid_norm.split("::")[-1].lower() if "::" in nodeid_norm else nodeid_norm.lower()

        if "/e2e/" in nodeid_norm or nodeid_norm.startswith("tests/e2e/"):
            return "Tier 4"
        elif "/integration/" in nodeid_norm or nodeid_norm.startswith("tests/integration/"):
            return "Tier 3"
        elif "/unit/" in nodeid_norm or nodeid_norm.startswith("tests/unit/"):
            boundary_keywords = (
                "boundary", "corner", "error", "fallback", "invalid",
                "fail", "null", "empty", "exception", "limit", "cap", "overflow", "timeout", "disfluenc"
            )
            if any(kw in node_name for kw in boundary_keywords):
                return "Tier 2"
            return "Tier 1"
        else:
            return "Tier 1"

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Hook called after each test phase (setup, call, teardown)."""
        if report.when == "call":
            tier = self._determine_tier_from_nodeid(report.nodeid)

            if report.passed:
                self.stats[tier]["passed"] += 1
            elif report.failed:
                self.stats[tier]["failed"] += 1
            self.test_details.append({
                "nodeid": report.nodeid,
                "tier": tier,
                "outcome": report.outcome,
                "duration": f"{report.duration:.3f}s",
            })


def format_summary_table(plugin: TierCoverageCollectorPlugin) -> str:
    """Formats a clean ASCII table of test coverage per tier."""
    stats = plugin.stats

    tier_descriptions = {
        "Tier 1": "Unit Tests (Happy Path Feature Coverage)",
        "Tier 2": "Unit Tests (Boundary & Corner Cases)",
        "Tier 3": "Integration Tests (Cross-Subsystem)",
        "Tier 4": "Real-World Application Workload E2E",
    }

    lines = []
    lines.append("=" * 86)
    lines.append("                      FLUIDVOICE WINDOWS TEST SUITE RESULTS")
    lines.append("=" * 86)
    lines.append(f"{'Tier':<8} {'Description':<44} {'Passed':>8} {'Failed':>8} {'Total':>8} {'Pass Rate':>10}")
    lines.append("-" * 86)

    total_passed = 0
    total_failed = 0
    total_skipped = 0
    total_tests = 0

    for tier_id in ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]:
        t_data = stats[tier_id]
        passed = t_data["passed"]
        failed = t_data["failed"]
        skipped = t_data["skipped"]
        t_total = passed + failed + skipped

        total_passed += passed
        total_failed += failed
        total_skipped += skipped
        total_tests += t_total

        pass_rate_str = f"{(passed / t_total * 100):.1f}%" if t_total > 0 else "N/A"
        desc = tier_descriptions[tier_id]
        lines.append(f"{tier_id:<8} {desc:<44} {passed:>8} {failed:>8} {t_total:>8} {pass_rate_str:>10}")

    lines.append("-" * 86)
    overall_rate_str = f"{(total_passed / total_tests * 100):.1f}%" if total_tests > 0 else "0.0%"
    lines.append(f"{'TOTAL':<8} {'SUMMARY (ALL TIERS 1-4)':<44} {total_passed:>8} {total_failed:>8} {total_tests:>8} {overall_rate_str:>10}")
    lines.append("=" * 86)

    status_str = "SUCCESS — All test suites passed cleanly!" if total_failed == 0 else f"FAILURE — {total_failed} test(s) failed."
    lines.append(f" STATUS: {status_str}")
    lines.append(f" EXECUTION TIME: {plugin.duration:.2f} seconds")
    lines.append("=" * 86)

    return "\n".join(lines)


def run_standalone_tests(test_dir: Path | None = None, extra_pytest_args: List[str] | None = None) -> int:
    """
    Executes pytest on target directory, prints summary table, and returns exit code (0 on success).
    """
    root_dir = test_dir or (Path(__file__).parent.parent)
    tests_path = root_dir / "tests"

    plugin = TierCoverageCollectorPlugin()

    pytest_args = [
        str(tests_path),
        "-v",
        "--tb=short",
        "-q",
    ] + (extra_pytest_args or [])

    plugin.start_time = time.time()
    exit_code = pytest.main(pytest_args, plugins=[plugin])
    plugin.duration = time.time() - plugin.start_time

    # Print summary table
    summary_output = format_summary_table(plugin)
    print("\n" + summary_output + "\n")

    # If all tests passed, return 0
    total_failed = sum(tier["failed"] for tier in plugin.stats.values())
    if total_failed == 0 and exit_code in (0, 5):  # 5 = no tests collected if empty
        return 0
    return 1


if __name__ == "__main__":
    exit_code = run_standalone_tests(extra_pytest_args=sys.argv[1:])
    sys.exit(exit_code)
