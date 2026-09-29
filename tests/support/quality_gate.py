"""
Required Quality Gate: fail-closed verification of one Jenkins profile.

The gate passes only when ALL of the following hold for the profile
(support/ci_profiles.py):

- every required stage completed successfully (stage evidence from Jenkins;
  a stage that was skipped or failed is missing from the evidence)
- every required JUnit report exists, is readable and belongs to its suite
- every suite contains EXACTLY the pinned test functions with the pinned
  number of cases: a missing, extra or moved test (e.g. a marker removed or
  added by accident) fails, and so does zero tests
- every test case passed: any failure, error or skip fails (xfail is
  reported as skipped, and xfail_strict turns an unexpected pass into a
  failure)

Only suite/function names and counts are printed, never test output.
Absence of evidence is never treated as success.

Run from the project root with tests on the path (Windows: set PYTHONPATH=tests):

    python -m support.quality_gate --profile pr --reports reports --completed-stages "Ruff,PR Offline,..."
"""

import argparse
import sys
import xml.etree.ElementTree as ElementTree
from collections import Counter
from pathlib import Path

from support.ci_profiles import PROFILES, expected_count


def test_function(case):
    """'tests.api.test_client' + 'test_x[a]' -> 'tests/api/test_client.py::test_x'."""
    module = case.get("classname", "").replace(".", "/") + ".py"

    return f"{module}::{case.get('name', '').split('[')[0]}"


def outcome(case):
    for status in ("failure", "error", "skipped"):
        if case.find(status) is not None:
            return status

    return "passed"


def check_suite(path, suite, expected):
    """(passed cases, problems) for one required suite."""
    if not path.exists():
        return 0, ["missing report: the suite never ran"]

    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as error:
        return 0, [f"unreadable report ({type(error).__name__})"]

    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")

    if not suites:
        return 0, ["the report contains no test suite"]

    problems = []
    names = sorted({element.get("name", "") for element in suites})

    if names != [suite]:
        problems.append(f"report belongs to suite(s) {names}")

    cases = [case for element in suites for case in element.iter("testcase")]

    if not cases:
        problems.append("zero tests executed")

    outcomes = Counter(outcome(case) for case in cases)

    for status in ("failure", "error", "skipped"):
        if outcomes[status]:
            problems.append(f"{outcomes[status]} {status}")

    actual = Counter(test_function(case) for case in cases)

    if missing := sorted(set(expected) - set(actual)):
        problems.append(f"missing tests: {missing}")

    if unexpected := sorted(set(actual) - set(expected)):
        problems.append(f"unexpected tests: {unexpected}")

    if wrong := sorted(f"{fn}: {actual[fn]} of {expected[fn]}" for fn in set(expected) & set(actual) if actual[fn] != expected[fn]):
        problems.append(f"wrong case counts: {wrong}")

    return outcomes["passed"], problems


def run(profile, reports, completed_stages):
    if profile not in PROFILES:
        print(f"Quality Gate FAILED: unknown profile '{profile}' (known: {sorted(PROFILES)})")
        return 1

    spec = PROFILES[profile]
    failed = []

    print(f"REQUIRED QUALITY GATE - profile: {profile}")

    completed = {stage.strip() for stage in completed_stages.split(",") if stage.strip()}
    missing_stages = [stage for stage in spec["stages"] if stage not in completed]

    for stage in spec["stages"]:
        print(f"  stage  {stage:<32} {'COMPLETED' if stage in completed else 'FAIL: not completed'}")

    if missing_stages:
        failed.append(f"stages not completed: {missing_stages}")

    passed_total = 0

    for suite, expected in spec["suites"].items():
        passed, problems = check_suite(Path(reports) / f"{suite}.xml", suite, expected)
        passed_total += passed
        verdict = "PASS" if not problems else "FAIL: " + "; ".join(problems)
        print(f"  suite  {suite:<32} expected {sum(expected.values()):>3}  passed {passed:>3}  {verdict}")

        if problems:
            failed.append(suite)

    total = expected_count(profile)
    print(f"  total  expected {total}, passed {passed_total}")

    if passed_total != total:
        failed.append(f"passed {passed_total} of {total} expected tests")

    if failed:
        print(f"Quality Gate FAILED ({profile}): {failed}")
        return 1

    print(f"Quality Gate PASSED ({profile}): {len(spec['stages'])} stages, {total} tests")
    return 0


def main(arguments=None):
    parser = argparse.ArgumentParser(description="Fail-closed Required Quality Gate")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--reports", default="reports")
    parser.add_argument("--completed-stages", default="")

    try:
        args = parser.parse_args(arguments)
    except SystemExit:
        return 2

    return run(args.profile, args.reports, args.completed_stages)


if __name__ == "__main__":
    sys.exit(main())
