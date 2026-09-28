from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from utils.json_files import read_json, write_json


# Business rule: product_name = original source title + " - RP".
# Always built from the raw title (never from an already processed name),
# so re-running the ETL cannot append the suffix twice.
PRODUCT_NAME_SUFFIX = " - RP"


def load_raw_products():
    data = read_json(RAW_DATA_DIR / "products.json")

    return data["products"]


def transform_product(product):
    discounted_price = round(
        product["price"] * (1 - product["discountPercentage"] / 100),
        2
    )

    transformed_product = {
        "product_id": product["id"],
        "product_name": product["title"] + PRODUCT_NAME_SUFFIX,
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


def transform_products_data(products):
    """Pure transformation: raw products -> processed products (no I/O)."""
    return [
        transform_product(product)
        for product in products
    ]


def transform_products():
    products = load_raw_products()

    transformed_products = transform_products_data(products)

    write_json(PROCESSED_DATA_DIR / "products.json", transformed_products)

    print("Products transformed:", len(transformed_products))

    return transformed_products
