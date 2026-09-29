"""
Fixtures for the idempotency suite (pre-merge regression).

Run 1 is the ETL the pipeline has already executed (Extract, Transform and
Load stages, or 'python src/main.py --load' locally); its database state is
captured here without running anything. The suite then re-runs the ETL once
and captures the state again. Every capture is read-only.
"""

import time

import pytest

from support.etl_contract import ENTITIES, source_key, source_records
from support.etl_e2e import artifact_mtimes, capture_database_state, run_etl


@pytest.fixture(scope="session")
def idempotency_runs(source_payloads):
    before = capture_database_state()

    # Run 1 must be complete, otherwise a difference after the re-run would
    # only mean "run 1 never happened", not a lack of idempotency
    expected = {
        entity: len({source_key(entity, r) for r in source_records(entity, source_payloads)})
        for entity in ENTITIES
    }

    if before["counts"] != expected:
        pytest.fail(
            f"[Idempotency] the database does not hold a complete first run "
            f"(counts {before['counts']}, source {expected}). "
            f"Run the ETL with --load before this suite.",
            pytrace=False
        )

    started = time.time()
    run_etl()

    return {
        "before": before,
        "after": capture_database_state(),
        "started": started,
        "artifact_mtimes": artifact_mtimes(),
    }
