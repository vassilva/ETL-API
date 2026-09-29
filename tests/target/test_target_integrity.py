"""
Target integrity after the Load.

Load freshness is PR Regression (merge-blocking: without it every database
check can pass on old rows). Uniqueness, referential integrity and
mandatory fields mostly monitor upstream data (code-induced defects are
caught by Source -> Database and completeness) and run in the local Full
Regression.

Set-based checks evaluated inside PostgreSQL; only violation counts and
sample business keys leave the database, never personal values.

The database's own PRIMARY KEY/UNIQUE/FOREIGN KEY constraints normally
reject these defects during the Load itself (the Load stage then fails
first). These checks are defense in depth for constraint drift and for keys
the schema does not enforce (normalized email, trimmed sku).

Duplicate business keys (user_id, product_id, cart_id, (cart_id,
item_position)) are not re-checked here: test_completeness reports them at
the Database boundary in the same gate, even if a constraint drifted.
"""

import pytest

from support.db_helpers import violations
from support.etl_contract import ENTITIES, is_text, mandatory_columns
from support.load_freshness import BASELINE_FILE, KEY_SQL, row_versions
from support.reconciliation import sample
from utils.json_files import read_json


pytestmark = [pytest.mark.load, pytest.mark.database]


# (case id, table, group expression, "value present" condition, sample key expression)
UNIQUE_KEY_CASES = [
    # Email is a business key compared case- and whitespace-insensitively;
    # blank/NULL emails are mandatory-field defects, not duplicates
    ("users.email (normalized)", "users", "LOWER(BTRIM(email))",
     "NULLIF(BTRIM(email), '') IS NOT NULL", "user_id::text"),
    ("products.sku (trimmed)", "products", "BTRIM(sku)",
     "NULLIF(BTRIM(sku), '') IS NOT NULL", "product_id::text"),
]


# Validate uniqueness of the business keys the schema does not enforce; each
# duplicate group is reported by the ids of its rows (the email is never shown)
@pytest.mark.parametrize(
    "case_id, table, group_by, present, sample_key",
    UNIQUE_KEY_CASES,
    ids=[case[0] for case in UNIQUE_KEY_CASES]
)
def test_target_unique_keys(db_connection, case_id, table, group_by, present, sample_key):
    count, groups = violations(
        db_connection,
        f"STRING_AGG({sample_key}, ',' ORDER BY {sample_key})",
        f"FROM {table} WHERE {present} GROUP BY {group_by} HAVING COUNT(*) > 1"
    )

    assert count == 0, (
        f"[Database] unique key: {case_id} | duplicate groups: {count} | "
        f"sample groups (row keys): {groups}"
    )


CI_KEY = "ci.cart_id::text || ':' || ci.item_position::text"

RI_CASES = [
    ("carts.user_id -> users", "c.cart_id",
     "FROM carts c WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.user_id = c.user_id)"),
    ("cart_items.cart_id -> carts", CI_KEY,
     "FROM cart_items ci WHERE NOT EXISTS (SELECT 1 FROM carts c WHERE c.cart_id = ci.cart_id)"),
    ("cart_items.product_id -> products", CI_KEY,
     "FROM cart_items ci WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = ci.product_id)"),
]


# Validate referential integrity with anti-joins (a NULL foreign key counts
# as an orphan; no INNER JOIN can hide the defective row)
@pytest.mark.parametrize("relationship, key_sql, from_sql", RI_CASES, ids=[c[0] for c in RI_CASES])
def test_target_referential_integrity(db_connection, relationship, key_sql, from_sql):
    count, keys = violations(db_connection, key_sql, from_sql)

    assert count == 0, f"[Database] {relationship} | orphans: {count} | sample keys: {keys}"


# Validate mandatory fields: NULL for every column, and also '' or
# whitespace-only for text columns
@pytest.mark.parametrize("entity", ENTITIES)
def test_target_mandatory_fields(db_connection, entity):
    failures = []

    for column in mandatory_columns(entity):
        missing = (
            f"NULLIF(BTRIM({column}), '') IS NULL" if is_text(entity, column)
            else f"{column} IS NULL"
        )
        count, keys = violations(db_connection, KEY_SQL[entity], f"FROM {entity} WHERE {missing}")

        if count:
            failures.append(f"field: {column} | missing/blank: {count} | sample keys: {keys}")

    assert not failures, f"[Database] entity: {entity}\n  " + "\n  ".join(failures)


# Validate that the Load of this pipeline run actually wrote every target row:
# each key must have a new row version (xmin) compared with the baseline
# captured just before the Load. Assumes no other process loads the same
# database between the baseline and this check (build isolation).
@pytest.mark.parametrize("entity", ENTITIES)
@pytest.mark.regression
def test_load_freshness(db_connection, entity):
    if not BASELINE_FILE.exists():
        pytest.fail(
            "[Load freshness] no baseline: run 'python -m support.load_freshness' "
            "(PYTHONPATH=src;tests) immediately before the Load",
            pytrace=False
        )

    baseline = read_json(BASELINE_FILE)
    before = baseline["row_versions"][entity]

    cursor = db_connection.cursor()
    after = row_versions(cursor, entity)
    cursor.close()

    assert after, f"[Load freshness] {entity}: the target table is empty after the Load"

    unchanged = [key for key, version in after.items() if before.get(key) == version]

    assert not unchanged, (
        f"[Load freshness] {entity}: {len(unchanged)} of {len(after)} rows were not "
        f"written by the Load since the baseline ({baseline['captured_at']}) | "
        f"sample keys: {sample(unchanged)}"
    )
