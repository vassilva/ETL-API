import pytest

from database.connection import get_connection


@pytest.fixture(scope="session")
def db_connection():
    """
    One PostgreSQL connection for all database validation tests.

    The session is read-only: the server rejects any write statement.
    """
    connection = get_connection(read_only=True)

    yield connection

    connection.close()
