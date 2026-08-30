import json


def load_raw_products():
    with open("data/raw/products.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    return data["products"]


def transform_product(product):
    discounted_price = round(
        product["price"] * (1 - product["discountPercentage"] / 100),
        2
    )

    transformed_product = {
        "product_id": product["id"],
        "product_name": product["title"],
        "category": product["category"],
        "price": product["price"],
        "discount_percentage": product["discountPercentage"],
        "discounted_price": discounted_price,
        "rating": product["rating"],
        "stock": product["stock"],
        "brand": product.get("brand"),
        "sku": product["sku"],
        "availability_status": product["availabilityStatus"]
    }

    return transformed_product


def transform_products():
    products = load_raw_products()

    transformed_products = [
        transform_product(product)
        for product in products
    ]

    with open("data/processed/products.json", "w", encoding="utf-8") as file:
        json.dump(
            transformed_products,
            file,
            ensure_ascii=False,
            indent=4
        )

    print("Products transformed:", len(transformed_products))

    return transformed_products