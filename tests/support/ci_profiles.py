"""
Pinned Jenkins test profiles: the independent expectation the Required
Quality Gate compares every CI run against.

Markers (smoke, regression) SELECT the tests; this file states which test
functions each JUnit suite MUST contain and how many cases each one has.
Both must agree, otherwise the gate fails. A marker removed, added or moved
by accident therefore changes the executed tests and fails the build
instead of silently shrinking or growing a gate. Changing a profile means
changing this file, so the change is visible in the Pull Request diff.

Required stages are the Jenkins stages (exact stage names) that must have
completed successfully before the gate can pass.

The LOCAL Full Regression (all tests) is intentionally not a profile here:
it never runs in Jenkins.
"""

# Push Smoke: fundamental offline code contracts (18)
SMOKE = {
    "tests/api/test_client.py::test_get_resource_requests_full_collection": 1,
    "tests/extract/test_extract_unit.py::test_extract_saves_raw_payload": 3,
    "tests/transform/test_transform_unit.py::test_transform_user_maps_all_fields": 1,
    "tests/transform/test_transform_unit.py::test_transform_product_maps_all_fields": 1,
    "tests/transform/test_transform_unit.py::test_transform_cart_maps_cart_and_products": 1,
    "tests/load/test_load_contract_unit.py::test_upsert_matches_target_contract": 4,
    "tests/load/test_load_contract_unit.py::test_row_values_align_with_sql_columns": 4,
    "tests/pipeline/test_main_unit.py::test_entry_point_stage_order": 3,
}

# PR offline preconditions beyond Smoke (19): defects runtime reconciliation
# cannot see (secret leaks, destructive loader, transactions, edge contracts)
PR_OFFLINE = {
    "tests/api/test_client.py::test_http_error_hides_response_body": 2,
    "tests/api/test_client.py::test_timeout_raises_safe_error": 1,
    "tests/api/test_client.py::test_connection_error_hides_url": 1,
    "tests/api/test_client.py::test_invalid_json_raises_safe_error": 1,
    "tests/api/test_client.py::test_client_uses_centralized_settings": 1,
    "tests/load/test_database_unit.py::test_connection_error_is_sanitized": 1,
    "tests/load/test_database_unit.py::test_database_settings_repr_hides_connection_details": 1,
    "tests/load/test_database_unit.py::test_get_connection_read_only": 1,
    "tests/load/test_database_unit.py::test_transaction_rolls_back_on_error": 1,
    "tests/load/test_database_unit.py::test_execute_for_each_counts_rows": 1,
    "tests/load/test_database_unit.py::test_loader_delegates_to_execute_for_each": 2,
    "tests/transform/test_transform_unit.py::test_transform_product_name_appends_rp_suffix": 5,
    "tests/transform/test_transform_unit.py::test_transform_user_full_name_keeps_unicode": 1,
}

# PR critical source contract, before Extract (3)
PR_SOURCE = {
    "tests/extract/test_source_quality.py::test_source_collection_is_complete": 3,
}

# PR critical target evidence after the Load (17)
PR_TARGET = {
    "tests/reconciliation/test_reconciliation.py::test_completeness": 4,
    "tests/target/test_target_integrity.py::test_load_freshness": 4,
    "tests/reconciliation/test_reconciliation.py::test_source_to_database": 4,
    "tests/reconciliation/test_reconciliation.py::test_measure_control_total": 2,
    "tests/target/test_business_rules.py::test_business_rule": 3,
}

PROFILES = {
    "push": {
        "suites": {"smoke": SMOKE},
        "stages": ["Ruff", "Smoke"],
    },
    "pr": {
        "suites": {
            "pr-offline": {**SMOKE, **PR_OFFLINE},
            "pr-source": PR_SOURCE,
            "pr-target": PR_TARGET,
        },
        "stages": [
            "Ruff", "PR Offline", "Environment Validation", "Source Critical",
            "Extract", "Transform", "Load", "Target and Reconciliation",
        ],
    },
    # main: the merged tree is proven identical to the PR-validated tree
    "main-evidence": {
        "suites": {},
        "stages": ["Main Evidence"],
    },
    # main: identity not provable -> the exact Smoke profile, fail closed
    "main-fallback": {
        "suites": {"smoke": SMOKE},
        "stages": ["Main Evidence", "Ruff", "Smoke"],
    },
}


def expected_count(profile):
    return sum(sum(suite.values()) for suite in PROFILES[profile]["suites"].values())
