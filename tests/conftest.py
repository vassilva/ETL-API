"""
Shared fixtures and hooks for the whole test suite.

Markers are declared per module/test. Three markers are derived here so they
can never drift out of sync, and every test belongs to exactly one gate:

- integration: every test marked live_api, database or artifacts (it needs
  an external system or the runtime output of a real ETL run), so the
  offline selections can never pick it up
- sanity (push gate): every test that is not integration
- regression (pre-merge gate): every integration test not marked smoke

smoke (the PR critical path) is the only gate marker applied by hand, and
only integration tests may carry it. sanity and regression must never be
applied by hand.

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

DERIVED_GATE_MARKERS = ("sanity", "regression")


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
        if manual := [name for name in DERIVED_GATE_MARKERS if item.get_closest_marker(name)]:
            raise pytest.UsageError(
                f"{item.nodeid}: gate marker(s) {manual} are derived automatically; remove them"
            )

        integration = any(item.get_closest_marker(name) for name in EXTERNAL_DEPENDENCY_MARKERS)
        smoke = item.get_closest_marker("smoke") is not None

        if smoke and not integration:
            raise pytest.UsageError(
                f"{item.nodeid}: smoke is the PR critical path on the real ETL run; "
                f"offline tests already run in sanity"
            )

        if integration:
            item.add_marker(pytest.mark.integration)

        if not integration:
            item.add_marker(pytest.mark.sanity)
        elif not smoke:
            item.add_marker(pytest.mark.regression)

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
