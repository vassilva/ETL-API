from config.settings import PROCESSED_DATA_DIR
from database.connection import execute_for_each
from utils.json_files import read_json


UPSERT_CART_SQL = """
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
"""


def cart_row(cart):
    return (
        cart["cart_id"],
        cart["user_id"],
        cart["total"],
        cart["discounted_total"],
        cart["total_products"],
        cart["total_quantity"]
    )


def load_carts():
    # Read transformed carts from the processed JSON file
    carts = read_json(PROCESSED_DATA_DIR / "carts.json")

    # Upsert every cart in a single transaction (rollback on any error)
    execute_for_each(UPSERT_CART_SQL, (cart_row(cart) for cart in carts))

    print(f"Carts loaded: {len(carts)}")


if __name__ == "__main__":
    load_carts()
