"""
Reconciliation across the ETL boundaries of the current run.

    Source (live API) -> RAW -> Processed -> Database

Oracles (never the production transform/load code):
- Source -> RAW          the live API payload (Extract must preserve it)
- RAW -> Processed       the declarative ETL contract applied to RAW
- Processed -> Database  the processed files (correct oracle for the Load
                         boundary only; not a source-to-target check)
- Source -> Database     the declarative ETL contract applied to the live API
                         (independent end-to-end check)

Completeness and Processed -> Database are smoke (the PR critical path); the
rest runs in the pre-merge regression.
"""

from decimal import Decimal

import pytest

from support.db_helpers import fetch_records, scalar
from support.etl_contract import (
    BUSINESS_KEYS,
    ENTITIES,
    MAPPINGS,
    SENSITIVE_COLUMNS,
    SOURCE_RESOURCES,
    VOLATILE_SOURCE_FIELDS,
    business_columns,
    exact_value,
    expected_rows,
    key_of,
    numeric_scale,
    processed_rows,
    source_key,
    source_records,
    stored_value,
)
from support.reconciliation import assert_reconciled, index_unique, reconcile, sample


def _database_rows(connection, entity):
    return fetch_records(connection, f"SELECT {', '.join(business_columns(entity))} FROM {entity}")


def _non_key_columns(entity):
    return [c for c in business_columns(entity) if c not in BUSINESS_KEYS[entity]]


def _rules(entity, default="exact"):
    rules = {m.column: m.rule for m in MAPPINGS[entity]}

    for column in business_columns(entity):
        scale = numeric_scale(entity, column)

        if scale is not None:
            rules[column] = f"{rules.get(column, default)}; stored at NUMERIC scale {scale} (schema)"

    return rules


# Completeness (smoke)

def _key_problems(keys, reference):
    index, duplicates = index_unique(keys, lambda key: key)
    problems = []

    if duplicates:
        problems.append(f"duplicate keys: {len(duplicates)} sample {sample(duplicates)}")

    if missing := reference - index.keys():
        problems.append(f"missing keys: {len(missing)} sample {sample(missing)}")

    if unexpected := index.keys() - reference:
        problems.append(f"unexpected keys: {len(unexpected)} sample {sample(unexpected)}")

    return problems


# Validate record counts and key sets at every boundary against the live
# source, reporting the first boundary where they diverge
@pytest.mark.smoke
@pytest.mark.live_api
@pytest.mark.database
@pytest.mark.artifacts
@pytest.mark.parametrize("entity", ENTITIES)
def test_completeness(source_payloads, runtime_raw, runtime_processed, db_connection, entity):
    source_keys = [source_key(entity, r) for r in source_records(entity, source_payloads)]
    reference = set(source_keys)

    key_columns = ", ".join(BUSINESS_KEYS[entity])
    boundaries = {
        "Source": source_keys,
        "RAW": [source_key(entity, r) for r in source_records(entity, runtime_raw)],
        "Processed": [key_of(entity, row) for row in processed_rows(entity, runtime_processed)],
        "Database": [
            key_of(entity, row)
            for row in fetch_records(db_connection, f"SELECT {key_columns} FROM {entity}")
        ],
    }

    counts = " | ".join(f"{name}: {len(keys)}" for name, keys in boundaries.items())
    report = [f"counts: {counts}"]
    first_divergent = None

    if not source_keys:
        first_divergent = "Source"
        report.append("Source: empty (nothing to validate)")

    for name, keys in boundaries.items():
        problems = _key_problems(keys, reference)

        if problems:
            first_divergent = first_divergent or name
            report.append(f"{name}: " + "; ".join(problems))

    assert first_divergent is None, (
        f"[Completeness] entity: {entity} | first divergent boundary: {first_divergent}\n  "
        + "\n  ".join(report)
    )


# Processed -> Database (smoke): Load boundary

# Validate every business column of every row loaded, with key sets compared
# in both directions (missing, unexpected and duplicate keys)
@pytest.mark.smoke
@pytest.mark.load
@pytest.mark.database
@pytest.mark.artifacts
@pytest.mark.parametrize("entity", ENTITIES)
def test_processed_to_database(runtime_processed, db_connection, entity):
    problems = reconcile(
        processed_rows(entity, runtime_processed),
        _database_rows(db_connection, entity),
        key_fn=lambda row: key_of(entity, row),
        columns=_non_key_columns(entity),
        normalize_expected=lambda column, value: stored_value(entity, column, value),
        rules={c: f"exact; stored at NUMERIC scale {numeric_scale(entity, c)} (schema)"
               for c in business_columns(entity) if numeric_scale(entity, c) is not None},
        sensitive=SENSITIVE_COLUMNS.get(entity, ()),
    )

    assert_reconciled("Processed -> Database", entity, problems)


# Source -> RAW (regression): Extract boundary

def _flatten(value, prefix=""):
    """{path: leaf value}; list items get their index, e.g. reviews[0].rating."""
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = ((f"[{index}]", item) for index, item in enumerate(value))
    else:
        return {prefix: value}

    flat = {}

    for name, item in items:
        path = f"{prefix}{name}" if name.startswith("[") else (f"{prefix}.{name}" if prefix else name)
        flat.update(_flatten(item, path))

    return flat


# Validate that Extract preserved every source field of every record
# (only the API's own volatile metadata is excluded)
@pytest.mark.extract
@pytest.mark.live_api
@pytest.mark.artifacts
@pytest.mark.parametrize("resource", SOURCE_RESOURCES)
def test_source_to_raw(source_payloads, runtime_raw, resource):
    volatile = VOLATILE_SOURCE_FIELDS.get(resource, ())

    def flat_records(payload):
        return [
            {path: v for path, v in _flatten(record).items() if path not in volatile}
            for record in payload[resource]
        ]

    expected = flat_records(source_payloads[resource])
    actual = flat_records(runtime_raw[resource])
    paths = sorted({path for record in expected + actual for path in record})

    problems = reconcile(
        expected,
        actual,
        key_fn=lambda record: record.get("id"),
        columns=[p for p in paths if p != "id"],
        sensitive=paths if resource == "users" else (),
    )

    if runtime_raw[resource]["total"] != source_payloads[resource]["total"]:
        problems.append(
            f"payload total: expected {source_payloads[resource]['total']}, "
            f"actual {runtime_raw[resource]['total']}"
        )

    assert_reconciled("Source -> RAW", resource, problems)


# RAW -> Processed (regression): Transform boundary

# Validate the processed output of this run against the ETL contract applied
# to the RAW input of this run (independent of the transform code)
@pytest.mark.transform
@pytest.mark.artifacts
@pytest.mark.parametrize("entity", ENTITIES)
def test_raw_to_processed(runtime_raw, runtime_processed, entity):
    problems = reconcile(
        expected_rows(entity, runtime_raw),
        processed_rows(entity, runtime_processed),
        key_fn=lambda row: key_of(entity, row),
        columns=_non_key_columns(entity),
        normalize_expected=lambda column, value: exact_value(entity, column, value),
        normalize_actual=lambda column, value: exact_value(entity, column, value),
        rules={m.column: m.rule for m in MAPPINGS[entity]},
        sensitive=SENSITIVE_COLUMNS.get(entity, ()),
    )

    assert_reconciled("RAW -> Processed", entity, problems)


# Source -> Database (regression): independent end-to-end check

# Validate every business column of the target against the live source via
# the declarative contract (copies and business rules restated independently)
@pytest.mark.live_api
@pytest.mark.database
@pytest.mark.parametrize("entity", ENTITIES)
def test_source_to_database(source_payloads, db_connection, entity):
    problems = reconcile(
        expected_rows(entity, source_payloads),
        _database_rows(db_connection, entity),
        key_fn=lambda row: key_of(entity, row),
        columns=_non_key_columns(entity),
        normalize_expected=lambda column, value: stored_value(entity, column, value),
        rules=_rules(entity),
        sensitive=SENSITIVE_COLUMNS.get(entity, ()),
    )

    assert_reconciled("Source -> Database", entity, problems)


# Control totals (regression)

# (measure, entity, source field, target column). Each total is computed from
# its own dataset in this run, per record at the target's stored precision;
# nothing is hardcoded. A control total complements, never replaces, the
# record-level checks above: swapping values between two records keeps it
# green while the record-level reconciliation fails.
MEASURES = [
    ("products.stock", "products", "stock", "stock"),
    ("carts.total", "carts", "total", "total"),
]


@pytest.mark.live_api
@pytest.mark.database
@pytest.mark.artifacts
@pytest.mark.parametrize("measure, entity, source_field, column", MEASURES, ids=[m[0] for m in MEASURES])
def test_measure_control_total(
    source_payloads, runtime_raw, runtime_processed, db_connection, measure, entity, source_field, column
):
    def total(values):
        return sum((stored_value(entity, column, v) for v in values), Decimal(0))

    source = source_records(entity, source_payloads)

    assert source, f"[Control total] {measure}: the source is empty"

    totals = {
        "Source": total(r[source_field] for r in source),
        "RAW": total(r[source_field] for r in source_records(entity, runtime_raw)),
        "Processed": total(row[column] for row in processed_rows(entity, runtime_processed)),
        "Database": Decimal(scalar(db_connection, f"SELECT COALESCE(SUM({column}), 0) FROM {entity}")),
    }

    divergent = next(
        (name for name, value in totals.items() if value != totals["Source"]), None
    )

    assert divergent is None, (
        f"{measure} control total failed | "
        + " | ".join(f"{name}: {value}" for name, value in totals.items())
        + f" | first divergent boundary: {divergent}"
    )


# Business-data drift (regression)

# Validate that the data processed in this run equals the reviewed, committed
# snapshot the offline tests run against. A real upstream change fails here
# (reporting only record ids) until the snapshot is reviewed and refreshed.
@pytest.mark.artifacts
@pytest.mark.parametrize("entity", ENTITIES)
def test_business_data_drift(runtime_processed, snapshot_processed, entity):
    committed = processed_rows(entity, snapshot_processed)
    current = processed_rows(entity, runtime_processed)
    columns = sorted({c for row in committed + current for c in row} - set(BUSINESS_KEYS[entity]))

    problems = reconcile(
        committed,
        current,
        key_fn=lambda row: key_of(entity, row),
        columns=columns,
        sensitive=SENSITIVE_COLUMNS.get(entity, ()),
    )

    assert_reconciled("Committed snapshot -> current Processed (drift)", entity, problems)
