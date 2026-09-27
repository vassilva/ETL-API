from api.client import ApiClient
from config.settings import RAW_DATA_DIR
from utils.json_files import write_json


def raw_file(resource):
    return RAW_DATA_DIR / f"{resource}.json"


def fetch_payload(resource):
    """Fetch the complete API payload for a resource (no file is written)."""
    with ApiClient() as client:
        return client.get_resource(resource)


def split_payload(payload, resource):
    """Return (records, total) from a collection payload."""
    return payload[resource], payload["total"]


def fetch_resource(resource):
    """Fetch (records, total) from the API without writing any artifact."""
    return split_payload(fetch_payload(resource), resource)


def extract_resource(resource, label):
    """Fetch a resource, save the raw payload and return (records, total)."""
    payload = fetch_payload(resource)
    records, total = split_payload(payload, resource)

    write_json(raw_file(resource), payload)

    print(f"{label} extracted:", len(records))

    return records, total
