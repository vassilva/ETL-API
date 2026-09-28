"""Read-only query helpers for database validation tests."""


def fetch_records(connection, query):
    """Run a SELECT and return rows as dicts keyed by column name."""
    cursor = connection.cursor()

    cursor.execute(query)

    columns = [column.name for column in cursor.description]
    records = [dict(zip(columns, row)) for row in cursor.fetchall()]

    cursor.close()

    return records


def index_by(records, *key_fields):
    """Index records by one field, or by a tuple of several fields."""
    if len(key_fields) == 1:
        return {record[key_fields[0]]: record for record in records}

    return {
        tuple(record[field] for field in key_fields): record
        for record in records
    }
