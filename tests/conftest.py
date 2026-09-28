"""
Shared fixtures and hooks for the whole test suite.

Stage and dependency markers are declared per module (pytestmark). Two
markers are derived here so they can never drift out of sync:

- regression: every collected test
- integration: every test marked live_api or database
"""

import json
from pathlib import Path

import pytest

from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from support.artifacts import read_artifact


SYNTHETIC_FIXTURES_DIR = Path(__file__).parent / "fixtures"


EXTERNAL_DEPENDENCY_MARKERS = ("live_api", "database")


# tryfirst: markers must exist before '-m' deselection runs
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.regression)

        if any(item.get_closest_marker(name) for name in EXTERNAL_DEPENDENCY_MARKERS):
            item.add_marker(pytest.mark.integration)


# Synthetic test data (tests/fixtures) — deterministic, no real data

@pytest.fixture
def synthetic_payload():
    """Return a fresh copy of a synthetic source payload by resource name."""
    def load(resource):
        path = SYNTHETIC_FIXTURES_DIR / f"{resource}_sample.json"

        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    return load


# Generated pipeline artifacts (read-only; produced by 'python src/main.py')

@pytest.fixture(scope="session")
def raw_users():
    return read_artifact(RAW_DATA_DIR / "users.json")["users"]


@pytest.fixture(scope="session")
def raw_products():
    return read_artifact(RAW_DATA_DIR / "products.json")["products"]


@pytest.fixture(scope="session")
def raw_carts():
    return read_artifact(RAW_DATA_DIR / "carts.json")["carts"]


@pytest.fixture(scope="session")
def processed_users():
    return read_artifact(PROCESSED_DATA_DIR / "users.json")


@pytest.fixture(scope="session")
def processed_products():
    return read_artifact(PROCESSED_DATA_DIR / "products.json")


@pytest.fixture(scope="session")
def processed_carts():
    return read_artifact(PROCESSED_DATA_DIR / "carts.json")
