"""
Shared fixtures and hooks for the whole test suite.

Markers are declared per module/test. integration is derived here so it can
never drift out of sync: every test marked live_api, database or artifacts
(it needs an external system or the runtime output of a real ETL run), so the
offline selections can never pick it up.

Execution profiles (see README "CI/CD Lifecycle"):

- smoke       Jenkins push builds (the PR build re-runs it on the merge
              candidate). Offline tests only.
- regression  Jenkins PR builds, in addition to every smoke test.
- neither     LOCAL Full Regression only. Full is every test (151) and
              never runs in Jenkins.

The exact tests of each Jenkins profile are pinned in support/ci_profiles.py;
the Required Quality Gate fails when the executed tests differ from it, so a
marker added or removed by accident cannot silently change a gate.

Invalid combinations stop the collection: smoke on an integration test,
smoke together with regression, and smoke/regression on e2e tests (the
idempotency re-run is local only).

e2e tests re-run the ETL (they write data/ and PostgreSQL), so they are
skipped unless the run explicitly opts in with --run-e2e.
"""

import json
from pathlib import Path

import pytest

from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from database.connection import get_connection
from extract.common import fetch_payload
from support.artifacts import (
    SNAPSHOT_PROCESSED_DIR,
    SNAPSHOT_RAW_DIR,
    read_artifact,
)
from support.etl_contract import SOURCE_RESOURCES


SYNTHETIC_FIXTURES_DIR = Path(__file__).parent / "fixtures"


EXTERNAL_DEPENDENCY_MARKERS = ("live_api", "database", "artifacts")


def pytest_addoption(parser):
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="run e2e tests (re-runs the real ETL: writes data/ and PostgreSQL)"
    )


# tryfirst: markers must exist before '-m' deselection runs
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    run_e2e = config.getoption("--run-e2e")
    skip_e2e = pytest.mark.skip(reason="re-runs the ETL (writes data/ and PostgreSQL); use --run-e2e")

    for item in items:
        integration = any(item.get_closest_marker(name) for name in EXTERNAL_DEPENDENCY_MARKERS)
        smoke = item.get_closest_marker("smoke") is not None
        regression = item.get_closest_marker("regression") is not None

        if smoke and integration:
            raise pytest.UsageError(f"{item.nodeid}: smoke tests must be offline (no live_api, database or artifacts)")

        if smoke and regression:
            raise pytest.UsageError(f"{item.nodeid}: smoke and regression are exclusive (the PR build already runs smoke)")

        if (smoke or regression) and item.get_closest_marker("e2e"):
            raise pytest.UsageError(f"{item.nodeid}: e2e tests (ETL re-run) belong to the local Full Regression only")

        if integration:
            item.add_marker(pytest.mark.integration)

        if item.get_closest_marker("e2e") and not run_e2e:
            item.add_marker(skip_e2e)


# Synthetic test data (tests/fixtures) — deterministic, no real data

@pytest.fixture
def synthetic_payload():
    """Return a fresh copy of a synthetic source payload by resource name."""
    def load(resource):
        path = SYNTHETIC_FIXTURES_DIR / f"{resource}_sample.json"

        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    return load


# Versioned pipeline snapshot (tests/fixtures/snapshot): a committed, reviewed
# copy of one real run, so offline tests are reproducible.

@pytest.fixture(scope="session")
def snapshot_raw():
    """{resource: raw payload} as committed (API shape)."""
    return {r: read_artifact(SNAPSHOT_RAW_DIR / f"{r}.json") for r in SOURCE_RESOURCES}


@pytest.fixture(scope="session")
def snapshot_processed():
    """{resource: processed list} as committed."""
    return {r: read_artifact(SNAPSHOT_PROCESSED_DIR / f"{r}.json") for r in SOURCE_RESOURCES}


# Runtime artifacts (data/raw, data/processed): written by the last real ETL
# run of this workspace; tests using them are marked 'artifacts'.

@pytest.fixture(scope="session")
def runtime_raw():
    return {r: read_artifact(RAW_DATA_DIR / f"{r}.json") for r in SOURCE_RESOURCES}


@pytest.fixture(scope="session")
def runtime_processed():
    return {r: read_artifact(PROCESSED_DATA_DIR / f"{r}.json") for r in SOURCE_RESOURCES}


# Live source (DummyJSON), fetched once per session independently of the ETL;
# tests using it are marked 'live_api'.

@pytest.fixture(scope="session")
def source_payloads():
    return {resource: fetch_payload(resource) for resource in SOURCE_RESOURCES}


# PostgreSQL target; tests using it are marked 'database'.

@pytest.fixture(scope="session")
def db_connection():
    """One read-only connection: the server rejects any write statement."""
    connection = get_connection(read_only=True)

    yield connection

    connection.close()
