from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from utils.json_files import read_json, write_json


def load_raw_carts():
    data = read_json(RAW_DATA_DIR / "carts.json")

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


def transform_carts_data(carts):
    """Pure transformation: raw carts -> processed carts (no I/O)."""
    return [
        transform_cart(cart)
        for cart in carts
    ]


def transform_carts():
    carts = load_raw_carts()

    transformed_carts = transform_carts_data(carts)

    write_json(PROCESSED_DATA_DIR / "carts.json", transformed_carts)

    print("Carts transformed:", len(transformed_carts))

    return transformed_carts
