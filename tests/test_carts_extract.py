import pytest
from extract.carts import extract_carts
from extract.products import extract_products


@pytest.fixture(scope="module")
def carts_data():
    return extract_carts()


@pytest.fixture(scope="module")
def products_data():
    return extract_products()


# Validate that the extraction returns cart data
def test_extract_carts_returns_data(carts_data):
    carts, total = carts_data

    assert carts is not None
    assert len(carts) > 0


# Validate that the number of extracted carts matches the total reported by the API
def test_extract_carts_count(carts_data):
    carts, total = carts_data

    assert len(carts) == total


# Validate that every extracted cart has a non-null ID
def test_carts_have_id(carts_data):
    carts, total = carts_data

    for cart in carts:
        assert cart["id"] is not None


# Validate that there are no duplicate cart IDs
def test_carts_ids_are_unique(carts_data):
    carts, total = carts_data

    ids = [cart["id"] for cart in carts]

    assert len(ids) == len(set(ids))


# Validate that every cart has a user ID
def test_carts_have_user_id(carts_data):
    carts, total = carts_data

    for cart in carts:
        assert cart["userId"] is not None


# Validate that every cart contains at least one product
def test_carts_have_products(carts_data):
    carts, total = carts_data

    for cart in carts:
        assert cart["products"] is not None
        assert len(cart["products"]) > 0


# Validate that product quantities in carts are greater than zero
def test_cart_products_have_valid_quantity(carts_data):
    carts, total = carts_data

    for cart in carts:
        for product in cart["products"]:
            assert product["quantity"] > 0


# Validate that cart totals are not negative
def test_carts_have_valid_total(carts_data):
    carts, total = carts_data

    for cart in carts:
        assert cart["total"] is not None
        assert cart["total"] >= 0


# Validate that every product referenced by a cart exists in the Products source
def test_cart_products_exist_in_products(carts_data, products_data):
    carts, _ = carts_data
    products, _ = products_data

    product_ids = {product["id"] for product in products}

    for cart in carts:
        for cart_product in cart["products"]:
            assert cart_product["id"] in product_ids


# Validate that product prices in carts match the Products source
def test_cart_product_prices_match_products(carts_data, products_data):
    carts, _ = carts_data
    products, _ = products_data

    product_prices = {
        product["id"]: product["price"]
        for product in products
    }

    for cart in carts:
        for cart_product in cart["products"]:
            product_id = cart_product["id"]

            assert cart_product["price"] == product_prices[product_id]