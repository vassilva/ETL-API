"""
Live source quality (DummyJSON), independent of the ETL.

Detects upstream data problems at the Source boundary, before the ETL can
propagate them. Every check first requires a non-empty collection, so an
empty source can never pass vacuously, and reports the offending ids.

PR Regression (merge-blocking source contract, before Extract): the complete
collection, the anchor of Source-anchored completeness. Everything else here
is upstream monitoring and runs only in the local Full Regression.
"""

import pytest

from support.etl_contract import SOURCE_RESOURCES, source_key, source_records
from support.reconciliation import sample


pytestmark = [pytest.mark.extract, pytest.mark.live_api]


def _records(source_payloads, entity):
    records = source_records(entity, source_payloads)

    assert records, f"[Source] {entity}: the API returned no records"

    return records


# Validate that the API returned the complete, non-empty collection
@pytest.mark.regression
@pytest.mark.parametrize("resource", SOURCE_RESOURCES)
def test_source_collection_is_complete(source_payloads, resource):
    payload = source_payloads[resource]
    returned = len(payload[resource])

    assert payload["total"] > 0, f"[Source] {resource}: API reports total 0"
    assert returned == payload["total"], (
        f"[Source] {resource}: returned {returned} of {payload['total']} records (truncated?)"
    )


# Validate that every source record has a unique, non-null id
@pytest.mark.parametrize("resource", SOURCE_RESOURCES)
def test_source_keys_are_valid(source_payloads, resource):
    ids = [record.get("id") for record in _records(source_payloads, resource)]
    seen, duplicates = set(), []

    for record_id in ids:
        if record_id in seen:
            duplicates.append(record_id)
        seen.add(record_id)

    nulls = ids.count(None)

    assert nulls == 0 and not duplicates, (
        f"[Source] {resource}.id: null ids: {nulls} | "
        f"duplicates: {len(duplicates)} | sample: {sample(duplicates)}"
    )


def _is_blank(value):
    return not isinstance(value, str) or not value.strip()


# (rule id, entity, violation predicate). Price > 0 is the explicit
# laboratory business rule, applied identically at the Target.
SOURCE_RULES = [
    ("products.title is not blank", "products", lambda p: _is_blank(p.get("title"))),
    ("products.price > 0", "products", lambda p: not (p.get("price") or 0) > 0),
    ("products.stock >= 0", "products",
     lambda p: not isinstance(p.get("stock"), int) or p["stock"] < 0),
    ("carts.userId is present", "carts", lambda c: c.get("userId") is None),
    ("carts have at least one product", "carts", lambda c: not c.get("products")),
    ("carts.total >= 0", "carts", lambda c: c.get("total") is None or c["total"] < 0),
    ("cart items quantity > 0", "cart_items", lambda i: not (i["item"].get("quantity") or 0) > 0),
]


# Validate each source business rule; failures list the violating keys
@pytest.mark.parametrize("rule_id, entity, violates", SOURCE_RULES, ids=[r[0] for r in SOURCE_RULES])
def test_source_rule(source_payloads, rule_id, entity, violates):
    records = _records(source_payloads, entity)
    violating = [source_key(entity, record) for record in records if violates(record)]

    assert not violating, (
        f"[Source] rule: {rule_id} | violations: {len(violating)} | sample keys: {sample(violating)}"
    )


# Validate that every product referenced by a cart exists in the products source
def test_source_cart_products_exist(source_payloads):
    product_ids = {p["id"] for p in _records(source_payloads, "products")}
    items = _records(source_payloads, "cart_items")

    orphans = [source_key("cart_items", i) for i in items if i["item"]["id"] not in product_ids]

    assert not orphans, (
        f"[Source] cart items -> products: orphans: {len(orphans)} | sample keys: {sample(orphans)}"
    )


# Validate that cart item prices match the products source
def test_source_cart_prices_match_products(source_payloads):
    prices = {p["id"]: p["price"] for p in _records(source_payloads, "products")}
    items = _records(source_payloads, "cart_items")

    mismatched = [
        source_key("cart_items", i) for i in items
        if i["item"]["id"] in prices and i["item"]["price"] != prices[i["item"]["id"]]
    ]

    assert not mismatched, (
        f"[Source] cart item price == product price: mismatches: {len(mismatched)} | "
        f"sample keys: {sample(mismatched)}"
    )
