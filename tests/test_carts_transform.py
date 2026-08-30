import json
import pytest

from transform.carts import load_raw_carts
from transform.carts import transform_carts


@pytest.fixture(scope="module")
def carts_transform_data():
    raw_carts = load_raw_carts()
    processed_carts = transform_carts()

    return raw_carts, processed_carts


@pytest.fixture(scope="module")
def processed_users():
    with open("data/processed/users.json", "r", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture(scope="module")
def processed_products():
    with open("data/processed/products.json", "r", encoding="utf-8") as file:
        return json.load(file)


# Validate that the number of processed carts matches the number of raw carts
def test_carts_transform_count(carts_transform_data):
    raw_carts, processed_carts = carts_transform_data

    assert len(processed_carts) == len(raw_carts)


# Validate that raw cart ID is correctly mapped to cart_id
def test_carts_id_mapping(carts_transform_data):
    raw_carts, processed_carts = carts_transform_data

    for raw_cart, processed_cart in zip(raw_carts, processed_carts):
        assert processed_cart["cart_id"] == raw_cart["id"]


# Validate that userId is correctly mapped to user_id
def test_carts_user_id_mapping(carts_transform_data):
    raw_carts, processed_carts = carts_transform_data

    for raw_cart, processed_cart in zip(raw_carts, processed_carts):
        assert processed_cart["user_id"] == raw_cart["userId"]


# Validate that total is correctly mapped
def test_carts_total_mapping(carts_transform_data):
    raw_carts, processed_carts = carts_transform_data

    for raw_cart, processed_cart in zip(raw_carts, processed_carts):
        assert processed_cart["total"] == raw_cart["total"]


# Validate that discountedTotal is correctly mapped
def test_carts_discounted_total_mapping(carts_transform_data):
    raw_carts, processed_carts = carts_transform_data

    for raw_cart, processed_cart in zip(raw_carts, processed_carts):
        assert processed_cart["discounted_total"] == raw_cart["discountedTotal"]


# Validate that totalProducts is correctly mapped
def test_carts_total_products_mapping(carts_transform_data):
    raw_carts, processed_carts = carts_transform_data

    for raw_cart, processed_cart in zip(raw_carts, processed_carts):
        assert processed_cart["total_products"] == raw_cart["totalProducts"]


# Validate that totalQuantity is correctly mapped
def test_carts_total_quantity_mapping(carts_transform_data):
    raw_carts, processed_carts = carts_transform_data

    for raw_cart, processed_cart in zip(raw_carts, processed_carts):
        assert processed_cart["total_quantity"] == raw_cart["totalQuantity"]


# Validate that the number of processed products matches the raw cart products
def test_carts_products_count_mapping(carts_transform_data):
    raw_carts, processed_carts = carts_transform_data

    for raw_cart, processed_cart in zip(raw_carts, processed_carts):
        assert len(processed_cart["products"]) == len(raw_cart["products"])


# Validate that cart product fields are correctly transformed
def test_cart_products_mapping(carts_transform_data):
    raw_carts, processed_carts = carts_transform_data

    for raw_cart, processed_cart in zip(raw_carts, processed_carts):
        for raw_product, processed_product in zip(
            raw_cart["products"],
            processed_cart["products"]
        ):
            assert processed_product["product_id"] == raw_product["id"]
            assert processed_product["product_name"] == raw_product["title"]
            assert processed_product["price"] == raw_product["price"]
            assert processed_product["quantity"] == raw_product["quantity"]
            assert processed_product["total"] == raw_product["total"]
            assert (
                processed_product["discount_percentage"]
                == raw_product["discountPercentage"]
            )
            assert (
                processed_product["discounted_total"]
                == raw_product["discountedTotal"]
            )


# Validate that processed cart IDs remain unique
def test_processed_carts_ids_are_unique(carts_transform_data):
    raw_carts, processed_carts = carts_transform_data

    ids = [cart["cart_id"] for cart in processed_carts]

    assert len(ids) == len(set(ids))


# Validate that every cart user_id exists in processed users
def test_cart_users_exist_in_processed_users(
    carts_transform_data,
    processed_users
):
    raw_carts, processed_carts = carts_transform_data

    user_ids = {user["user_id"] for user in processed_users}

    for cart in processed_carts:
        assert cart["user_id"] in user_ids


# Validate that every cart product exists in processed products
def test_cart_products_exist_in_processed_products(
    carts_transform_data,
    processed_products
):
    raw_carts, processed_carts = carts_transform_data

    product_ids = {
        product["product_id"]
        for product in processed_products
    }

    for cart in processed_carts:
        for product in cart["products"]:
            assert product["product_id"] in product_ids