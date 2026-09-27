import pytest
from decimal import Decimal

from support.assertions import assert_field_matches
from support.db_helpers import fetch_records, index_by


pytestmark = [pytest.mark.load, pytest.mark.database, pytest.mark.artifacts]


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
    database_users = fetch_records(
        db_connection,
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

    database_by_id = index_by(database_users, "user_id")

    for expected_user in processed_users:
        user_id = expected_user["user_id"]

        assert user_id in database_by_id

        actual_user = database_by_id[user_id]

        assert_field_matches(
            actual_user["first_name"],
            expected_user["first_name"],
            entity="user",
            record_id=user_id,
            field="first_name"
        )
        assert_field_matches(
            actual_user["last_name"],
            expected_user["last_name"],
            entity="user",
            record_id=user_id,
            field="last_name"
        )
        assert_field_matches(
            actual_user["full_name"],
            expected_user["full_name"],
            entity="user",
            record_id=user_id,
            field="full_name"
        )
        assert_field_matches(
            actual_user["email"],
            expected_user["email"],
            entity="user",
            record_id=user_id,
            field="email"
        )
        assert_field_matches(
            actual_user["phone"],
            expected_user["phone"],
            entity="user",
            record_id=user_id,
            field="phone"
        )
        assert_field_matches(
            actual_user["city"],
            expected_user["city"],
            entity="user",
            record_id=user_id,
            field="city"
        )
        assert_field_matches(
            actual_user["state"],
            expected_user["state"],
            entity="user",
            record_id=user_id,
            field="state"
        )
        assert_field_matches(
            actual_user["country"],
            expected_user["country"],
            entity="user",
            record_id=user_id,
            field="country"
        )
        assert_field_matches(
            actual_user["company_name"],
            expected_user["company_name"],
            entity="user",
            record_id=user_id,
            field="company_name"
        )
        assert_field_matches(
            actual_user["department"],
            expected_user["department"],
            entity="user",
            record_id=user_id,
            field="department"
        )


# Products data reconciliation

def test_products_data_reconciliation(processed_products, db_connection):
    """
    Validate Products field by field:
    Processed JSON vs PostgreSQL.
    """
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