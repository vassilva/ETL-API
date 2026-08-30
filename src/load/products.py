import json

from src.load.database import get_connection


def load_products():
    with open("data/processed/products.json", "r", encoding="utf-8") as file:
        products = json.load(file)

    connection = get_connection()
    cursor = connection.cursor()

    for product in products:
        cursor.execute(
            """
            INSERT INTO products (
                product_id,
                product_name,
                category,
                price,
                discount_percentage,
                discounted_price,
                rating,
                stock,
                brand,
                sku,
                availability_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)

            ON CONFLICT (product_id) DO UPDATE SET
                product_name = EXCLUDED.product_name,
                category = EXCLUDED.category,
                price = EXCLUDED.price,
                discount_percentage = EXCLUDED.discount_percentage,
                discounted_price = EXCLUDED.discounted_price,
                rating = EXCLUDED.rating,
                stock = EXCLUDED.stock,
                brand = EXCLUDED.brand,
                sku = EXCLUDED.sku,
                availability_status = EXCLUDED.availability_status
            """,
            (
                product["product_id"],
                product["product_name"],
                product["category"],
                product["price"],
                product["discount_percentage"],
                product["discounted_price"],
                product["rating"],
                product["stock"],
                product["brand"],
                product["sku"],
                product["availability_status"]
            )
        )

    connection.commit()

    cursor.close()
    connection.close()

    print(f"Products loaded: {len(products)}")


if __name__ == "__main__":
    load_products()