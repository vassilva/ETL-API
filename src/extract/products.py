from extract.common import extract_resource, fetch_resource

RESOURCE = "products"


def fetch_products():
    """Fetch products from the API without writing data/raw (used by tests)."""
    return fetch_resource(RESOURCE)


def extract_products():
    """Fetch products, save data/raw/products.json and return (products, total)."""
    return extract_resource(RESOURCE, "Products")
