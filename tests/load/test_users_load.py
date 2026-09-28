import pytest

from support.assertions import assert_field_matches
from support.db_helpers import fetch_records, index_by


pytestmark = [pytest.mark.load, pytest.mark.database, pytest.mark.artifacts]


# Validate processed Users count against PostgreSQL
@pytest.mark.smoke
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
