"""
Record-level reconciliation with safe, boundary-aware diagnostics.

reconcile() never collapses duplicates silently, never passes on an empty
expected side, compares key sets in both directions before comparing
fields, and hides the values of sensitive (personal-data) columns.
"""

import pytest


SAMPLE_SIZE = 10
MAX_VALUE_LENGTH = 80


class _Missing:
    def __repr__(self):
        return "<missing>"


_MISSING = _Missing()


def sample(keys):
    return sorted(keys, key=repr)[:SAMPLE_SIZE]


def index_unique(rows, key_fn):
    """Index rows by key; duplicates are returned, never overwritten."""
    index, duplicates = {}, []

    for row in rows:
        key = key_fn(row)

        if key in index:
            duplicates.append(key)
        else:
            index[key] = row

    return index, duplicates


def _normalized(normalize, column, row):
    """A column absent from the row is reported as <missing>, never normalized."""
    if column not in row:
        return _MISSING

    return normalize(column, row[column])


def _shown(value):
    text = repr(value)

    return text if len(text) <= MAX_VALUE_LENGTH else text[:MAX_VALUE_LENGTH] + "..."


def reconcile(
    expected_rows,
    actual_rows,
    *,
    key_fn,
    columns,
    normalize_expected=lambda column, value: value,
    normalize_actual=lambda column, value: value,
    rules=None,
    sensitive=(),
):
    """
    Compare two record sets. Returns a list of problem lines (empty = OK).

    columns: fields compared on every common key
    rules: {column: rule description} used in diagnostics (default "exact")
    """
    problems = []

    if not expected_rows:
        problems.append("expected side is empty: nothing to reconcile")

    expected, expected_duplicates = index_unique(expected_rows, key_fn)
    actual, actual_duplicates = index_unique(actual_rows, key_fn)

    if expected_duplicates:
        problems.append(
            f"duplicate expected keys: {len(expected_duplicates)} | "
            f"sample keys: {sample(expected_duplicates)}"
        )

    if actual_duplicates:
        problems.append(
            f"duplicate actual keys: {len(actual_duplicates)} | "
            f"sample keys: {sample(actual_duplicates)}"
        )

    missing = expected.keys() - actual.keys()
    unexpected = actual.keys() - expected.keys()

    if missing:
        problems.append(f"missing keys: {len(missing)} | sample keys: {sample(missing)}")

    if unexpected:
        problems.append(f"unexpected keys: {len(unexpected)} | sample keys: {sample(unexpected)}")

    common = sorted(expected.keys() & actual.keys(), key=repr)

    for column in columns:
        mismatched = []

        for key in common:
            expected_value = _normalized(normalize_expected, column, expected[key])
            actual_value = _normalized(normalize_actual, column, actual[key])

            if expected_value != actual_value:
                mismatched.append((key, expected_value, actual_value))

        if mismatched:
            _, expected_value, actual_value = mismatched[0]
            hidden = column in sensitive
            rule = (rules or {}).get(column, "exact")

            # expected/actual shown for the first sample key
            problems.append(
                f"field: {column} | rule: {rule} | mismatches: {len(mismatched)} | "
                f"sample keys: {[m[0] for m in mismatched[:SAMPLE_SIZE]]} | "
                f"expected: {'(hidden)' if hidden else _shown(expected_value)} | "
                f"actual: {'(hidden)' if hidden else _shown(actual_value)}"
            )

    return problems


def assert_reconciled(boundary, entity, problems):
    """Fail with a readable report; values were already masked where needed."""
    __tracebackhide__ = True

    if problems:
        pytest.fail(
            f"[{boundary}] entity: {entity}\n  " + "\n  ".join(problems),
            pytrace=False
        )
