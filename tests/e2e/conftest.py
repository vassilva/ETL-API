"""
Fixtures for the end-to-end ETL tests.

The ETL is executed through its real entry point (python src/main.py --load)
twice per session. After each run the database state is captured once, in a
read-only session, so every test asserts on a fixed snapshot regardless of
test order. The tests themselves never write to the database.
"""

import pytest

from extract.common import fetch_payload
from support.etl_e2e import RESOURCES, execute_run


@pytest.fixture(scope="session")
def source_data():
    """Complete live API payloads, fetched independently of the ETL."""
    return {resource: fetch_payload(resource) for resource in RESOURCES}


@pytest.fixture(scope="session")
def first_run(source_data):
    return execute_run()


@pytest.fixture(scope="session")
def second_run(first_run):
    """Second ETL run against the same database (idempotency)."""
    return execute_run()
