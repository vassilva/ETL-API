import json

from src.load.database import get_connection


def load_users():
    # Read transformed users from the processed JSON file
    with open("data/processed/users.json", "r", encoding="utf-8") as file:
        users = json.load(file)

    # Open database connection
    connection = get_connection()
    cursor = connection.cursor()

    # Insert each processed user into PostgreSQL
    for user in users:
        cursor.execute(
            """
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
            """,
            (
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
        )

    # Confirm database transaction
    connection.commit()

    # Close database resources
    cursor.close()
    connection.close()

    print(f"Users loaded: {len(users)}")


if __name__ == "__main__":
    load_users()