import json

from src.load.database import get_connection


def load_carts():
    # Read transformed carts from the processed JSON file
    with open("data/processed/carts.json", "r", encoding="utf-8") as file:
        carts = json.load(file)

    # Open database connection
    connection = get_connection()
    cursor = connection.cursor()

    # Insert each cart into PostgreSQL
    for cart in carts:
        cursor.execute(
            """
            INSERT INTO carts (
                cart_id,
                user_id,
                total,
                discounted_total,
                total_products,
                total_quantity
            )
            VALUES (%s, %s, %s, %s, %s, %s)

            ON CONFLICT (cart_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                total = EXCLUDED.total,
                discounted_total = EXCLUDED.discounted_total,
                total_products = EXCLUDED.total_products,
                total_quantity = EXCLUDED.total_quantity
            """,
            (
                cart["cart_id"],
                cart["user_id"],
                cart["total"],
                cart["discounted_total"],
                cart["total_products"],
                cart["total_quantity"]
            )
        )

    # Confirm database transaction
    connection.commit()

    # Close database resources
    cursor.close()
    connection.close()

    print(f"Carts loaded: {len(carts)}")


if __name__ == "__main__":
    load_carts()