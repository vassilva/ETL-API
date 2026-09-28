from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from utils.json_files import read_json, write_json


def load_raw_users():
    data = read_json(RAW_DATA_DIR / "users.json")

    return data["users"]


def transform_user(user):
    transformed_user = {
        "user_id": user["id"],
        "first_name": user["firstName"],
        "last_name": user["lastName"],
        "full_name": f'{user["firstName"]} {user["lastName"]}',
        "email": user["email"],
        "phone": user["phone"],
        "city": user["address"]["city"],
        "state": user["address"]["state"],
        "country": user["address"]["country"],
        "company_name": user["company"]["name"],
        "department": user["company"]["department"]
    }

    return transformed_user


def transform_users_data(users):
    """Pure transformation: raw users -> processed users (no I/O)."""
    return [
        transform_user(user)
        for user in users
    ]


def transform_users():
    users = load_raw_users()

    transformed_users = transform_users_data(users)

    write_json(PROCESSED_DATA_DIR / "users.json", transformed_users)

    print("Users transformed:", len(transformed_users))

    return transformed_users
