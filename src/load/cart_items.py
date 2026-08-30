import json

from src.load.database import get_connection


def load_cart_items():
    with open("data/processed/carts.json", "r", encoding="utf-8") as file:
        carts = json.load(file)

    connection = get_connection()
    cursor = connection.cursor()

    total_items = 0

    for cart in carts:
        for item_position, product in enumerate(cart["products"], start=1):
            cursor.execute(
                """
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
                """,
                (
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
            )

            total_items += 1

    connection.commit()

    cursor.close()
    connection.close()

    print(f"Cart items loaded: {total_items}")


if __name__ == "__main__":
    load_cart_items()