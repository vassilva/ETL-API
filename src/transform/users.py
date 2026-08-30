import json


def load_raw_users():
    with open("data/raw/users.json", "r", encoding="utf-8") as file:
        data = json.load(file)

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


def transform_users():
    users = load_raw_users()

    transformed_users = [
        transform_user(user)
        for user in users
    ]

    with open("data/processed/users.json", "w", encoding="utf-8") as file:
        json.dump(
            transformed_users,
            file,
            ensure_ascii=False,
            indent=4
        )

    print("Users transformed:", len(transformed_users))

    return transformed_users