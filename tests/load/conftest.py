import pytest

from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from database.connection import get_connection
from support.artifacts import read_artifact


@pytest.fixture(scope="session")
def db_connection():
    """
    One PostgreSQL connection for all database validation tests.

    The session is read-only: the server rejects any write statement.
    """
    connection = get_connection(read_only=True)

    yield connection

    connection.close()


# Database tests reconcile PostgreSQL against the runtime artifacts in
# data/raw and data/processed (exactly what the last real ETL run extracted
# and loaded), not against the versioned snapshot used by offline tests.

@pytest.fixture(scope="session")
def raw_products():
    """Source products exactly as extracted by the last real ETL run."""
    return read_artifact(RAW_DATA_DIR / "products.json")["products"]


@pytest.fixture(scope="session")
def processed_users():
    return read_artifact(PROCESSED_DATA_DIR / "users.json")


@pytest.fixture(scope="session")
def processed_products():
    return read_artifact(PROCESSED_DATA_DIR / "products.json")


@pytest.fixture(scope="session")
def processed_carts():
    return read_artifact(PROCESSED_DATA_DIR / "carts.json")
