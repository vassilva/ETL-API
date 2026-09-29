"""
Idempotency of the complete ETL (pre-merge regression, last stage; opt-in
with --run-e2e).

Re-running the ETL against the same source must leave every target table
exactly as it was, while really taking the UPSERT update path for every row.

What these tests prove:
- content hash unchanged: no row added, removed or changed in any column
  (including the cart_items identity key, so a delete + re-insert of cart
  items is visible); this also rules out new duplicates and orphans
- every row has a new row version (xmin): the re-run wrote every key; a
  re-run that silently does nothing fails here

What they do not prove:
- that the UPDATE branch writes every column when the SOURCE CHANGES
  (both runs load the same data): covered by the static UPSERT contract
  (tests/load/test_load_contract_unit.py)
- who wrote the new row versions: another process loading the same
  database during the re-run would also change xmin (build isolation is an
  assumption, see README)
"""

import pytest

from support.etl_contract import ENTITIES
from support.reconciliation import sample


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.live_api,
    pytest.mark.database,
]


# Allowance for file-system timestamp resolution
MTIME_TOLERANCE_SECONDS = 2


# Validate that the re-run really executed Extract and Transform again
def test_rerun_rewrites_artifacts(idempotency_runs):
    stale = [
        path.name
        for path, modified in idempotency_runs["artifact_mtimes"].items()
        if modified < idempotency_runs["started"] - MTIME_TOLERANCE_SECONDS
    ]

    assert not stale, f"[Idempotency] artifacts not rewritten by the re-run: {stale}"


# Validate that the re-run left the content of every table unchanged
@pytest.mark.parametrize("table", ENTITIES)
def test_rerun_leaves_table_content_unchanged(idempotency_runs, table):
    before, after = idempotency_runs["before"], idempotency_runs["after"]

    assert after["fingerprints"][table] == before["fingerprints"][table], (
        f"[Idempotency] {table}: content changed after the re-run | "
        f"rows before: {before['counts'][table]} | rows after: {after['counts'][table]}"
    )


# Validate that the re-run took the UPSERT update path for every existing row
@pytest.mark.parametrize("table", ENTITIES)
def test_rerun_upserts_every_row(idempotency_runs, table):
    before = idempotency_runs["before"]["row_versions"][table]
    after = idempotency_runs["after"]["row_versions"][table]

    unchanged = [key for key, version in after.items() if before.get(key) == version]

    assert not unchanged, (
        f"[Idempotency] {table}: {len(unchanged)} of {len(after)} rows were not "
        f"rewritten by the re-run | sample keys: {sample(unchanged)}"
    )
