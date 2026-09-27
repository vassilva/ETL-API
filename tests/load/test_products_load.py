import pytest
from decimal import Decimal

from support.db_helpers import fetch_records, index_by


pytestmark = [pytest.mark.load, pytest.mark.database, pytest.mark.artifacts]


# Validate processed Products count against PostgreSQL
@pytest.mark.smoke
def test_products_count(processed_products, db_connection):
    cursor = db_connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM products")
    database_count = cursor.fetchone()[0]

    cursor.close()

    assert database_count == len(processed_products)


# Validate that Product IDs are unique in PostgreSQL
def test_products_ids_are_unique(db_connection):
    cursor = db_connection.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT product_id)
        FROM products
        """
    )

    total_count, unique_count = cursor.fetchone()

    cursor.close()

    assert total_count == unique_count


# Validate Products field by field: Processed JSON vs PostgreSQL
def test_products_data_reconciliation(processed_products, db_connection):
    database_products = fetch_records(
        db_connection,
        """
        SELECT
            product_id,
            product_name,
            category,
            price,
            discount_percentage,
            discounted_price,
            rating,
            stock,
            brand,
            sku,
            availability_status
        FROM products
        """
    )

    database_by_id = index_by(database_products, "product_id")

    for expected_product in processed_products:
        product_id = expected_product["product_id"]

        assert product_id in database_by_id

        actual_product = database_by_id[product_id]

        assert actual_product["product_name"] == expected_product["product_name"]
        assert actual_product["category"] == expected_product["category"]

        assert actual_product["price"] == Decimal(
            str(expected_product["price"])
        )

        assert actual_product["discount_percentage"] == Decimal(
            str(expected_product["discount_percentage"])
        )

        assert actual_product["discounted_price"] == Decimal(
            str(expected_product["discounted_price"])
        )

        assert actual_product["rating"] == Decimal(
            str(expected_product["rating"])
        )

        assert actual_product["stock"] == expected_product["stock"]
        assert actual_product["brand"] == expected_product["brand"]
        assert actual_product["sku"] == expected_product["sku"]
        assert (
            actual_product["availability_status"]
            == expected_product["availability_status"]
        )