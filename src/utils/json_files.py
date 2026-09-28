"""
JSON file helpers with paths anchored to the project root.

Serialization matches the original pipeline output (UTF-8, ensure_ascii=False,
indent=4, platform text-mode newlines) so regenerated artifacts are identical.
"""

import json
from pathlib import Path

from config.settings import PROJECT_ROOT


def resolve_path(path):
    path = Path(path)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def read_json(path):
    with open(resolve_path(path), "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    target = resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with open(target, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
