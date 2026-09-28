"""
Access to pipeline artifacts.

Two locations hold the same file layout (raw/ and processed/):

- Versioned snapshot (tests/fixtures/snapshot): a committed, reviewed copy of
  one pipeline run. Offline tests use it, so they are reproducible and never
  change when the live source changes.
- Runtime artifacts (data/raw, data/processed): written by every real ETL
  run and git-ignored. Database tests use them because they are exactly what
  was loaded into PostgreSQL.
"""

from pathlib import Path

import pytest

from config.settings import PROCESSED_DATA_DIR, PROJECT_ROOT, RAW_DATA_DIR
from utils.json_files import read_json


SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot"
SNAPSHOT_RAW_DIR = SNAPSHOT_DIR / "raw"
SNAPSHOT_PROCESSED_DIR = SNAPSHOT_DIR / "processed"

RUNTIME_DIRS = (RAW_DATA_DIR, PROCESSED_DATA_DIR)


def read_artifact(path):
    """Read an artifact, failing clearly if it does not exist."""
    __tracebackhide__ = True

    if not path.exists():
        if path.parent in RUNTIME_DIRS:
            hint = "Run 'python src/main.py --load' first."
        else:
            hint = "The versioned snapshot is missing from the checkout."

        pytest.fail(
            f"Missing pipeline artifact: {path.relative_to(PROJECT_ROOT)}. {hint}",
            pytrace=False
        )

    return read_json(path)
