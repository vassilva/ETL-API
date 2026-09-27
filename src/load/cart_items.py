from config.settings import PROCESSED_DATA_DIR
from database.connection import execute_for_each
from utils.json_files import read_json


UPSERT_CART_ITEM_SQL = """
    INSERT INTO cart_items (
        cart_id,
        item_position,
        product_id,
        product_name,
        price,
        quantity,
        total,
        discount_percentage,
        discounted_total
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)

    ON CONFLICT (cart_id, item_position) DO UPDATE SET
        product_id = EXCLUDED.product_id,
        product_name = EXCLUDED.product_name,
        price = EXCLUDED.price,
        quantity = EXCLUDED.quantity,
        total = EXCLUDED.total,
        discount_percentage = EXCLUDED.discount_percentage,
        discounted_total = EXCLUDED.discounted_total
"""


def cart_item_rows(carts):
    """Yield one row per cart product; item_position starts at 1 per cart."""
    for cart in carts:
        for item_position, product in enumerate(cart["products"], start=1):
            yield (
                cart["cart_id"],
                item_position,
                product["product_id"],
                product["product_name"],
                product["price"],
                product["quantity"],
                product["total"],
                product["discount_percentage"],
                product["discounted_total"]
            )


def load_cart_items():
    carts = read_json(PROCESSED_DATA_DIR / "carts.json")

    total_items = execute_for_each(UPSERT_CART_ITEM_SQL, cart_item_rows(carts))

    print(f"Cart items loaded: {total_items}")


if __name__ == "__main__":
    load_cart_items()
