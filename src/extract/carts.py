from extract.common import extract_resource, fetch_resource

RESOURCE = "carts"


def fetch_carts():
    """Fetch carts from the API without writing data/raw (used by tests)."""
    return fetch_resource(RESOURCE)


def extract_carts():
    """Fetch carts, save data/raw/carts.json and return (carts, total)."""
    return extract_resource(RESOURCE, "Carts")
