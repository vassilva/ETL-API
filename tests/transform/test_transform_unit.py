import copy
import json

import pytest

import transform.carts
import transform.products
import transform.users
from config.settings import PROJECT_ROOT
from transform.carts import transform_cart, transform_carts_data
from transform.products import transform_product, transform_products_data
from transform.users import transform_user, transform_users_data
from utils.json_files import read_json, resolve_path, write_json


pytestmark = [pytest.mark.transform, pytest.mark.unit]


# Users

# Validate the complete user mapping, including flattened nested fields
@pytest.mark.smoke
def test_transform_user_maps_all_fields(synthetic_payload):
    raw_user = synthetic_payload("users")["users"][0]

    assert transform_user(raw_user) == {
        "user_id": 1,
        "first_name": "Test",
        "last_name": "User-One",
        "full_name": "Test User-One",
        "email": "user.one@example.test",
        "phone": "+00 000-000-0001",
        "city": "Sample City",
        "state": "Sample State",
        "country": "Testland",
        "company_name": "Example Corp",
        "department": "Quality"
    }


# Validate that full_name keeps non-ASCII characters unchanged
@pytest.mark.regression
def test_transform_user_full_name_keeps_unicode(synthetic_payload):
    raw_user = synthetic_payload("users")["users"][1]

    assert transform_user(raw_user)["full_name"] == "Ámélie Tëst"


# Products

# Validate discounted_price = price * (1 - discount / 100), rounded to 2 decimals
@pytest.mark.parametrize(
    "price, discount, expected",
    [
        (100.0, 12.5, 87.5),
        (19.99, 10.0, 17.99),
        (50.0, 0.0, 50.0),
        (0.0, 25.0, 0.0),
    ]
)
def test_transform_product_discounted_price(synthetic_payload, price, discount, expected):
    raw_product = synthetic_payload("products")["products"][0]
    raw_product["price"] = price
    raw_product["discountPercentage"] = discount

    assert transform_product(raw_product)["discounted_price"] == expected


# Validate the complete product mapping
@pytest.mark.smoke
def test_transform_product_maps_all_fields(synthetic_payload):
    raw_product = synthetic_payload("products")["products"][0]

    assert transform_product(raw_product) == {
        "product_id": 101,
        "product_name": "Synthetic Widget - RP",
        "category": "test-category",
        "price": 100.0,
        "discount_percentage": 12.5,
        "discounted_price": 87.5,
        "rating": 4.5,
        "stock": 10,
        "brand": "TestBrand",
        "sku": "TST-0101",
        "availability_status": "In Stock"
    }


# Validate that a product without brand is mapped to None
def test_transform_product_without_brand(synthetic_payload):
    raw_product = synthetic_payload("products")["products"][1]

    assert "brand" not in raw_product
    assert transform_product(raw_product)["brand"] is None


# Validate product_name = original title + " - RP": the whole original title is
# kept unchanged as the prefix and the suffix is added exactly once
@pytest.mark.parametrize(
    "title",
    [
        "Synthetic Widget",
        "Ámélie Café Crème",               # non-ASCII characters unchanged
        "  Padded  Name  ",                # inner and outer whitespace unchanged
        "RP Product - Special Edition",    # existing "RP" and " - " text unchanged
        "Name - R",                        # suffix-like ending is not merged
    ]
)
@pytest.mark.regression
def test_transform_product_name_appends_rp_suffix(synthetic_payload, title):
    raw_product = synthetic_payload("products")["products"][0]
    raw_product["title"] = title

    product_name = transform_product(raw_product)["product_name"]

    assert product_name == title + " - RP"
    assert product_name[:len(title)] == title
    assert product_name[len(title):] == " - RP"
    assert product_name.count(" - RP") == title.count(" - RP") + 1


# Carts

# Validate the cart mapping including the nested product list. Cart item names
# keep the original title: the " - RP" rule applies to products only
@pytest.mark.smoke
def test_transform_cart_maps_cart_and_products(synthetic_payload):
    raw_cart = synthetic_payload("carts")["carts"][0]

    transformed = transform_cart(raw_cart)

    assert transformed["cart_id"] == 201
    assert transformed["user_id"] == 1
    assert transformed["total"] == 239.98
    assert transformed["discounted_total"] == 214.98
    assert transformed["total_products"] == 2
    assert transformed["total_quantity"] == 4
    assert transformed["products"] == [
        {
            "product_id": 101,
            "product_name": "Synthetic Widget",
            "price": 100.0,
            "quantity": 2,
            "total": 200.0,
            "discount_percentage": 12.5,
            "discounted_total": 175.0
        },
        {
            "product_id": 102,
            "product_name": "Unbranded Gadget",
            "price": 19.99,
            "quantity": 2,
            "total": 39.98,
            "discount_percentage": 0.0,
            "discounted_total": 39.98
        }
    ]


# Pure list transformations

# Validate that *_data functions keep order and length and never mutate input
@pytest.mark.parametrize(
    "resource, transform_data, single_transform, id_field",
    [
        ("users", transform_users_data, transform_user, "user_id"),
        ("products", transform_products_data, transform_product, "product_id"),
        ("carts", transform_carts_data, transform_cart, "cart_id"),
    ]
)
def test_transform_data_is_pure(
    synthetic_payload, resource, transform_data, single_transform, id_field
):
    records = synthetic_payload(resource)[resource]
    original = copy.deepcopy(records)

    transformed = transform_data(records)

    assert records == original
    assert transformed == [single_transform(record) for record in original]
    assert [row[id_field] for row in transformed] == [
        record["id"] for record in original
    ]


# Backward-compatible file wrappers

# Validate that transform_*() still read raw, write processed and return the data
@pytest.mark.parametrize(
    "resource, module, wrapper, label",
    [
        ("users", transform.users, transform.users.transform_users, "Users"),
        ("products", transform.products, transform.products.transform_products, "Products"),
        ("carts", transform.carts, transform.carts.transform_carts, "Carts"),
    ]
)
def test_transform_wrapper_file_contract(
    monkeypatch, tmp_path, capsys, synthetic_payload, resource, module, wrapper, label
):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    payload = synthetic_payload(resource)

    write_json(raw_dir / f"{resource}.json", payload)
    monkeypatch.setattr(module, "RAW_DATA_DIR", raw_dir)
    monkeypatch.setattr(module, "PROCESSED_DATA_DIR", processed_dir)

    result = wrapper()

    processed_file = processed_dir / f"{resource}.json"

    transform_data = getattr(module, f"transform_{resource}_data")

    assert result == transform_data(payload[resource])
    assert read_json(processed_file) == result
    assert capsys.readouterr().out == f"{label} transformed: {len(result)}\n"


# JSON utilities

# Validate that written JSON keeps the original serialization format
def test_write_json_preserves_serialization_format(tmp_path):
    data = [{"full_name": "Ámélie Tëst", "price": 1.5}]
    target = tmp_path / "nested" / "out.json"

    write_json(target, data)

    with open(target, "r", encoding="utf-8") as file:
        written = file.read()

    assert written == json.dumps(data, ensure_ascii=False, indent=4)
    assert "Ámélie" in written


# Validate that relative paths are anchored to the project root
def test_resolve_path_is_anchored_to_project_root(tmp_path):
    assert resolve_path("data/raw/users.json") == PROJECT_ROOT / "data/raw/users.json"
    assert resolve_path(tmp_path) == tmp_path
