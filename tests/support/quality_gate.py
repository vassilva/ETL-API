"""
Required Quality Gate: verifies the JUnit reports of the required suites.

A gate passes only when every required suite
- produced its report (a stage that never ran leaves no report),
- is the suite it claims to be (JUnit testsuite name),
- collected at least one test,
- has no failures, errors or skipped tests: every required test must really
  execute, a skipped test proves nothing (e.g. e2e without --run-e2e).

Only counts and suite names are printed, never test output.

Run from the project root with tests on the path (Windows: set PYTHONPATH=tests):

    python -m support.quality_gate <reports dir> <suite> [<suite> ...]
"""

import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path


COUNTERS = ("tests", "failures", "errors", "skipped")


def check_suite(path, suite):
    """(counts or None, problems) for one required suite report."""
    if not path.exists():
        return None, ["missing report: the suite never ran"]

    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as error:
        return None, [f"unreadable report ({type(error).__name__})"]

    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")

    if not suites:
        return None, ["the report contains no test suite"]

    problems = []
    names = sorted({element.get("name", "") for element in suites})

    if names != [suite]:
        problems.append(f"report belongs to suite(s) {names}")

    counts = {
        counter: sum(int(element.get(counter, 0)) for element in suites)
        for counter in COUNTERS
    }

    if counts["tests"] == 0:
        problems.append("zero tests collected")

    for counter in ("failures", "errors", "skipped"):
        if counts[counter]:
            problems.append(f"{counts[counter]} {counter}")

    return counts, problems


def main(arguments):
    if len(arguments) < 2:
        print("usage: python -m support.quality_gate <reports dir> <suite> [<suite> ...]")
        return 2

    reports_dir, suites = Path(arguments[0]), arguments[1:]
    failed = []

    print("REQUIRED QUALITY GATE")
    print(f"{'suite':<24} {'tests':>6} {'failed':>7} {'errors':>7} {'skipped':>8}  verdict")

    for suite in suites:
        counts, problems = check_suite(reports_dir / f"{suite}.xml", suite)

        if counts:
            numbers = (
                f"{counts['tests']:>6} {counts['failures']:>7} "
                f"{counts['errors']:>7} {counts['skipped']:>8}"
            )
        else:
            numbers = f"{'-':>6} {'-':>7} {'-':>7} {'-':>8}"

        verdict = "FAIL: " + "; ".join(problems) if problems else "PASS"
        print(f"{suite:<24} {numbers}  {verdict}")

        if problems:
            failed.append(suite)

    if failed:
        print(f"Quality Gate FAILED: {len(failed)} of {len(suites)} required suites: {failed}")
        return 1

    print(f"Quality Gate PASSED: {len(suites)} required suites complete")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
