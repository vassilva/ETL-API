from config.settings import PROCESSED_DATA_DIR
from database.connection import execute_for_each
from utils.json_files import read_json


UPSERT_USER_SQL = """
    INSERT INTO users (
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
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)

    ON CONFLICT (user_id) DO UPDATE SET
        first_name = EXCLUDED.first_name,
        last_name = EXCLUDED.last_name,
        full_name = EXCLUDED.full_name,
        email = EXCLUDED.email,
        phone = EXCLUDED.phone,
        city = EXCLUDED.city,
        state = EXCLUDED.state,
        country = EXCLUDED.country,
        company_name = EXCLUDED.company_name,
        department = EXCLUDED.department
"""


def user_row(user):
    return (
        user["user_id"],
        user["first_name"],
        user["last_name"],
        user["full_name"],
        user["email"],
        user["phone"],
        user["city"],
        user["state"],
        user["country"],
        user["company_name"],
        user["department"]
    )


def load_users():
    # Read transformed users from the processed JSON file
    users = read_json(PROCESSED_DATA_DIR / "users.json")

    # Upsert every user in a single transaction (rollback on any error)
    execute_for_each(UPSERT_USER_SQL, (user_row(user) for user in users))

    print(f"Users loaded: {len(users)}")


if __name__ == "__main__":
    load_users()
