import json
import pytest
from decimal import Decimal

from load.database import get_connection


# Fixtures

@pytest.fixture(scope="module")
def db_connection():
    """
    Create one PostgreSQL connection for all Load tests.
    """
    connection = get_connection()

    yield connection

    connection.close()


@pytest.fixture(scope="module")
def processed_users():
    """
    Read transformed Users data from the processed JSON file.
    """
    with open("data/processed/users.json", "r", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture(scope="module")
def processed_products():
    """
    Read transformed Products data from the processed JSON file.
    """
    with open("data/processed/products.json", "r", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture(scope="module")
def processed_carts():
    """
    Read transformed Carts data from the processed JSON file.
    """
    with open("data/processed/carts.json", "r", encoding="utf-8") as file:
        return json.load(file)


# Count reconciliation

def test_users_count(processed_users, db_connection):
    """
    Validate processed Users count against PostgreSQL.
    """
    cursor = db_connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    database_count = cursor.fetchone()[0]

    cursor.close()

    assert database_count == len(processed_users)


def test_products_count(processed_products, db_connection):
    """
    Validate processed Products count against PostgreSQL.
    """
    cursor = db_connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM products")
    database_count = cursor.fetchone()[0]

    cursor.close()

    assert database_count == len(processed_products)


def test_carts_count(processed_carts, db_connection):
    """
    Validate processed Carts count against PostgreSQL.
    """
    cursor = db_connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM carts")
    database_count = cursor.fetchone()[0]

    cursor.close()

    assert database_count == len(processed_carts)


def test_cart_items_count(processed_carts, db_connection):
    """
    Validate total Cart Items count against PostgreSQL.
    """
    expected_count = sum(
        len(cart["products"])
        for cart in processed_carts
    )

    cursor = db_connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM cart_items")
    database_count = cursor.fetchone()[0]

    cursor.close()

    assert database_count == expected_count


# Primary key and uniqueness validation

def test_users_ids_are_unique(db_connection):
    """
    Validate that User IDs are unique in PostgreSQL.
    """
    cursor = db_connection.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT user_id)
        FROM users
        """
    )

    total_count, unique_count = cursor.fetchone()

    cursor.close()

    assert total_count == unique_count


def test_products_ids_are_unique(db_connection):
    """
    Validate that Product IDs are unique in PostgreSQL.
    """
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


def test_carts_ids_are_unique(db_connection):
    """
    Validate that Cart IDs are unique in PostgreSQL.
    """
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


# Foreign key and referential integrity validation

def test_carts_have_valid_users(db_connection):
    """
    Validate that every Cart references an existing User.
    """
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


def test_cart_items_have_valid_carts(db_connection):
    """
    Validate that every Cart Item references an existing Cart.
    """
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


def test_cart_items_have_valid_products(db_connection):
    """
    Validate that every Cart Item references an existing Product.
    """
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


# Users data reconciliation

def test_users_data_reconciliation(processed_users, db_connection):
    """
    Validate Users field by field:
    Processed JSON vs PostgreSQL.
    """
    cursor = db_connection.cursor()

    cursor.execute(
        """
        SELECT
            user_id,
            first_name,
            last_name,
            full_name,
            email,
            phone,
            city,
            state,
            country,
            company_name,
            department
        FROM users
        """
    )

    database_users = cursor.fetchall()

    cursor.close()

    database_by_id = {
        row[0]: {
            "user_id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "full_name": row[3],
            "email": row[4],
            "phone": row[5],
            "city": row[6],
            "state": row[7],
            "country": row[8],
            "company_name": row[9],
            "department": row[10]
        }
        for row in database_users
    }

    for expected_user in processed_users:
        user_id = expected_user["user_id"]

        assert user_id in database_by_id

        actual_user = database_by_id[user_id]

        assert actual_user["first_name"] == expected_user["first_name"]
        assert actual_user["last_name"] == expected_user["last_name"]
        assert actual_user["full_name"] == expected_user["full_name"]
        assert actual_user["email"] == expected_user["email"]
        assert actual_user["phone"] == expected_user["phone"]
        assert actual_user["city"] == expected_user["city"]
        assert actual_user["state"] == expected_user["state"]
        assert actual_user["country"] == expected_user["country"]
        assert actual_user["company_name"] == expected_user["company_name"]
        assert actual_user["department"] == expected_user["department"]


# Products data reconciliation

def test_products_data_reconciliation(processed_products, db_connection):
    """
    Validate Products field by field:
    Processed JSON vs PostgreSQL.
    """
    cursor = db_connection.cursor()

    cursor.execute(
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

    database_products = cursor.fetchall()

    cursor.close()

    database_by_id = {
        row[0]: {
            "product_id": row[0],
            "product_name": row[1],
            "category": row[2],
            "price": row[3],
            "discount_percentage": row[4],
            "discounted_price": row[5],
            "rating": row[6],
            "stock": row[7],
            "brand": row[8],
            "sku": row[9],
            "availability_status": row[10]
        }
        for row in database_products
    }

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