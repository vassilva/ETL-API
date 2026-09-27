"""
Assertion helpers that never expose compared values.

Use these for fields that may hold personal data (names, emails, phones,
addresses, companies). The failure message identifies the record by a safe
identifier and the field name only, so values never reach console output,
CI logs or JUnit reports.
"""


def assert_field_matches(actual, expected, *, entity, record_id, field):
    __tracebackhide__ = True

    if actual != expected:
        raise AssertionError(
            f"{entity} {record_id}: field '{field}' does not match "
            f"(values hidden)"
        )
