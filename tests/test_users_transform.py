import pytest

from transform.users import load_raw_users
from transform.users import transform_users


@pytest.fixture(scope="module")
def users_transform_data():
    raw_users = load_raw_users()
    processed_users = transform_users()

    return raw_users, processed_users


# Validate that the number of processed users matches the number of raw users
def test_users_transform_count(users_transform_data):
    raw_users, processed_users = users_transform_data

    assert len(processed_users) == len(raw_users)


# Validate that raw user ID is correctly mapped to processed user_id
def test_users_id_mapping(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        assert processed_user["user_id"] == raw_user["id"]


# Validate that firstName is correctly mapped to first_name
def test_users_first_name_mapping(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        assert processed_user["first_name"] == raw_user["firstName"]


# Validate that lastName is correctly mapped to last_name
def test_users_last_name_mapping(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        assert processed_user["last_name"] == raw_user["lastName"]


# Validate that full_name is correctly derived from firstName and lastName
def test_users_full_name_transformation(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        expected_full_name = f'{raw_user["firstName"]} {raw_user["lastName"]}'

        assert processed_user["full_name"] == expected_full_name


# Validate that email is correctly mapped
def test_users_email_mapping(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        assert processed_user["email"] == raw_user["email"]


# Validate that phone is correctly mapped
def test_users_phone_mapping(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        assert processed_user["phone"] == raw_user["phone"]


# Validate that nested address.city is correctly flattened to city
def test_users_city_mapping(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        assert processed_user["city"] == raw_user["address"]["city"]


# Validate that nested address.state is correctly flattened to state
def test_users_state_mapping(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        assert processed_user["state"] == raw_user["address"]["state"]


# Validate that nested address.country is correctly flattened to country
def test_users_country_mapping(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        assert processed_user["country"] == raw_user["address"]["country"]


# Validate that nested company.name is correctly flattened to company_name
def test_users_company_mapping(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        assert processed_user["company_name"] == raw_user["company"]["name"]


# Validate that nested company.department is correctly flattened to department
def test_users_department_mapping(users_transform_data):
    raw_users, processed_users = users_transform_data

    for raw_user, processed_user in zip(raw_users, processed_users):
        assert processed_user["department"] == raw_user["company"]["department"]


# Validate that processed user IDs remain unique
def test_processed_users_ids_are_unique(users_transform_data):
    raw_users, processed_users = users_transform_data

    ids = [user["user_id"] for user in processed_users]

    assert len(ids) == len(set(ids))