import json
import pytest
from decimal import Decimal

from load.database import get_connection


@pytest.fixture(scope="module")
def db_connection():
    connection = get_connection()

    yield connection

    connection.close()


@pytest.fixture(scope="module")
def processed_carts():
    with open("data/processed/carts.json", "r", encoding="utf-8") as file:
        return json.load(file)


# Validate processed Carts count against PostgreSQL
def test_carts_count(processed_carts, db_connection):
    cursor = db_connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM carts")
    database_count = cursor.fetchone()[0]

    cursor.close()

    assert database_count == len(processed_carts)


# Validate that Cart IDs are unique in PostgreSQL
def test_carts_ids_are_unique(db_connection):
    cursor = db_connection.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT cart_id)
        FROM carts
        """
    )

    total_count, unique_count = cursor.fetchone()

    cursor.close()

    assert total_count == unique_count


# Validate that every Cart references an existing User
def test_carts_have_valid_users(db_connection):
    cursor = db_connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM carts c
        LEFT JOIN users u
            ON c.user_id = u.user_id
        WHERE u.user_id IS NULL
        """
    )

    invalid_count = cursor.fetchone()[0]

    cursor.close()

    assert invalid_count == 0


# Validate Carts field by field: Processed JSON vs PostgreSQL
def test_carts_data_reconciliation(processed_carts, db_connection):
    cursor = db_connection.cursor()

    cursor.execute(
        """
        SELECT
            cart_id,
            user_id,
            total,
            discounted_total,
            total_products,
            total_quantity
        FROM carts
        """
    )

    database_carts = cursor.fetchall()

    cursor.close()

    database_by_id = {
        row[0]: {
            "cart_id": row[0],
            "user_id": row[1],
            "total": row[2],
            "discounted_total": row[3],
            "total_products": row[4],
            "total_quantity": row[5]
        }
        for row in database_carts
    }

    for expected_cart in processed_carts:
        cart_id = expected_cart["cart_id"]

        assert cart_id in database_by_id

        actual_cart = database_by_id[cart_id]

        assert actual_cart["user_id"] == expected_cart["user_id"]

        assert actual_cart["total"] == Decimal(
            str(expected_cart["total"])
        )

        assert actual_cart["discounted_total"] == Decimal(
            str(expected_cart["discounted_total"])
        )

        assert (
            actual_cart["total_products"]
            == expected_cart["total_products"]
        )

        assert (
            actual_cart["total_quantity"]
            == expected_cart["total_quantity"]
        )