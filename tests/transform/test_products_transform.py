import pytest

from transform.products import transform_products_data


pytestmark = [pytest.mark.transform, pytest.mark.artifacts]


@pytest.fixture(scope="module")
def products_transform_data(raw_products):
    processed_products = transform_products_data(raw_products)

    return raw_products, processed_products


# Validate that the number of processed products matches the number of raw products
@pytest.mark.smoke
def test_products_transform_count(products_transform_data):
    raw_products, processed_products = products_transform_data

    assert len(processed_products) == len(raw_products)


# Validate that raw product ID is correctly mapped to product_id
def test_products_id_mapping(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        assert processed_product["product_id"] == raw_product["id"]


# Validate product_name = raw title + " - RP" (exact, matched by product id)
def test_products_name_mapping(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        assert processed_product["product_id"] == raw_product["id"]
        assert processed_product["product_name"] == raw_product["title"] + " - RP"


# Validate that every product keeps its complete original title as the prefix
# and gets the " - RP" suffix exactly once
def test_products_name_suffix_exactly_once(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        title = raw_product["title"]
        product_name = processed_product["product_name"]

        assert product_name[:len(title)] == title
        assert product_name[len(title):] == " - RP"
        assert not product_name.endswith(" - RP - RP")
        assert product_name.count(" - RP") == title.count(" - RP") + 1


# Validate that the committed processed snapshot is exactly the transformation
# of the raw snapshot (every field, every product), so only the fields changed
# by the transformation rules can differ from the raw data
def test_processed_products_snapshot_matches_transformation(
    products_transform_data,
    processed_products
):
    raw_products, expected_products = products_transform_data

    assert len(processed_products) == len(raw_products)
    assert processed_products == expected_products


# Validate that category is correctly mapped
def test_products_category_mapping(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        assert processed_product["category"] == raw_product["category"]


# Validate that price is correctly mapped
def test_products_price_mapping(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        assert processed_product["price"] == raw_product["price"]


# Validate that discountPercentage is correctly mapped
def test_products_discount_mapping(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        assert (
            processed_product["discount_percentage"]
            == raw_product["discountPercentage"]
        )


# Validate that discounted_price is correctly calculated
def test_products_discounted_price_calculation(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        expected_price = round(
            raw_product["price"]
            * (1 - raw_product["discountPercentage"] / 100),
            2
        )

        assert processed_product["discounted_price"] == expected_price


# Validate that rating is correctly mapped
def test_products_rating_mapping(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        assert processed_product["rating"] == raw_product["rating"]


# Validate that stock is correctly mapped
def test_products_stock_mapping(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        assert processed_product["stock"] == raw_product["stock"]


# Validate that brand is correctly mapped
def test_products_brand_mapping(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        assert processed_product["brand"] == raw_product.get("brand")


# Validate that SKU is correctly mapped
def test_products_sku_mapping(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        assert processed_product["sku"] == raw_product["sku"]


# Validate that availabilityStatus is correctly mapped
def test_products_availability_status_mapping(products_transform_data):
    raw_products, processed_products = products_transform_data

    for raw_product, processed_product in zip(raw_products, processed_products):
        assert (
            processed_product["availability_status"]
            == raw_product["availabilityStatus"]
        )


# Validate that processed product IDs remain unique
def test_processed_products_ids_are_unique(products_transform_data):
    raw_products, processed_products = products_transform_data

    ids = [product["product_id"] for product in processed_products]

    assert len(ids) == len(set(ids))