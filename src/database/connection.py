"""
Centralized PostgreSQL connection and transaction handling.

Table-specific SQL lives in the load modules; this module only manages
connections, transactions, rollback and cleanup.
"""

from contextlib import contextmanager

import psycopg2

from config.settings import get_settings


class DatabaseConnectionError(RuntimeError):
    """Raised when a connection cannot be opened (details are not exposed)."""


def get_connection(read_only=False):
    """
    Open a new PostgreSQL connection.

    read_only=True makes the server reject any write in this session.
    """
    database = get_settings().database()

    try:
        connection = psycopg2.connect(
            host=database.host,
            port=database.port,
            dbname=database.name,
            user=database.user,
            password=database.password,
            connect_timeout=database.connect_timeout
        )
    except psycopg2.Error as error:
        # The driver message may contain host or user names; report only the
        # error type and suppress the original exception chain.
        raise DatabaseConnectionError(
            f"Could not connect to the configured database "
            f"({type(error).__name__}). Check the DB_* settings."
        ) from None

    if read_only:
        connection.set_session(readonly=True)

    return connection


@contextmanager
def transaction(read_only=False):
    """
    Yield a cursor inside a single transaction.

    Commits on success, rolls back on any error and always closes the
    connection.
    """
    connection = get_connection(read_only=read_only)

    try:
        with connection.cursor() as cursor:
            yield cursor

        connection.commit()
    except BaseException:
        try:
            connection.rollback()
        except psycopg2.Error:
            # Never let a failed rollback hide the original error.
            pass

        raise
    finally:
        connection.close()


def execute_for_each(statement, rows):
    """
    Execute one static, parameterized statement per row in one transaction.

    Returns the number of executed rows.
    """
    executed = 0

    with transaction() as cursor:
        for params in rows:
            cursor.execute(statement, params)
            executed += 1

    return executed


if __name__ == "__main__":
    get_connection(read_only=True).close()

    print("Database connection successful")
