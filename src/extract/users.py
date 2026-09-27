from extract.common import extract_resource, fetch_resource

RESOURCE = "users"


def fetch_users():
    """Fetch users from the API without writing data/raw (used by tests)."""
    return fetch_resource(RESOURCE)


def extract_users():
    """Fetch users, save data/raw/users.json and return (users, total)."""
    return extract_resource(RESOURCE, "Users")
