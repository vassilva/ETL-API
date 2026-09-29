"""
Structural load contract (offline).

The oracle is sql/create_tables.sql plus the declared business keys, never
the load SQL text itself:

- Non-destructive SQL: no DELETE/DROP/TRUNCATE/ALTER/CREATE/GRANT anywhere
  in the statement (reported before the structure is parsed).
- UPSERT contract: inserted columns = the table's business columns, conflict
  target = the business key (backed by a PRIMARY KEY/UNIQUE constraint), and
  DO UPDATE SET updates every other inserted column from its own EXCLUDED
  value. Protects against an UPSERT that silently stops updating a column
  (invisible to idempotency tests, whose two runs load identical data).
- Row alignment: every value a row builder produces lands in the SQL column
  of the same name. Protects against swapped values (e.g. price and
  discount_percentage), which a placeholder count cannot detect.
"""

import re

import pytest

import load.cart_items
import load.carts
import load.products
import load.users
from support.etl_contract import BUSINESS_KEYS, UNIQUE_KEYS, business_columns


pytestmark = [pytest.mark.load, pytest.mark.unit, pytest.mark.smoke]


UPSERT_STATEMENTS = {
    "users": load.users.UPSERT_USER_SQL,
    "products": load.products.UPSERT_PRODUCT_SQL,
    "carts": load.carts.UPSERT_CART_SQL,
    "cart_items": load.cart_items.UPSERT_CART_ITEM_SQL,
}

DESTRUCTIVE_KEYWORDS = ("DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT")

UPSERT_PATTERN = re.compile(
    r"INSERT INTO (?P<table>\w+) \((?P<columns>[^)]*)\) VALUES \((?P<values>[^)]*)\) "
    r"ON CONFLICT \((?P<conflict>[^)]*)\) DO UPDATE SET (?P<updates>.*)",
    re.I
)


def parse_upsert(statement):
    match = UPSERT_PATTERN.fullmatch(" ".join(statement.split()))

    assert match, "statement is not a single INSERT ... ON CONFLICT (...) DO UPDATE SET ..."

    def names(text):
        return [name.strip() for name in text.split(",")]

    assignments = [
        re.fullmatch(r"(\w+)\s*=\s*EXCLUDED\.(\w+)", item.strip(), re.I)
        for item in match["updates"].split(",")
    ]

    return {
        "table": match["table"],
        "columns": names(match["columns"]),
        "placeholders": names(match["values"]),
        "conflict": tuple(names(match["conflict"])),
        "updates": [
            (item.group(1), item.group(2)) if item else (None, None)
            for item in assignments
        ],
    }


# Validate the UPSERT structure of every table against the target contract
@pytest.mark.parametrize("table", UPSERT_STATEMENTS)
def test_upsert_matches_target_contract(table):
    statement = UPSERT_STATEMENTS[table]
    normalized = " ".join(statement.split()).upper()
    destructive = [k for k in DESTRUCTIVE_KEYWORDS if re.search(rf"\b{k}\b", normalized)]

    assert not destructive, f"[UPSERT contract] table: {table}: destructive SQL keywords {destructive}"

    upsert = parse_upsert(statement)
    expected_columns = business_columns(table)
    key = BUSINESS_KEYS[table]

    inserted = upsert["columns"]
    updated = [target for target, _ in upsert["updates"]]
    problems = []

    if upsert["table"] != table:
        problems.append(f"inserts into '{upsert['table']}'")

    if duplicates := sorted({c for c in inserted if inserted.count(c) > 1}):
        problems.append(f"duplicated insert columns: {duplicates}")

    if missing := [c for c in expected_columns if c not in inserted]:
        problems.append(f"missing insert columns: {missing}")

    if unexpected := [c for c in inserted if c not in expected_columns]:
        problems.append(f"unexpected insert columns: {unexpected}")

    if len(upsert["placeholders"]) != len(inserted):
        problems.append(
            f"{len(upsert['placeholders'])} placeholders for {len(inserted)} columns"
        )

    if upsert["conflict"] != key:
        problems.append(f"conflict target {upsert['conflict']} != business key {key}")

    if key not in UNIQUE_KEYS[table]:
        problems.append(f"business key {key} has no PRIMARY KEY/UNIQUE constraint in the DDL")

    if None in updated:
        problems.append("DO UPDATE SET has an assignment that is not 'column = EXCLUDED.column'")

    if crossed := [(t, s) for t, s in upsert["updates"] if t and t != s]:
        problems.append(f"columns updated from another column's value: {crossed}")

    if missing_updates := [c for c in inserted if c not in key and c not in updated]:
        problems.append(f"missing update columns: {missing_updates}")

    if unexpected_updates := [c for c in updated if c and (c in key or c not in inserted)]:
        problems.append(f"unexpected update columns: {unexpected_updates}")

    assert not problems, f"[UPSERT contract] table: {table}\n  " + "\n  ".join(problems)


def _sentinel(column):
    return f"<{column}>"


def _aligned_row(table):
    """(row produced by the load code, expected value for every SQL column)."""
    if table != "cart_items":
        record = {column: _sentinel(column) for column in business_columns(table)}
        builder = {
            "users": load.users.user_row,
            "products": load.products.product_row,
            "carts": load.carts.cart_row,
        }[table]

        return builder(record), record

    item_columns = [c for c in business_columns(table) if c not in ("cart_id", "item_position")]
    item = {column: _sentinel(column) for column in item_columns}
    cart = {"cart_id": _sentinel("cart_id"), "products": [item]}

    (row,) = load.cart_items.cart_item_rows([cart])

    # item_position is generated by the load: the first item of a cart is 1
    return row, {**item, "cart_id": _sentinel("cart_id"), "item_position": 1}


# Validate that each row value lands in the SQL column of the same name
@pytest.mark.parametrize("table", UPSERT_STATEMENTS)
def test_row_values_align_with_sql_columns(table):
    columns = parse_upsert(UPSERT_STATEMENTS[table])["columns"]
    row, expected = _aligned_row(table)

    assert len(row) == len(columns), (
        f"[Row alignment] table: {table}: row has {len(row)} values for {len(columns)} columns"
    )

    misaligned = [
        f"column '{column}' receives {value!r} (expected {expected.get(column)!r})"
        for column, value in zip(columns, row)
        if value != expected.get(column)
    ]

    assert not misaligned, f"[Row alignment] table: {table}\n  " + "\n  ".join(misaligned)
