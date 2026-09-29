"""
Load freshness baseline (read-only).

Captures the PostgreSQL row version (xmin) of every target row BEFORE the
Load, so tests can prove afterwards that the Load actually wrote every
expected row, even when the database already held identical data.

What a changed xmin proves: a new row version of that key was committed
after the baseline (an INSERT, or the UPDATE branch of the UPSERT). It is a
technical signal, never a business value, and it does not prove who wrote
the row: another process loading the same database in between (e.g. a
concurrent build) would also change it. Values are verified separately by
the reconciliation tests.

Run before the Load, from the project root, with src and tests on the path
(Windows: set PYTHONPATH=src;tests):

    python -m support.load_freshness
"""

from datetime import datetime, timezone

from config.settings import DATA_DIR
from database.connection import transaction
from utils.json_files import write_json


BASELINE_FILE = DATA_DIR / "state" / "load_baseline.json"

# Business key rendered as text (JSON object keys must be strings)
KEY_SQL = {
    "users": "user_id::text",
    "products": "product_id::text",
    "carts": "cart_id::text",
    "cart_items": "cart_id::text || ':' || item_position::text",
}


def row_versions(cursor, table):
    """{business key as text: xmin as text} for every row of the table."""
    cursor.execute(f"SELECT {KEY_SQL[table]}, xmin::text FROM {table}")

    return dict(cursor.fetchall())


def capture():
    with transaction(read_only=True) as cursor:
        versions = {table: row_versions(cursor, table) for table in KEY_SQL}

    write_json(BASELINE_FILE, {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "row_versions": versions,
    })

    counts = ", ".join(f"{table}={len(rows)}" for table, rows in versions.items())
    print(f"Load baseline captured: {counts}")


if __name__ == "__main__":
    capture()
