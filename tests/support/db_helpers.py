"""Read-only query helpers for database validation tests."""

SAMPLE_SIZE = 10


def fetch_records(connection, query):
    """Run a SELECT and return rows as dicts keyed by column name."""
    cursor = connection.cursor()

    cursor.execute(query)

    columns = [column.name for column in cursor.description]
    records = [dict(zip(columns, row)) for row in cursor.fetchall()]

    cursor.close()

    return records


def scalar(connection, query):
    cursor = connection.cursor()

    cursor.execute(query)
    value = cursor.fetchone()[0]

    cursor.close()

    return value


def violations(connection, key_sql, from_sql):
    """
    Set-based check evaluated in the database.

    Runs 'SELECT <key_sql> AS k <from_sql>' (each returned row is one
    violation) and returns (count, sample keys). Only keys leave the
    database, never the offending values.
    """
    cursor = connection.cursor()

    cursor.execute(
        f"""
        SELECT COUNT(*), (ARRAY_AGG(k ORDER BY k))[1:{SAMPLE_SIZE}]
        FROM (SELECT {key_sql} AS k {from_sql}) violating
        """
    )

    count, keys = cursor.fetchone()

    cursor.close()

    return count, keys or []
