"""
End-to-end ETL helpers: run the real pipeline and capture PostgreSQL state.

Every query here is a read-only SELECT executed in a read-only session.
"""

import subprocess
import sys
import time

import pytest

from config.settings import PROCESSED_DATA_DIR, PROJECT_ROOT, RAW_DATA_DIR
from database.connection import transaction
from support.db_helpers import fetch_records
from utils.json_files import read_json


RESOURCES = ("users", "products", "carts")

ETL_TIMEOUT_SECONDS = 600

# Business key(s) per table, used to order and index rows
TABLE_KEYS = {
    "users": ("user_id",),
    "products": ("product_id",),
    "carts": ("cart_id",),
    "cart_items": ("cart_id", "item_position"),
}

# Unique keys: primary keys plus the business keys of the source data
UNIQUE_KEYS = {
    "users.user_id": ("users", "user_id"),
    "users.email": ("users", "email"),
    "products.product_id": ("products", "product_id"),
    "products.sku": ("products", "sku"),
    "carts.cart_id": ("carts", "cart_id"),
    "cart_items.cart_item_id": ("cart_items", "cart_item_id"),
    "cart_items.(cart_id, item_position)": ("cart_items", "(cart_id, item_position)"),
}

FOREIGN_KEYS = {
    "carts.user_id -> users": ("carts", "user_id", "users", "user_id"),
    "cart_items.cart_id -> carts": ("cart_items", "cart_id", "carts", "cart_id"),
    "cart_items.product_id -> products": (
        "cart_items", "product_id", "products", "product_id"
    ),
}

# Columns that must never be NULL after a load (products.brand is optional
# in the source data and intentionally absent here)
MANDATORY_COLUMNS = {
    "users": (
        "first_name", "last_name", "full_name", "email", "phone", "city",
        "state", "country", "company_name", "department"
    ),
    "products": (
        "product_name", "category", "price", "discount_percentage",
        "discounted_price", "rating", "stock", "sku", "availability_status"
    ),
    "carts": ("total", "discounted_total", "total_products", "total_quantity"),
    "cart_items": (
        "product_name", "price", "quantity", "total", "discount_percentage",
        "discounted_total"
    ),
}

# Each query counts the rows that VIOLATE the rule
BUSINESS_RULES = {
    "users.full_name = first_name + last_name": """
        SELECT COUNT(*) FROM users
        WHERE full_name <> first_name || ' ' || last_name
    """,
    "users.email has a valid format": r"""
        SELECT COUNT(*) FROM users
        WHERE email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'
    """,
    "products.product_name ends with exactly one ' - RP'": """
        SELECT COUNT(*) FROM products
        WHERE product_name NOT LIKE '% - RP'
           OR product_name LIKE '% - RP - RP'
    """,
    "products.price > 0": """
        SELECT COUNT(*) FROM products WHERE price <= 0
    """,
    "products.discount_percentage between 0 and 100": """
        SELECT COUNT(*) FROM products
        WHERE discount_percentage NOT BETWEEN 0 AND 100
    """,
    "products.rating between 0 and 5": """
        SELECT COUNT(*) FROM products WHERE rating NOT BETWEEN 0 AND 5
    """,
    "products.stock >= 0": """
        SELECT COUNT(*) FROM products WHERE stock < 0
    """,
    "products.discounted_price = price * (1 - discount / 100)": """
        SELECT COUNT(*) FROM products
        WHERE discounted_price <> ROUND(price * (1 - discount_percentage / 100), 2)
    """,
    "carts.discounted_total <= total": """
        SELECT COUNT(*) FROM carts WHERE discounted_total > total
    """,
    "carts have at least one item": """
        SELECT COUNT(*) FROM carts c
        WHERE NOT EXISTS (
            SELECT 1 FROM cart_items ci WHERE ci.cart_id = c.cart_id
        )
    """,
    "cart_items.quantity > 0": """
        SELECT COUNT(*) FROM cart_items WHERE quantity <= 0
    """,
    "cart_items.total = price * quantity": """
        SELECT COUNT(*) FROM cart_items
        WHERE total <> ROUND(price * quantity, 2)
    """,
    "cart_items.discounted_total <= total": """
        SELECT COUNT(*) FROM cart_items WHERE discounted_total > total
    """,
    "cart_items.item_position is 1..n per cart": """
        SELECT COUNT(*) FROM (
            SELECT cart_id
            FROM cart_items
            GROUP BY cart_id
            HAVING MIN(item_position) <> 1
                OR MAX(item_position) <> COUNT(*)
        ) gaps
    """,
}


def run_etl():
    """Run the real pipeline entry point; fail with a safe summary on error."""
    result = subprocess.run(
        [sys.executable, "src/main.py", "--load"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=ETL_TIMEOUT_SECONDS
    )

    if result.returncode != 0:
        # Report only the exception type: driver messages can contain data
        lines = [line for line in result.stderr.splitlines() if line.strip()]
        error_type = lines[-1].split(":", 1)[0] if lines else "no stderr output"

        pytest.fail(
            f"ETL run failed (exit code {result.returncode}): {error_type}",
            pytrace=False
        )

    return result.stdout


def _scalar(cursor, query):
    cursor.execute(query)

    return cursor.fetchone()[0]


def capture_database_state():
    """Capture counts, integrity checks, rows and row versions (read-only)."""
    state = {
        "counts": {},
        "duplicates": {},
        "orphans": {},
        "nulls": {},
        "rule_violations": {},
        "fingerprints": {},
        "row_versions": {},
        "rows": {},
    }

    with transaction(read_only=True) as cursor:
        connection = cursor.connection

        for table, key in TABLE_KEYS.items():
            order_by = ", ".join(f"t.{column}" for column in key)
            key_columns = ", ".join(key)

            state["counts"][table] = _scalar(cursor, f"SELECT COUNT(*) FROM {table}")

            # Hash of every column of every row, in key order
            state["fingerprints"][table] = _scalar(
                cursor,
                f"SELECT md5(string_agg(t::text, '|' ORDER BY {order_by})) "
                f"FROM {table} t"
            )

            # xmin changes whenever PostgreSQL writes a new row version
            cursor.execute(f"SELECT {key_columns}, xmin::text FROM {table}")
            state["row_versions"][table] = {
                row[:-1]: row[-1] for row in cursor.fetchall()
            }

            state["rows"][table] = fetch_records(
                connection, f"SELECT * FROM {table} ORDER BY {key_columns}"
            )

        for name, (table, column) in UNIQUE_KEYS.items():
            state["duplicates"][name] = _scalar(
                cursor,
                f"SELECT COUNT(*) - COUNT(DISTINCT {column}) FROM {table}"
            )

        for name, (child, column, parent, parent_column) in FOREIGN_KEYS.items():
            state["orphans"][name] = _scalar(
                cursor,
                f"""
                SELECT COUNT(*)
                FROM {child} c
                LEFT JOIN {parent} p ON c.{column} = p.{parent_column}
                WHERE p.{parent_column} IS NULL
                """
            )

        for table, columns in MANDATORY_COLUMNS.items():
            for column in columns:
                state["nulls"][f"{table}.{column}"] = _scalar(
                    cursor,
                    f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL"
                )

        for name, query in BUSINESS_RULES.items():
            state["rule_violations"][name] = _scalar(cursor, query)

    return state


def read_artifacts():
    return {
        "raw": {
            resource: read_json(RAW_DATA_DIR / f"{resource}.json")
            for resource in RESOURCES
        },
        "processed": {
            resource: read_json(PROCESSED_DATA_DIR / f"{resource}.json")
            for resource in RESOURCES
        },
        "modified": {
            path: path.stat().st_mtime
            for directory in (RAW_DATA_DIR, PROCESSED_DATA_DIR)
            for path in (directory / f"{resource}.json" for resource in RESOURCES)
        },
    }


def execute_run():
    started = time.time()
    stdout = run_etl()

    return {
        "started": started,
        "stdout": stdout,
        "artifacts": read_artifacts(),
        "state": capture_database_state(),
    }
