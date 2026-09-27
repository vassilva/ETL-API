import pytest

import extract.common
from extract.carts import extract_carts, fetch_carts
from extract.products import extract_products, fetch_products
from extract.users import extract_users, fetch_users
from utils.json_files import read_json


pytestmark = [pytest.mark.extract, pytest.mark.unit]


EXTRACTORS = [
    ("users", "Users", extract_users, fetch_users),
    ("products", "Products", extract_products, fetch_products),
    ("carts", "Carts", extract_carts, fetch_carts),
]


@pytest.fixture
def offline_extract(monkeypatch, tmp_path, synthetic_payload):
    """Serve synthetic payloads instead of the API and write to tmp_path."""
    monkeypatch.setattr(extract.common, "fetch_payload", synthetic_payload)
    monkeypatch.setattr(extract.common, "RAW_DATA_DIR", tmp_path)

    return tmp_path


# Validate that extract_* returns (records, total) and saves the raw payload
@pytest.mark.parametrize("resource, label, extract_fn, fetch_fn", EXTRACTORS)
def test_extract_saves_raw_payload(
    offline_extract, synthetic_payload, capsys, resource, label, extract_fn, fetch_fn
):
    expected_payload = synthetic_payload(resource)

    records, total = extract_fn()

    assert records == expected_payload[resource]
    assert total == expected_payload["total"]
    assert read_json(offline_extract / f"{resource}.json") == expected_payload
    assert capsys.readouterr().out == f"{label} extracted: {len(records)}\n"


# Validate that fetch_* returns the same contract without writing artifacts
@pytest.mark.parametrize("resource, label, extract_fn, fetch_fn", EXTRACTORS)
def test_fetch_does_not_write_artifacts(
    offline_extract, synthetic_payload, resource, label, extract_fn, fetch_fn
):
    expected_payload = synthetic_payload(resource)

    records, total = fetch_fn()

    assert records == expected_payload[resource]
    assert total == expected_payload["total"]
    assert list(offline_extract.iterdir()) == []


# Validate that an unexpected payload fails before anything is written
def test_extract_rejects_payload_without_records(monkeypatch, tmp_path):
    monkeypatch.setattr(extract.common, "fetch_payload", lambda resource: {"total": 0})
    monkeypatch.setattr(extract.common, "RAW_DATA_DIR", tmp_path)

    with pytest.raises(KeyError):
        extract_users()

    assert list(tmp_path.iterdir()) == []
