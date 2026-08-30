import pytest
from extract.products import extract_products


@pytest.fixture(scope="module")
def products_data():
    return extract_products()


# Validate that the extraction returns product data
def test_extract_products_returns_data(products_data):
    products, total = products_data

    assert products is not None
    assert len(products) > 0


# Validate that the number of extracted products matches the total reported by the API
def test_extract_products_count(products_data):
    products, total = products_data

    assert len(products) == total


# Validate that every extracted product has a non-null ID
def test_products_have_id(products_data):
    products, total = products_data

    for product in products:
        assert product["id"] is not None


# Validate that there are no duplicate product IDs
def test_products_ids_are_unique(products_data):
    products, total = products_data

    ids = [product["id"] for product in products]

    assert len(ids) == len(set(ids))


# Validate that every product has a title
def test_products_have_title(products_data):
    products, total = products_data

    for product in products:
        assert product["title"] is not None
        assert product["title"] != ""


# Validate that every product has a valid non-negative price
def test_products_have_valid_price(products_data):
    products, total = products_data

    for product in products:
        assert product["price"] is not None
        assert product["price"] >= 0


# Validate that product stock cannot be negative
def test_products_have_valid_stock(products_data):
    products, total = products_data

    for product in products:
        assert product["stock"] is not None
        assert product["stock"] >= 0