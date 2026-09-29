"""
Idempotency helpers: run the real pipeline and capture PostgreSQL state.

Every query here is a read-only SELECT executed in a read-only session.
"""

import subprocess
import sys

import pytest

from config.settings import PROCESSED_DATA_DIR, PROJECT_ROOT, RAW_DATA_DIR
from database.connection import transaction
from support.etl_contract import BUSINESS_KEYS, SOURCE_RESOURCES
from support.load_freshness import row_versions


ETL_TIMEOUT_SECONDS = 600


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


def capture_database_state():
    """Row counts, a content hash and row versions of every target table."""
    state = {"counts": {}, "fingerprints": {}, "row_versions": {}}

    with transaction(read_only=True) as cursor:
        for table, key in BUSINESS_KEYS.items():
            order_by = ", ".join(f"t.{column}" for column in key)

            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            state["counts"][table] = cursor.fetchone()[0]

            # Hash of every column of every row (including generated identity
            # columns, so a delete + re-insert of cart_items is visible)
            cursor.execute(
                f"SELECT md5(string_agg(t::text, '|' ORDER BY {order_by})) FROM {table} t"
            )
            state["fingerprints"][table] = cursor.fetchone()[0]

            state["row_versions"][table] = row_versions(cursor, table)

    return state


def artifact_mtimes():
    return {
        path: path.stat().st_mtime
        for directory in (RAW_DATA_DIR, PROCESSED_DATA_DIR)
        for path in (directory / f"{resource}.json" for resource in SOURCE_RESOURCES)
    }
