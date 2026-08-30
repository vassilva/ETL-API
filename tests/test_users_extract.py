import pytest
from extract.users import extract_users


@pytest.fixture(scope="module")
def users_data():
    return extract_users()


# Validate that the extraction returns user data
def test_extract_users_returns_data(users_data):
    users, total = users_data

    assert users is not None
    assert len(users) > 0


# Validate that the number of extracted users matches the total reported by the API
def test_extract_users_count(users_data):
    users, total = users_data

    assert len(users) == total


# Validate that every extracted user has a non-null ID
def test_users_have_id(users_data):
    users, total = users_data

    for user in users:
        assert user["id"] is not None


# Validate that there are no duplicate user IDs
def test_users_ids_are_unique(users_data):
    users, total = users_data

    ids = [user["id"] for user in users]

    assert len(ids) == len(set(ids))