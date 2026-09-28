"""Access to generated pipeline artifacts (data/raw, data/processed)."""

import pytest

from config.settings import PROJECT_ROOT
from utils.json_files import read_json


def read_artifact(path):
    """Read a generated artifact, failing clearly if it does not exist."""
    __tracebackhide__ = True

    if not path.exists():
        pytest.fail(
            f"Missing pipeline artifact: {path.relative_to(PROJECT_ROOT)}. "
            f"Run 'python src/main.py' first.",
            pytrace=False
        )

    return read_json(path)
