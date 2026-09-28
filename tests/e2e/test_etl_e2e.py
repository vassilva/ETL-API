"""
End-to-end ETL validation:

    DummyJSON API -> Extract -> data/raw -> Transform -> data/processed
    -> Load -> PostgreSQL -> QA validation, then a second run (idempotency)

Opt-in only (pytest -m e2e --run-e2e): the ETL writes data/ and upserts
into PostgreSQL. Row-by-row processed JSON vs PostgreSQL reconciliation is
already covered by tests/load and is not repeated here; run it after this
suite (pytest -m database).
"""

from decimal import Decimal

import pytest

from support.assertions import assert_field_matches
from support.db_helpers import index_by
from transform.carts import transform_carts_data
from transform.products import transform_products_data
from transform.users import transform_users_data

from support.etl_e2e import (
    BUSINESS_RULES,
    FOREIGN_KEYS,
    MANDATORY_COLUMNS,
    RESOURCES,
    TABLE_KEYS,
    UNIQUE_KEYS,
)


pytestmark = [pytest.mark.e2e, pytest.mark.live_api, pytest.mark.database]


TRANSFORMS = {
    "users": transform_users_data,
    "products": transform_products_data,
    "carts": transform_carts_data,
}

# Allowance for file-system timestamp resolution
MTIME_TOLERANCE_SECONDS = 2


def expected_counts(source_data):
    carts = source_data["carts"]["carts"]

    return {
        "users": source_data["users"]["total"],
        "products": source_data["products"]["total"],
        "carts": source_data["carts"]["total"],
        "cart_items": sum(len(cart["products"]) for cart in carts),
    }


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


# Extract

@pytest.mark.parametrize("resource", RESOURCES)
def test_live_api_returns_complete_collection(source_data, resource):
    payload = source_data[resource]

    assert payload["total"] > 0
    assert len(payload[resource]) == payload["total"]


def test_etl_run_reports_every_stage(first_run):
    output = first_run["stdout"]

    for line in (
        "Users extracted:", "Products extracted:", "Carts extracted:",
        "Users transformed:", "Products transformed:", "Carts transformed:",
        "Users loaded:", "Products loaded:", "Carts loaded:",
        "Cart items loaded:",
    ):
        assert line in output


def test_artifacts_written_by_this_run(first_run):
    for path, modified in first_run["artifacts"]["modified"].items():
        assert modified >= first_run["started"] - MTIME_TOLERANCE_SECONDS, (
            f"{path.name} was not rewritten by the ETL run"
        )


@pytest.mark.parametrize("resource", RESOURCES)
def test_raw_matches_live_api(first_run, source_data, resource):
    raw = first_run["artifacts"]["raw"][resource]
    source = source_data[resource]

    assert raw["total"] == source["total"]
    assert sorted(record["id"] for record in raw[resource]) == sorted(
        record["id"] for record in source[resource]
    )


# Transform

@pytest.mark.parametrize("resource", RESOURCES)
def test_processed_is_transform_of_raw(first_run, resource):
    artifacts = first_run["artifacts"]
    raw_records = artifacts["raw"][resource][resource]

    # Compared by equality only, so no record values reach the report
    assert artifacts["processed"][resource] == TRANSFORMS[resource](raw_records)


# Load: first run

def test_row_counts_match_source(first_run, source_data):
    assert first_run["state"]["counts"] == expected_counts(source_data)


@pytest.mark.parametrize("key", UNIQUE_KEYS)
def test_keys_are_unique(first_run, key):
    assert first_run["state"]["duplicates"][key] == 0


@pytest.mark.parametrize("relationship", FOREIGN_KEYS)
def test_referential_integrity(first_run, relationship):
    assert first_run["state"]["orphans"][relationship] == 0


@pytest.mark.parametrize("table", MANDATORY_COLUMNS)
def test_mandatory_fields_are_not_null(first_run, table):
    nulls = {
        column: count
        for column, count in first_run["state"]["nulls"].items()
        if column.startswith(f"{table}.") and count
    }

    assert nulls == {}


@pytest.mark.parametrize("rule", BUSINESS_RULES)
def test_business_rule(first_run, rule):
    assert first_run["state"]["rule_violations"][rule] == 0


# Source (live API) -> PostgreSQL, bypassing the intermediate files

def test_users_source_values_in_database(first_run, source_data):
    database_by_id = index_by(first_run["state"]["rows"]["users"], "user_id")

    for user in source_data["users"]["users"]:
        user_id = user["id"]
        actual = database_by_id[user_id]

        for field, expected in (
            ("email", user["email"]),
            ("full_name", f'{user["firstName"]} {user["lastName"]}'),
            ("city", user["address"]["city"]),
            ("company_name", user["company"]["name"]),
        ):
            assert_field_matches(
                actual[field],
                expected,
                entity="user",
                record_id=user_id,
                field=field
            )


def test_products_source_values_in_database(first_run, source_data):
    database_by_id = index_by(first_run["state"]["rows"]["products"], "product_id")

    for product in source_data["products"]["products"]:
        actual = database_by_id[product["id"]]

        assert actual["product_name"] == product["title"]
        assert actual["category"] == product["category"]
        assert actual["price"] == money(product["price"])
        assert actual["discount_percentage"] == money(product["discountPercentage"])
        assert actual["rating"] == money(product["rating"])
        assert actual["stock"] == product["stock"]
        assert actual["brand"] == product.get("brand")
        assert actual["sku"] == product["sku"]


def test_carts_source_values_in_database(first_run, source_data):
    database_by_id = index_by(first_run["state"]["rows"]["carts"], "cart_id")

    for cart in source_data["carts"]["carts"]:
        actual = database_by_id[cart["id"]]

        assert actual["user_id"] == cart["userId"]
        assert actual["total"] == money(cart["total"])
        assert actual["discounted_total"] == money(cart["discountedTotal"])
        assert actual["total_products"] == cart["totalProducts"]
        assert actual["total_quantity"] == cart["totalQuantity"]


def test_cart_items_source_values_in_database(first_run, source_data):
    database_by_key = index_by(
        first_run["state"]["rows"]["cart_items"], "cart_id", "item_position"
    )

    for cart in source_data["carts"]["carts"]:
        for position, product in enumerate(cart["products"], start=1):
            actual = database_by_key[(cart["id"], position)]

            assert actual["product_id"] == product["id"]
            assert actual["quantity"] == product["quantity"]
            assert actual["price"] == money(product["price"])
            assert actual["total"] == money(product["total"])
            assert actual["discounted_total"] == money(product["discountedTotal"])


# Idempotency: second run against the same database

def test_second_run_keeps_row_counts(first_run, second_run, source_data):
    assert second_run["state"]["counts"] == first_run["state"]["counts"]
    assert second_run["state"]["counts"] == expected_counts(source_data)


@pytest.mark.parametrize("key", UNIQUE_KEYS)
def test_second_run_creates_no_duplicates(second_run, key):
    assert second_run["state"]["duplicates"][key] == 0


@pytest.mark.parametrize("relationship", FOREIGN_KEYS)
def test_second_run_keeps_referential_integrity(second_run, relationship):
    assert second_run["state"]["orphans"][relationship] == 0


@pytest.mark.parametrize("table", TABLE_KEYS)
def test_second_run_leaves_table_content_unchanged(first_run, second_run, table):
    # Covers every column, including the cart_items identity key: rows were
    # updated in place, not deleted and re-inserted
    assert (
        second_run["state"]["fingerprints"][table]
        == first_run["state"]["fingerprints"][table]
    )


@pytest.mark.parametrize("table", TABLE_KEYS)
def test_second_run_upserts_every_existing_row(first_run, second_run, table):
    before = first_run["state"]["row_versions"][table]
    after = second_run["state"]["row_versions"][table]

    assert after.keys() == before.keys()

    # ON CONFLICT DO UPDATE writes a new row version (new xmin) for each key
    not_updated = [key for key in before if after[key] == before[key]]

    assert not_updated == []
