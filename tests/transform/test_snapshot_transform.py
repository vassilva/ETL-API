"""
Offline Data Quality on the versioned snapshot (tests/fixtures/snapshot).

Deterministic: the committed raw snapshot is transformed by the production
code and checked against the independent ETL contract (support.etl_contract),
never against the transform implementation itself.

- mapping contract: every copied column, every record, key sets both ways
- transformation rules: each derived column, identified by its business rule
- golden snapshot: the committed processed snapshot is still what the code
  produces (change detector; the contract tests provide correctness)
- referential integrity inside the processed snapshot
"""

import pytest

from support.etl_contract import (
    ENTITIES,
    MAPPINGS,
    SENSITIVE_COLUMNS,
    exact_value,
    expected_rows,
    key_of,
    processed_rows,
)
from support.reconciliation import assert_reconciled, reconcile, sample
from transform.carts import transform_carts_data
from transform.products import transform_products_data
from transform.users import transform_users_data


pytestmark = [pytest.mark.transform]


DERIVED_RULES = [
    f"{entity}.{m.column}"
    for entity in ("users", "products", "carts")
    for m in MAPPINGS[entity]
    if m.derived
]


@pytest.fixture(scope="module")
def transformed(snapshot_raw):
    """Production transform output for the committed raw snapshot."""
    return {
        "users": transform_users_data(snapshot_raw["users"]["users"]),
        "products": transform_products_data(snapshot_raw["products"]["products"]),
        "carts": transform_carts_data(snapshot_raw["carts"]["carts"]),
    }


def _reconcile_transform(entity, snapshot_raw, transformed, columns, boundary):
    rules = {m.column: m.rule for m in MAPPINGS[entity]}

    problems = reconcile(
        expected_rows(entity, snapshot_raw, columns=columns),
        processed_rows(entity, transformed),
        key_fn=lambda row: key_of(entity, row),
        columns=columns,
        normalize_expected=lambda column, value: exact_value(entity, column, value),
        normalize_actual=lambda column, value: exact_value(entity, column, value),
        rules=rules,
        sensitive=SENSITIVE_COLUMNS.get(entity, ()),
    )

    assert_reconciled(boundary, entity, problems)


# Validate every copied column of every record (plus key sets, duplicates and
# item order inside carts) against the declarative mapping
@pytest.mark.parametrize("entity", ENTITIES)
def test_snapshot_mapping_contract(snapshot_raw, transformed, entity):
    columns = [m.column for m in MAPPINGS[entity] if not m.derived]

    _reconcile_transform(entity, snapshot_raw, transformed, columns, "RAW -> Processed | snapshot mapping")


# Validate each derived column against its explicit business rule
@pytest.mark.parametrize("rule_id", DERIVED_RULES)
def test_snapshot_transformation_rule(snapshot_raw, transformed, rule_id):
    entity, column = rule_id.split(".")

    _reconcile_transform(entity, snapshot_raw, transformed, [column], f"RAW -> Processed | rule {rule_id}")


# Validate that the committed processed snapshot is still what the code produces
@pytest.mark.parametrize("entity", ENTITIES)
def test_processed_snapshot_is_current_transformation(snapshot_processed, transformed, entity):
    committed = processed_rows(entity, snapshot_processed)
    produced = processed_rows(entity, transformed)
    columns = sorted({column for row in committed + produced for column in row})

    problems = reconcile(
        committed,
        produced,
        key_fn=lambda row: key_of(entity, row),
        columns=columns,
        sensitive=SENSITIVE_COLUMNS.get(entity, ()),
    )

    assert_reconciled("Committed snapshot -> current transformation", entity, problems)


# Validate referential integrity inside the processed snapshot
@pytest.mark.parametrize(
    "child, fk, parent, parent_key",
    [
        ("carts", "user_id", "users", "user_id"),
        ("cart_items", "product_id", "products", "product_id"),
    ],
    ids=["carts.user_id -> users", "cart_items.product_id -> products"]
)
def test_snapshot_referential_integrity(snapshot_processed, child, fk, parent, parent_key):
    children = processed_rows(child, snapshot_processed)
    parent_keys = {row[parent_key] for row in processed_rows(parent, snapshot_processed)}

    assert children and parent_keys, f"{child} or {parent} snapshot is empty"

    orphans = [key_of(child, row) for row in children if row[fk] not in parent_keys]

    assert not orphans, (
        f"[Processed snapshot] {child}.{fk} -> {parent}: "
        f"orphans: {len(orphans)} | sample keys: {sample(orphans)}"
    )
