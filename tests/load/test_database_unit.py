"""
Offline tests for configuration, connection/transaction handling and load
modules. All database interaction is faked; nothing touches PostgreSQL.
"""

import psycopg2
import pytest

import database.connection as connection_module
import load.cart_items
import load.carts
from config.settings import ConfigurationError, Settings
from utils.json_files import write_json


pytestmark = [pytest.mark.load, pytest.mark.unit]


SYNTHETIC_DB_ENV = {
    "DB_HOST": "synthetic-host",
    "DB_PORT": "5999",
    "DB_NAME": "synthetic_db",
    "DB_USER": "synthetic-user",
    "DB_PASSWORD": "synthetic-password-value",
}

class FakeCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, statement, params=None):
        if self.connection.fail_on_execute:
            raise psycopg2.DataError("synthetic failure")

        self.connection.executed.append((statement, params))


class FakeConnection:
    def __init__(self, fail_on_execute=False, fail_on_rollback=False):
        self.fail_on_execute = fail_on_execute
        self.fail_on_rollback = fail_on_rollback
        self.executed = []
        self.session = {}
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def set_session(self, **options):
        self.session.update(options)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

        if self.fail_on_rollback:
            raise psycopg2.InterfaceError("synthetic rollback failure")

    def close(self):
        self.closed = True


@pytest.fixture
def synthetic_db_env(monkeypatch):
    for name, value in SYNTHETIC_DB_ENV.items():
        monkeypatch.setenv(name, value)

    settings = Settings(
        api_base_url="https://api.example.test",
        api_timeout=5,
        db_connect_timeout=7
    )
    monkeypatch.setattr(connection_module, "get_settings", lambda: settings)

    return settings


@pytest.fixture
def fake_connect(monkeypatch, synthetic_db_env):
    """Replace psycopg2.connect; returns the list of created fake connections."""
    connections = []

    def connect(**kwargs):
        connection = FakeConnection()
        connection.kwargs = kwargs
        connections.append(connection)
        return connection

    monkeypatch.setattr(connection_module.psycopg2, "connect", connect)

    return connections


# Settings

# Validate that missing DB variables are reported by name only
def test_database_settings_report_missing_variables(synthetic_db_env, monkeypatch):
    monkeypatch.delenv("DB_PASSWORD")
    monkeypatch.setenv("DB_HOST", "")

    with pytest.raises(ConfigurationError) as error:
        synthetic_db_env.database()

    message = str(error.value)

    assert "DB_HOST" in message
    assert "DB_PASSWORD" in message
    assert "synthetic-user" not in message
    assert "synthetic_db" not in message


# Validate that connection details never appear in repr/str
def test_database_settings_repr_hides_connection_details(synthetic_db_env):
    database = synthetic_db_env.database()

    for value in SYNTHETIC_DB_ENV.values():
        assert value not in repr(database)
        assert value not in str(database)


# Connection

# Validate that the connection uses centralized settings and a timeout
def test_get_connection_uses_settings(fake_connect):
    connection_module.get_connection()

    assert fake_connect[0].kwargs == {
        "host": "synthetic-host",
        "port": "5999",
        "dbname": "synthetic_db",
        "user": "synthetic-user",
        "password": "synthetic-password-value",
        "connect_timeout": 7
    }
    assert fake_connect[0].session == {}


# Validate that read_only=True enforces a read-only session
def test_get_connection_read_only(fake_connect):
    connection_module.get_connection(read_only=True)

    assert fake_connect[0].session == {"readonly": True}


# Validate that connection failures do not expose driver details
def test_connection_error_is_sanitized(monkeypatch, synthetic_db_env):
    def failing_connect(**kwargs):
        raise psycopg2.OperationalError(
            'password authentication failed for user "synthetic-user"'
        )

    monkeypatch.setattr(connection_module.psycopg2, "connect", failing_connect)

    with pytest.raises(connection_module.DatabaseConnectionError) as error:
        connection_module.get_connection()

    assert "synthetic-user" not in str(error.value)
    assert "OperationalError" in str(error.value)
    assert error.value.__suppress_context__ is True


# Transactions

# Validate commit and close on success
def test_transaction_commits_and_closes(fake_connect):
    with connection_module.transaction() as cursor:
        cursor.execute("SELECT 1")

    connection = fake_connect[0]

    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True


# Validate rollback, close and re-raise on error
def test_transaction_rolls_back_on_error(fake_connect):
    with pytest.raises(RuntimeError):
        with connection_module.transaction():
            raise RuntimeError("synthetic")

    connection = fake_connect[0]

    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True


# Validate that a failing rollback does not hide the original error
def test_transaction_rollback_failure_keeps_original_error(monkeypatch, synthetic_db_env):
    connection = FakeConnection(fail_on_execute=True, fail_on_rollback=True)
    monkeypatch.setattr(connection_module.psycopg2, "connect", lambda **kwargs: connection)

    with pytest.raises(psycopg2.DataError):
        connection_module.execute_for_each("SELECT %s", [(1,)])

    assert connection.closed is True


# Validate that execute_for_each runs one statement per row in one transaction
def test_execute_for_each_counts_rows(fake_connect):
    executed = connection_module.execute_for_each("SELECT %s", [(1,), (2,), (3,)])

    connection = fake_connect[0]

    assert executed == 3
    assert connection.executed == [("SELECT %s", (1,)), ("SELECT %s", (2,)), ("SELECT %s", (3,))]
    assert connection.committed is True
    assert len(fake_connect) == 1


# Load modules (row mapping)

# UPSERT structure, non-destructive SQL, row/column alignment and placeholder
# counts: see test_load_contract_unit.py

# Validate cart item rows: positions restart at 1 for every cart
def test_cart_item_rows_positions():
    product = {
        "product_id": 1, "product_name": "n", "price": 1, "quantity": 1,
        "total": 1, "discount_percentage": 0, "discounted_total": 1
    }
    carts = [
        {"cart_id": 10, "products": [product, product]},
        {"cart_id": 20, "products": [product]},
    ]

    rows = list(load.cart_items.cart_item_rows(carts))

    assert [(row[0], row[1]) for row in rows] == [(10, 1), (10, 2), (20, 1)]
    assert all(
        load.cart_items.UPSERT_CART_ITEM_SQL.count("%s") == len(row)
        for row in rows
    )


# Validate that load_*() read processed files and delegate to execute_for_each
@pytest.mark.parametrize(
    "module, loader, statement, file_name, records, expected_rows",
    [
        (load.carts, load.carts.load_carts, load.carts.UPSERT_CART_SQL, "carts.json",
         [{"cart_id": 1, "user_id": 2, "total": 3, "discounted_total": 4,
           "total_products": 5, "total_quantity": 6, "products": []}],
         [(1, 2, 3, 4, 5, 6)]),
        (load.cart_items, load.cart_items.load_cart_items,
         load.cart_items.UPSERT_CART_ITEM_SQL, "carts.json",
         [{"cart_id": 1, "products": [{
             "product_id": 7, "product_name": "n", "price": 1, "quantity": 2,
             "total": 2, "discount_percentage": 0, "discounted_total": 2}]}],
         [(1, 1, 7, "n", 1, 2, 2, 0, 2)]),
    ]
)
def test_loader_delegates_to_execute_for_each(
    monkeypatch, tmp_path, module, loader, statement, file_name, records, expected_rows
):
    calls = []

    def fake_execute_for_each(sql, rows):
        rows = list(rows)
        calls.append((sql, rows))
        return len(rows)

    write_json(tmp_path / file_name, records)
    monkeypatch.setattr(module, "PROCESSED_DATA_DIR", tmp_path)
    monkeypatch.setattr(module, "execute_for_each", fake_execute_for_each)

    loader()

    assert calls == [(statement, expected_rows)]
