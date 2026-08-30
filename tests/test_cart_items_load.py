import json
import pytest

from decimal import Decimal, ROUND_HALF_UP
from load.database import get_connection


def decimal_2(value):
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


@pytest.fixture(scope="module")
def db_connection():
    connection = get_connection()

    yield connection

    connection.close()


@pytest.fixture(scope="module")
def processed_carts():
    with open("data/processed/carts.json", "r", encoding="utf-8") as file:
        return json.load(file)


# Validate total Cart Items count against PostgreSQL
def test_cart_items_count(processed_carts, db_connection):
    expected_count = sum(
        len(cart["products"])
        for cart in processed_carts
    )

    cursor = db_connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM cart_items")
    database_count = cursor.fetchone()[0]

    cursor.close()

    assert database_count == expected_count


# Validate that every Cart Item references an existing Cart
def test_cart_items_have_valid_carts(db_connection):
    cursor = db_connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM cart_items ci
        LEFT JOIN carts c
            ON ci.cart_id = c.cart_id
        WHERE c.cart_id IS NULL
        """
    )

    invalid_count = cursor.fetchone()[0]

    cursor.close()

    assert invalid_count == 0


# Validate that every Cart Item references an existing Product
def test_cart_items_have_valid_products(db_connection):
    cursor = db_connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM cart_items ci
        LEFT JOIN products p
            ON ci.product_id = p.product_id
        WHERE p.product_id IS NULL
        """
    )

    invalid_count = cursor.fetchone()[0]

    cursor.close()

    assert invalid_count == 0


# Validate that cart_id and item_position are unique in PostgreSQL
def test_cart_items_positions_are_unique(db_connection):
    cursor = db_connection.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT (cart_id, item_position))
        FROM cart_items
        """
    )

    total_count, unique_count = cursor.fetchone()

    cursor.close()

    assert total_count == unique_count


# Validate Cart Items field by field: Processed JSON vs PostgreSQL
def test_cart_items_data_reconciliation(processed_carts, db_connection):
    cursor = db_connection.cursor()

    cursor.execute(
        """
        SELECT
            cart_id,
            item_position,
            product_id,
            product_name,
            price,
            quantity,
            total,
            discount_percentage,
            discounted_total
        FROM cart_items
        """
    )

    database_items = cursor.fetchall()

    cursor.close()

    database_by_key = {
        (row[0], row[1]): {
            "cart_id": row[0],
            "item_position": row[1],
            "product_id": row[2],
            "product_name": row[3],
            "price": row[4],
            "quantity": row[5],
            "total": row[6],
            "discount_percentage": row[7],
            "discounted_total": row[8]
        }
        for row in database_items
    }

    for cart in processed_carts:
        cart_id = cart["cart_id"]

        for item_position, expected_item in enumerate(
            cart["products"],
            start=1
        ):
            key = (cart_id, item_position)

            assert key in database_by_key

            actual_item = database_by_key[key]

            assert actual_item["product_id"] == expected_item["product_id"]
            assert actual_item["product_name"] == expected_item["product_name"]

            assert decimal_2(actual_item["price"]) == decimal_2(
                expected_item["price"]
            )

            assert actual_item["quantity"] == expected_item["quantity"]

            assert decimal_2(actual_item["total"]) == decimal_2(
                expected_item["total"]
            )

            assert decimal_2(
                actual_item["discount_percentage"]
            ) == decimal_2(
                expected_item["discount_percentage"]
            )

            assert decimal_2(
                actual_item["discounted_total"]
            ) == decimal_2(
                expected_item["discounted_total"]
            )