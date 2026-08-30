import json


def load_raw_carts():
    with open("data/raw/carts.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    return data["carts"]


def transform_cart_product(product):
    transformed_product = {
        "product_id": product["id"],
        "product_name": product["title"],
        "price": product["price"],
        "quantity": product["quantity"],
        "total": product["total"],
        "discount_percentage": product["discountPercentage"],
        "discounted_total": product["discountedTotal"]
    }

    return transformed_product


def transform_cart(cart):
    transformed_products = [
        transform_cart_product(product)
        for product in cart["products"]
    ]

    transformed_cart = {
        "cart_id": cart["id"],
        "user_id": cart["userId"],
        "total": cart["total"],
        "discounted_total": cart["discountedTotal"],
        "total_products": cart["totalProducts"],
        "total_quantity": cart["totalQuantity"],
        "products": transformed_products
    }

    return transformed_cart


def transform_carts():
    carts = load_raw_carts()

    transformed_carts = [
        transform_cart(cart)
        for cart in carts
    ]

    with open("data/processed/carts.json", "w", encoding="utf-8") as file:
        json.dump(
            transformed_carts,
            file,
            ensure_ascii=False,
            indent=4
        )

    print("Carts transformed:", len(transformed_carts))

    return transformed_carts