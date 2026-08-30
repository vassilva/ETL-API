import json
import pytest

from load.database import get_connection


@pytest.fixture(scope="module")
def db_connection():
    connection = get_connection()

    yield connection

    connection.close()


@pytest.fixture(scope="module")
def processed_users():
    with open("data/processed/users.json", "r", encoding="utf-8") as file:
        return json.load(file)


# Validate processed Users count against PostgreSQL
def test_users_count(processed_users, db_connection):
    cursor = db_connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    database_count = cursor.fetchone()[0]

    cursor.close()

    assert database_count == len(processed_users)


# Validate that User IDs are unique in PostgreSQL
def test_users_ids_are_unique(db_connection):
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


# Validate Users field by field: Processed JSON vs PostgreSQL
def test_users_data_reconciliation(processed_users, db_connection):
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