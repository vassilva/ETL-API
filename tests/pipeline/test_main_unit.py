"""
Pipeline entry point orchestration (offline).

Every stage function is replaced by a recorder, so the test proves the
order and scope of the calls made by src/main.py, not the stages themselves.
"""

import pytest

import main


pytestmark = [pytest.mark.unit]


EXTRACT = ["extract_users", "extract_products", "extract_carts"]
TRANSFORM = ["transform_users", "transform_products", "transform_carts"]
# Parent tables first, so every foreign key exists before its children
LOAD = ["load_users", "load_products", "load_carts", "load_cart_items"]
SETTINGS_CHECK = ["check database settings"]


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    for name in EXTRACT + TRANSFORM + LOAD:
        monkeypatch.setattr(main, name, lambda name=name: recorded.append(name))

    class RecordingSettings:
        def database(self):
            recorded.append(SETTINGS_CHECK[0])

    monkeypatch.setattr(main, "get_settings", RecordingSettings)

    return recorded


# Validate the stage order of every entry-point mode. The default run must
# never touch the database; loading validates DB settings before any work.
@pytest.mark.parametrize(
    "mode, expected",
    [
        ("run", EXTRACT + TRANSFORM),
        ("run --load", SETTINGS_CHECK + EXTRACT + TRANSFORM + LOAD),
        ("--stage load", SETTINGS_CHECK + LOAD),
    ]
)
def test_entry_point_stage_order(calls, mode, expected):
    if mode == "run":
        main.run()
    elif mode == "run --load":
        main.run(load=True)
    else:
        main.run_stage("load")

    assert calls == expected
