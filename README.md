# ETL API Pipeline – Data Quality & CI/CD Automation

## Overview

This project implements an end-to-end ETL pipeline designed to simulate a production-like Data Engineering and Data Quality workflow.

The solution extracts data from external REST APIs, applies transformation and data quality rules, loads the processed data into PostgreSQL, and automatically validates the resulting datasets through an automated test suite.

Jenkins is the CI/CD layer. A single Multibranch Pipeline (one root `Jenkinsfile`) selects the lifecycle from the build event alone: a feature-branch push runs **Ruff + Smoke** (18 offline tests); a Pull Request runs the **ETL Regression** (57 tests on one real ETL run, the required merge status); `main` proves with **Main Evidence** that it holds exactly the PR-validated tree, then waits for a **Manual Deployment Approval** and runs a **Fake Deployment** (see [CI/CD Lifecycle](#cicd-lifecycle)). The complete library of 151 tests is the **Full Regression**, which QA runs **locally only** (see [QA local testing](#qa-local-testing-and-the-full-regression)).

The project was developed as a hands-on environment for practicing ETL testing, database validation, pipeline automation, Git workflows, and CI/CD concepts from a QA/Data QA perspective.

---

## Architecture

The current workflow follows the architecture below:

```text
External REST API
        |
        v
     Extract
        |
        v
   Transform
        |
        v
      Load
        |
        v
   PostgreSQL
        |
        v
Data Quality Tests
        |
        v
     Pytest
        |
        v
     Jenkins
        |
        +---- SUCCESS
        |
        +---- FAILURE
```

Power BI is used as the reporting and business validation layer on top of the PostgreSQL database.

---

## Technology Stack

- Python
- PostgreSQL
- REST API
- Pytest
- Jenkins
- Git
- GitHub
- Power BI
- DBeaver
- Windows Jenkins Agent

---

## Project Structure

```text
src/
├── main.py                 # Pipeline entry point: extract + transform (+ load with --load)
├── config/settings.py      # Centralized configuration (the only env reader)
├── api/client.py           # HTTP client: base URL, timeout, status checks, safe errors
├── extract/                # Fetch source resources and save data/raw
├── transform/              # Pure transformations + file wrappers (data/raw -> data/processed)
├── load/                   # Static, parameterized upserts per table
├── database/connection.py  # Connections, transactions, rollback, read-only sessions
└── utils/json_files.py     # JSON read/write anchored to the project root

tests/
├── conftest.py             # Markers, fixtures (snapshot, runtime artifacts, live source, read-only DB)
├── support/                # ETL contract (independent oracle), reconciliation engine, DB helpers, Load baseline,
│                           # Quality Gate and the pinned Jenkins test profiles (ci_profiles.py)
├── fixtures/               # Synthetic data + snapshot/ (versioned copy of one real run)
├── api/                    # API client unit tests (mocked HTTP)
├── pipeline/               # Entry-point orchestration unit tests
├── extract/                # Live source quality + offline extract unit tests
├── transform/              # Snapshot contract/rule/golden tests + synthetic unit tests
├── load/                   # UPSERT/row-alignment contract + DB infrastructure unit tests
├── target/                 # Post-load integrity and business rules (set-based SQL)
├── reconciliation/         # Completeness, boundary reconciliation, control totals, drift
└── e2e/                    # Idempotency: re-runs the ETL (local Full Regression only, --run-e2e)

data/raw, data/processed    # Runtime ETL artifacts (git-ignored, rewritten by every run)
data/state                  # Load freshness baseline (git-ignored)
sql/create_tables.sql       # Target schema DDL (IF NOT EXISTS; never executed automatically)
reports/                    # Local test reports (git-ignored)
```

---

## Local Setup

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env      (then fill in local values)
```

Run the pipeline (extract + transform) from the project root:

```text
python src/main.py
```

Run the complete ETL, including the load into PostgreSQL (requires the `DB_*` settings and the tables from `sql/create_tables.sql`):

```text
python src/main.py --load
```

Or one stage at a time (this is how Jenkins runs it, so each stage is reported separately):

```text
python src/main.py --stage extract
python src/main.py --stage transform
python src/main.py --stage load
```

Before a Load that will be validated, capture the Load freshness baseline (read-only; records each target row's version so the checks can prove the Load wrote every row):

```text
$env:PYTHONPATH = "src;tests"      (PowerShell; cmd: set PYTHONPATH=src;tests)
python -m support.load_freshness
```

Loading is opt-in: without `--load` / `--stage load` the pipeline never touches the database. Missing `DB_*` settings stop the run before any work, and only the variable names are reported. The load upserts in foreign-key order (users, products, carts, cart_items), so running it again updates rows in place instead of duplicating them (see [Idempotency](#idempotency)).

### PostgreSQL requirements

- PostgreSQL reachable from the machine that runs the ETL (locally: the `.env` settings; in CI: the Windows Jenkins agent).
- The four target tables, created once with `sql/create_tables.sql` (`CREATE TABLE IF NOT EXISTS`, never drops anything). The upserts rely on its primary keys and on `UNIQUE (cart_id, item_position)`.
- A database user allowed to `SELECT`, `INSERT` and `UPDATE` these tables.

Configuration is read only from environment variables (or the local `.env`); names only:

| Variable | Required | Notes |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME` | for load and database tests | connection target |
| `DB_USER`, `DB_PASSWORD` | for load and database tests | secret; never logged |
| `API_BASE_URL`, `API_TIMEOUT_SECONDS`, `DB_CONNECT_TIMEOUT_SECONDS` | optional | defaults in `src/config/settings.py` |

### Runtime artifacts vs versioned snapshot

| Location | Tracked in Git | Written by | Used by |
|---|---|---|---|
| `data/raw`, `data/processed` | No (git-ignored) | every real ETL run | the load step, database tests, E2E; inspect them here after a run |
| `tests/fixtures/snapshot/raw`, `.../processed` | Yes | nobody automatically (reviewed refresh only) | offline Data Quality tests |

The source API regenerates metadata such as `meta.createdAt` / `meta.updatedAt` on every request, so a committed `data/` directory became modified after every legitimate ETL run. Runtime output is therefore git-ignored and a real ETL / E2E run leaves `git status` clean, while offline tests keep running against a fixed, reviewed snapshot.

Business-data changes are not ignored: `test_business_data_drift` (local Full Regression: upstream monitoring) compares the loaded (processed) data with the snapshot and fails, reporting only the differing record IDs, if the source business data changes. Untransformed metadata is not part of the processed data and cannot trigger it. To accept a reviewed source change, run the ETL and copy `data/raw/*.json` and `data/processed/*.json` into `tests/fixtures/snapshot/raw` and `.../processed`, then commit the snapshot.

---

## Running Tests

The repository holds one automation library of **151 tests**. Every test carries markers for **what it validates** (boundary) and **what it needs** (dependency); two execution-profile markers select what Jenkins runs.

| Marker | Meaning |
|---|---|
| `extract` / `transform` / `load` | ETL boundary validated |
| `unit` | Offline, synthetic data only |
| `api` | Offline tests of our API client (mocked HTTP) |
| `live_api` | Calls the real source API |
| `database` | Needs PostgreSQL (read-only session) |
| `artifacts` | Needs the **runtime** output of a real ETL run in `data/` |
| `integration` | Derived automatically from `live_api`, `database` or `artifacts` |
| `e2e` | Re-runs the ETL (writes `data/` and PostgreSQL); skipped unless `--run-e2e` |
| `smoke` | **Push Smoke** (Jenkins push builds; the PR build re-runs it): fundamental offline code contracts. Offline tests only |
| `regression` | **PR ETL Regression** (Jenkins PR builds, together with every `smoke` test) |
| *(neither)* | **Local Full Regression only** |

`tests/conftest.py` stops the collection on invalid combinations: `smoke` on an integration test, `smoke` together with `regression`, and either on an `e2e` test. `tests/support/ci_profiles.py` pins the exact test functions and case counts of every Jenkins profile, and the Required Quality Gate compares each run against it, so a marker removed or added by accident fails the build.

| Profile | Selection | Tests | Runs where |
|---|---|---|---|
| Smoke | `-m smoke` | 18 | Jenkins push (and main fallback) |
| PR ETL Regression | offline `-m "(smoke or regression) and not integration"` (37) + source `-m "regression and live_api and not database and not artifacts"` (3) + target `-m "regression and (database or artifacts)"` (17) | 57 | Jenkins Pull Request |
| Local Full Regression | all tests (`-m "not e2e"` 142, then `-m e2e --run-e2e` 9) | 151 | **QA machine only** |

### QA local testing and the Full Regression

Developing or changing a test is a local activity; QA never needs Jenkins to validate the automation library:

```text
single test      python -m pytest tests/transform/test_transform_unit.py::test_transform_product_maps_all_fields
related group    python -m pytest tests/transform -m "not integration"
a CI profile     python -m pytest -m smoke
optional Full    the procedure below (151 tests)
```

The Full Regression validates the runtime ETL output, so it needs the ETL lifecycle first (local `.env` with the `DB_*` settings and the tables from `sql/create_tables.sql`). Run from the project root, in this order (PowerShell):

```text
python src/main.py --stage extract
python src/main.py --stage transform
$env:PYTHONPATH = "src;tests"; python -m support.load_freshness; Remove-Item Env:PYTHONPATH
python src/main.py --stage load
python -m pytest -m "not e2e"            # 142 tests on this run's artifacts and Load
python -m pytest -m e2e --run-e2e        # 9 idempotency tests: re-run the ETL, always last
```

The Load freshness baseline must be captured immediately before the Load (otherwise `test_load_freshness` fails by design), and the idempotency re-run must come last because it rewrites `data/` and the target rows. 142 + 9 = **151**. If Windows reports a `PermissionError` on `...\Temp\pytest-of-<user>\pytest-current`, a stale pytest temp link is the cause (environment, not product): point `TEMP`/`TMP` to another directory or pass `--basetemp`.

### Local Adaptive Sanity Testing

Four test concepts exist, with different owners and questions:

| Concept | Where | Selection | Size | Question |
|---|---|---|---|---|
| **Sanity** | **local only** (QA/developer) | **adaptive**: chosen for one specific fix or change | **variable** - no fixed count | Does this specific fix/change work, and do the directly affected behaviors still work? |
| **Smoke** | Jenkins push gate | fixed, curated (`smoke`) | 18, offline | Is the project fundamentally healthy enough to continue? |
| **ETL Regression** | Jenkins PR merge gate | fixed, risk-selected (`smoke` + `regression`) | 57, one real ETL run | Does this merge candidate have enough evidence to enter `main`? |
| **Full Regression** | local only | every test | 151 | Does the entire automation library pass? |

Sanity is **not** a fixed suite, a marker, a Jenkins stage or a Quality Gate profile, and it never runs on Push, PR, `main` or before a deployment. It is a QA decision made while developing a bug fix, a small change or a test-automation change, using plain pytest selection (node IDs, files, `-k`). There is deliberately no Sanity marker and no expected Sanity count.

**Selecting the tests.** Start from the change, not from a list:

- What exactly changed, and what failed before? Which test proves the fix?
- Which component is directly affected, and what is upstream and downstream of it?
- Does the change touch Extract, Transform, Load, database persistence, a relationship, a business rule, or a reconciliation?
- What adjacent behavior could the fix break (regression risk)?
- Which **smallest** set of existing tests proves those risks?

Two forms follow from the answers:

- **Fast local Sanity**: the risk is provable with unit/contract tests. A handful of offline tests; no API, database or ETL run needed.
- **Integration Sanity**: the change is specifically about persistence or reconciliation. A few directly related integration tests, after preparing only the ETL state they need (see the prerequisites below). It stays targeted; it never grows into the Full or the ETL Regression.

**Examples with real tests** (PowerShell, project root, virtual environment active; quote node IDs that contain brackets):

A. **`product_name` / `" - RP"` bug** (Transform business rule)

```text
# Fast (offline, 7 tests): the rule's edge cases, the full product mapping and the rule on real snapshot data
python -m pytest tests/transform/test_transform_unit.py::test_transform_product_name_appends_rp_suffix tests/transform/test_transform_unit.py::test_transform_product_maps_all_fields "tests/transform/test_snapshot_transform.py::test_snapshot_transformation_rule[products.product_name]"

# Integration (3 tests; needs this run's RAW/Processed, a completed Load and the live API): the Transform boundary,
# the value that reached the database and the SQL business rule on stored data
python -m pytest "tests/reconciliation/test_reconciliation.py::test_raw_to_processed[products]" "tests/reconciliation/test_reconciliation.py::test_source_to_database[products]" tests/target/test_business_rules.py -k "raw_to_processed or source_to_database or product_name"
```

`test_transform_product_name_appends_rp_suffix` proves the rule itself (unicode, padding, titles that already contain "RP"); `test_transform_product_maps_all_fields` proves the fix did not disturb the other product columns; the snapshot rule checks every real product. In the integration command `-k` filters **all** collected tests, so it names each wanted test.

B. **UPSERT bug** (Load)

```text
# Fast (offline, 10 tests): UPSERT contract (H1) and row/SQL alignment (H2) for every table, and the loader call
python -m pytest tests/load/test_load_contract_unit.py tests/load/test_database_unit.py::test_loader_delegates_to_execute_for_each

# Integration (12 tests; after: capture the Load baseline, run the Load): every row rewritten by THIS Load (H3),
# persisted values equal the Processed input, no missing/extra/duplicate keys
python -m pytest tests/target/test_target_integrity.py::test_load_freshness tests/reconciliation/test_reconciliation.py::test_processed_to_database tests/reconciliation/test_reconciliation.py::test_completeness
```

The offline part runs immediately. The integration part needs the prepared runtime: RAW/Processed of the current run, then `python -m support.load_freshness` (with `PYTHONPATH=src;tests`) **immediately before** `python src/main.py --stage load`. Only when the update semantics themselves changed, add the idempotency re-run last: `python -m pytest tests/e2e/test_idempotency.py --run-e2e` (it re-runs the whole ETL).

C. **Stock bug** (Transform/Load preservation)

```text
# Fast (offline, 3 tests): stock mapping, stock copied for every real product, stock bound to the right SQL column
python -m pytest tests/transform/test_transform_unit.py::test_transform_product_maps_all_fields "tests/transform/test_snapshot_transform.py::test_snapshot_mapping_contract[products]" "tests/load/test_load_contract_unit.py::test_row_values_align_with_sql_columns[products]"

# Integration (3 tests; needs live API, this run's artifacts and a completed Load): total stock at every boundary,
# every product's stock in the database, and the Transform boundary
python -m pytest "tests/reconciliation/test_reconciliation.py::test_measure_control_total[products.stock]" "tests/reconciliation/test_reconciliation.py::test_source_to_database[products]" "tests/reconciliation/test_reconciliation.py::test_raw_to_processed[products]"
```

The control total catches volume loss; the record-level Source -> Database check catches values moved between products, which a total cannot see. If the report is "negative stock", the upstream check is `python -m pytest tests/extract/test_source_quality.py -k "stock"` (live API only).

D. **API client bug** (Extract)

```text
# Fast (offline, 9 tests): request contract, timeouts, safe errors, JSON handling, session cleanup
python -m pytest tests/api/test_client.py

# If the change also touches how Extract uses the client (offline, 7 tests)
python -m pytest tests/extract/test_extract_unit.py

# Integration only if the request itself changed (e.g. parameters): complete collections from the live API (3 tests, no database)
python -m pytest tests/extract/test_source_quality.py::test_source_collection_is_complete
```

**Sanity never replaces CI.** Passing a local Sanity selection does not bypass anything; it only gives faster feedback before the real evidence:

```text
local change -> optional adaptive Sanity (local) -> Push -> Smoke (18) -> Pull Request -> ETL Regression (57) -> PR Gate -> Merge
```

**Sanity never replaces the Full Regression.** Run the Full (151) when shared fixtures, helpers (`tests/support`), the reconciliation framework or the test infrastructure changed, when broad confidence is needed, and before an automation-framework change is considered complete.

**Bug-fix workflow:**

```text
bug reported -> reproduce -> identify affected layer and risk -> select or create the test that proves the bug
-> fix -> adaptive local Sanity -> Push (Smoke) -> Pull Request (ETL Regression) -> PR Gate -> Merge
```

**Classifying a new bug-regression test.** A test written for a bug is permanent coverage, and its CI profile is decided by risk, not by having been used as Sanity:

- a fundamental capability whose failure should stop every push -> consider `smoke` (and update `tests/support/ci_profiles.py`);
- a critical merge risk -> consider `regression` (and update `tests/support/ci_profiles.py`);
- valuable but expensive, diagnostic, rare, edge-case or upstream monitoring -> no profile marker: local Full only;
- useful only temporarily -> do not keep duplicate permanent coverage.

Every permanent test must have a clear responsibility. Adding such a test naturally grows the library beyond today's 151; that number is the current size, not a limit. Automatic, change-based test selection (mapping changed files to tests) is future work; today Sanity is a QA decision.

Rules the suite follows:

- The expected side of every reconciliation comes from an independent oracle: the live source, the declarative ETL contract (`tests/support/etl_contract.py`, restated from the requirements and `sql/create_tables.sql`) or the committed snapshot; never from the production transform or load code.
- Record sets are indexed without collapsing duplicates, key sets are compared in both directions before fields, and an empty expected side fails instead of passing vacuously.
- Failures name the boundary, entity, field, rule, mismatch count, sample keys and expected/actual values; values of personal-data columns are always hidden.
- Monetary and other `NUMERIC(p, s)` columns are compared as `Decimal`. The only rounding applied is the explicit schema rule on the expected side (the target stores scale `s`); the database value is never rounded.
- Apart from the Load freshness baseline tool and `e2e`, tests never write to `data/` or to the database.

Lint: `ruff check src tests`

---

## Data Sources

The ETL process currently consumes the following datasets from the source API:

- Users
- Products
- Carts

Cart data is also normalized into cart-level and cart-item-level structures during processing.

---

## ETL Process

### 1. Extract

The extraction layer retrieves source data from the REST API.

The current extraction process retrieves:

- 208 users
- 194 products
- 208 carts

Source-level validations verify data availability, mandatory identifiers, uniqueness, valid values, and relationships between datasets.

### 2. Transform

The transformation layer converts the source payloads into structures suitable for the target database.

Examples of transformation logic include:

- Field mapping
- Full-name generation
- Product name rule: `product_name = source title + " - RP"` (complete original title kept, suffix added exactly once; products only, cart items keep the original title)
- Product price calculations
- Discount calculations
- Cart normalization
- Data type normalization
- Relationship mapping between users, carts, products, and cart items

Transformation tests validate both mapping rules and expected business logic.

### 3. Load

The transformed data is loaded into PostgreSQL.

Current target tables:

- `public.users`
- `public.products`
- `public.carts`
- `public.cart_items`

The load layer preserves relationships between datasets and provides the target data used for reconciliation, automated testing, and reporting.

---

## Data Quality Strategy

Automated Data Quality checks are implemented using Pytest: a library of **151 tests** (the local Full Regression); Jenkins runs the risk-selected subsets described in [CI/CD Lifecycle](#cicd-lifecycle).

| Dimension | Where it is validated |
|---|---|
| Completeness | Source collection complete; count **and key set** per boundary (Source, RAW, Processed, Database), anchored to the live source, first divergent boundary reported |
| Uniqueness | Source ids; business keys at every boundary (completeness and reconciliation report duplicate keys); target keys the schema does not enforce (`email` compared case- and whitespace-insensitively, `sku` trimmed) |
| Mandatory fields | NULL for every column; also `''`/whitespace for text columns |
| Validity / business rules | Source rules (price > 0, stock >= 0, ...) and 15 set-based target rules (formulas, ranges, " - RP" suffix, cart header = sum of items) |
| Referential integrity | Source, committed snapshot and target (anti-joins) |
| Transformation correctness | Declarative contract on the snapshot (offline) and on this run's RAW -> Processed |
| Reconciliation | Source -> RAW (every field), RAW -> Processed, Processed -> Database, Source -> Database |
| Control totals | `products.stock` and `carts.total` at every boundary (dynamic, never hardcoded) |
| Load freshness | Every target row rewritten by this run's Load |
| Load contract | UPSERT update completeness and row/column alignment (offline, against the DDL) |
| Idempotency | ETL re-run: unchanged content, every row upserted |
| Drift | This run's processed data vs the reviewed snapshot |

Record-level reconciliation and control totals protect different risks and are both kept: swapping the stock of two products keeps the stock total green while record-level reconciliation fails; losing volume is caught by the total even before individual records are compared.

The Product price rule is explicit and consistent across the suite: **price > 0** (source and target).

---

## Idempotency

The load is an UPSERT per table (`INSERT ... ON CONFLICT (key) DO UPDATE`), keyed by `user_id`, `product_id`, `cart_id` and `(cart_id, item_position)`.

Three complementary controls:

| Control | Gate | Proves | Does not prove |
|---|---|---|---|
| UPSERT contract (`tests/load/test_load_contract_unit.py`) | Smoke + PR (offline) | Inserted columns = DDL business columns; conflict target = business key (backed by PK/UNIQUE); every non-key column updated from its own `EXCLUDED` value | Runtime behaviour |
| Load freshness (`test_load_freshness`) | PR Regression | This run's Load wrote a new row version (`xmin`) for every target row, compared with a baseline captured just before the Load; a no-op Load fails even when the database already held identical rows | Who wrote the row (see [Build isolation](#build-isolation)) |
| Idempotency re-run (`tests/e2e`) | Local Full only | A second ETL run leaves every table's content unchanged (hash of every column of every row, including the `cart_items` identity key) while rewriting every row | That the UPDATE writes changed source values (both runs load the same data): covered by the UPSERT contract |

`xmin` is used only as a technical "row was written" signal, never as a business value.

---

## Source-to-Target Reconciliation

Each ETL boundary is reconciled against its own independent oracle:

```text
Source (live API) --[Source -> RAW: every field, API payload]--> RAW
RAW --[RAW -> Processed: declarative contract]--> Processed
Processed --[Processed -> Database: processed files, Load boundary only]--> PostgreSQL
Source (live API) --[Source -> Database: declarative contract, end to end]--> PostgreSQL
```

`Processed -> Database` is the correct oracle for the Load boundary, but it is **not** a source-to-target check (the processed files are the Load's own input); `Source -> Database` is the independent end-to-end check. Only the API's own volatile metadata (`meta.createdAt`, `meta.updatedAt`) is excluded from `Source -> RAW`.

---

## Jenkins Pipeline

The Jenkins pipeline definition is stored as code in the repository using a `Jenkinsfile`.

There is **one** Jenkins Multibranch Pipeline (`ETL-API-Pipeline`) and **one** root `Jenkinsfile`.

### CI/CD Lifecycle

```text
FEATURE BRANCH push (no Pull Request yet)
    Ruff -> Smoke (18 offline) -> Push Gate                         no ETL, no API, no DB, no deployment
                |
PULL REQUEST (opened, or any new push to it)
    Ruff -> PR Offline (37) -> Environment Validation -> Source Critical (3)
    -> Extract -> Transform -> Load -> Target and Reconciliation (17) -> PR Gate
    = continuous-integration/jenkins/pr-merge                       1 ETL run, no deployment
                |
MERGE to main
    Main Evidence: merged tree == PR-validated tree?  yes -> 0 tests
                                                      no/unknown -> Ruff + Smoke (18)
    -> Main Gate -> Manual Deployment Approval (30 min) -> Fake Deployment

QA LOCAL (never Jenkins)
    Adaptive Sanity = targeted tests for one change (variable count)
    Full Regression = all 151 tests
```

The build event alone selects the lifecycle; the pipeline has **no build parameters**, and no Jenkins path runs the Full Regression.

| Event | Tests | ETL runs | Live source | Database | Deployment |
|---|---|---|---|---|---|
| Push to a branch without a Pull Request | 18 | 0 | no (tripwire) | no | never |
| Pull Request opened or updated | 57 | 1 | 3 fetch rounds | yes | never |
| `main` (merged tree proven) | 0 | 0 | no | no | after manual approval |
| `main` (fallback) | 18 | 0 | no | no | after manual approval |
| QA local Full Regression | 151 | 2 | yes | yes | — |

### Gate purposes

| Gate | Question it answers | What runs |
|---|---|---|
| **Push Smoke** | Is the project fundamentally healthy enough to keep developing? | Ruff; full-collection API request; Extract writes RAW; hard-coded Transform contracts (full_name, `" - RP"`, discounted_price, cart relationship); UPSERT contract (H1) and row/SQL alignment (H2); pipeline stage order |
| **PR ETL Regression** | Is this merge candidate safe to enter `main`? | Smoke again on the merge candidate; offline merge preconditions the runtime checks cannot see (secret-leak protection, malformed-response handling, destructive-loader and transaction safety, RP/unicode business contracts); the source contract; one real Extract -> Transform -> Load; Load freshness (H3); completeness at every boundary; Source -> Database on every business column (H4); stock and cart control totals; the three critical business rules in SQL |
| **Main Evidence** | Is `main` exactly what the PR validated? | Git tree identity; Smoke only when identity cannot be proven |
| **Local Full** | Everything: diagnostics, monitoring, edge cases | All 151 tests, including intermediate boundary reconciliation, upstream source monitoring, drift, target data-quality monitoring and idempotency |

Why Jenkins does not run everything:

- **Push** only has to prove the code is fundamentally sound; Smoke answers that offline in about a second. Broader offline tests stay available locally and the ones that protect merge risks run in the PR.
- **Pull Request** is the technical merge gate. Its tests were selected from zero by risk and verified by fault injection: every realistic Extract, Transform and Load defect injected into the real data or the code was killed by the PR set. Tests that only localize a failure (Source -> RAW, RAW -> Processed, Processed -> Database), monitor upstream data (source rules, drift, mandatory/uniqueness/referential checks on source-provided values) or re-run the ETL (idempotency) add evidence that does not change the merge decision and run locally.
- **Smoke re-runs in the PR** because, once a Pull Request exists, pushes build only the PR job, and the PR validates the merge candidate, which can differ from the pushed branch head.
- **Main** does not repeat the regression: a GitHub merge commit whose tree equals its PR head tree contains exactly the code the PR build validated. Unknown evidence always falls back to Smoke.
- Independent checks protect the checks themselves: completeness (own key comparison), control totals (SQL `SUM`), the SQL business rules and the hard-coded Transform units still work if the generic reconciliation helper were broken.

### Stages

```text
CI (Windows agent, 20-minute timeout)
  Build Information -> Pipeline Gate -> Main Evidence (main) -> Workspace Guard
  -> Setup Python -> Install Dependencies (skipped on proven main evidence)
  -> Ruff
  -> Smoke                                                   push, main fallback
  -> PR Offline -> Environment Validation -> Source Critical
     -> Extract (+ RAW written) -> Transform (+ Processed written)
     -> Load (baseline first) -> Target and Reconciliation   Pull Request
  -> Required Quality Gate                                   every build
  Publish JUnit (always) -> Cleanup
Manual Deployment Approval (no agent, 30 minutes)            main, gate passed
Fake Deployment (Windows agent)                              main, approved
```

| Stage | Selection | Tests | JUnit suite |
|---|---|---|---|
| Smoke | `-m smoke` | 18 | `smoke` |
| PR Offline | `-m "(smoke or regression) and not integration"` | 37 | `pr-offline` |
| Source Critical | `-m "regression and live_api and not database and not artifacts"` | 3 | `pr-source` |
| Target and Reconciliation | `-m "regression and (database or artifacts)"` | 17 | `pr-target` |

Behavior:

- **Fail fast:** every stage requires all earlier stages to have succeeded. Ruff fails -> no tests; PR Offline fails -> no ETL; Environment Validation or Source Critical fails -> no Extract; Extract/Transform/Load fails (or does not write its artifacts) -> nothing after it. Inside one pytest suite every test still runs (no `-x`), so all failures of that suite are reported.
- **No stale data:** Workspace Guard fails when `data/raw`, `data/processed` or `data/state` exist before the build, and Extract/Transform must each write all three artifacts, so no check can pass on the output of an earlier run. Load freshness proves every target row was written by this build's Load.
- **Result semantics:** a required failure is **FAILURE** (never UNSTABLE, never SUCCESS; a later stage cannot improve it); a timeout or manual abort is **ABORTED**. Anything but SUCCESS keeps `pr-merge` from reporting success and prevents deployment.
- During the offline stages `API_BASE_URL` points to an unreachable local address, so an accidental API request fails immediately. In a Pull Request build, missing CI database configuration or unreachable PostgreSQL is a FAILURE.

### Required Quality Gate

The last CI stage (`tests/support/quality_gate.py`, standard library only) runs in every build with the profile of the event (`push`, `pr`, `main-evidence`, `main-fallback`) and fails closed unless:

- every required stage of the profile **completed** (Jenkins records each successful stage; a skipped or failed stage is missing);
- every required JUnit report exists, is readable and belongs to its suite;
- each suite contains **exactly** the pinned test functions and case counts of `tests/support/ci_profiles.py` (missing, extra or moved tests fail; so does zero);
- every test case passed (any failure, error or skip fails; `xfail_strict = true` makes an unexpected pass a failure);
- the executed total equals the expected total (push 18, PR 57, main evidence 0, main fallback 18), and the Jenkins build has no earlier failure.

```text
set PYTHONPATH=tests
python -m support.quality_gate --profile pr --reports reports --completed-stages "Ruff,PR Offline,..."
```

### Main Evidence

`main` builds prove instead of re-testing. `MAIN_TEST_MODE = EVIDENCE_ONLY` (0 tests) only when HEAD is a two-parent GitHub pull-request merge commit whose tree is identical to its PR head tree (checked with `git log --format=%T`, i.e. tree hashes, not commit SHAs). Anything else - a squash or direct commit, a different tree, a missing PR number, any error - is `SMOKE_FALLBACK`: Ruff + the exact Smoke profile, which must pass before approval is offered. This relies on the required `pr-merge` status on `main` (branch protection) for "the PR head was validated".

### Manual Deployment Approval

- Only a `main` build whose Main Gate passed reaches it; the stage condition and a second scripted guard both enforce this.
- Uses the standard Jenkins `input` step with a **30-minute** timeout. The stage has no agent, so no executor is held while waiting.
- Approver restriction (optional, configured in Jenkins, never in this repository): the global environment variable `DEPLOY_APPROVERS` (Manage Jenkins -> System -> Global properties -> Environment variables) with comma-separated Jenkins user IDs and/or group names. When it is not set, the log prints a warning and any user with Build permission on the job (and administrators) can approve.
- Rejected, aborted or timed out: the build ends **ABORTED**, its description reads `NOT DEPLOYED: ...`, the log prints `DEPLOYMENT DID NOT OCCUR`, and Fake Deployment does not run.
- Builds of `main` are serialized: a newer merge waits until the pending approval is decided or times out.

### Fake Deployment

A laboratory simulation, separate from pytest (0 tests): no external system is contacted and nothing is installed. It runs only on `main`, after the Main Gate and an explicit approval, and prints and archives `deployment/deployment-record.txt` with the application, simulated environment, commit SHA, branch, Jenkins job, build number and URL, qualifying Pull Request, main validation mode, approver, UTC deployment time and result. No credential is bound and no environment is printed.

### Jenkins and GitHub configuration (manual, not changed by this repository)

| Where | Setting | Why |
|---|---|---|
| GitHub branch protection on `main` | Keep `continuous-integration/jenkins/pr-merge` as a required status check | It is the PR ETL Regression + PR Gate |
| GitHub branch protection on `main` | Recommended: "Require branches to be up to date before merging" | The tested merge result then equals what lands on `main` |
| Jenkins Multibranch (GitHub Branch Source) | Keep "Exclude branches that are also filed as PRs"; discover Pull Requests by merging with the target branch only | One build per change; no duplicate `pr-head` build |
| Jenkins global properties | Optional `DEPLOY_APPROVERS` | Restricts who may approve deployments |
| Windows agent | Keep a single executor | Build isolation (below) |

### Build isolation

All Pull Request builds share one PostgreSQL database; feature-branch and `main` builds never touch it. Load freshness assumes that no other build loads it while it runs. Assumptions (not enforced by this repository): the Multibranch configuration excludes branch builds for branches that are also Pull Requests, and builds are serialized on the Windows agent (a single executor). Two concurrent Pull Request builds could otherwise interleave their Loads (known residual risk H5). If that becomes possible, add a Jenkins lock around the Pull Request ETL stages.

---

## Credentials Management

Database credentials are not stored in the source code or committed to GitHub.

Local development uses a `.env` file excluded from Git through `.gitignore`. Copy `.env.example` (placeholders only) to `.env` and fill in local values.

All environment access is centralized in `src/config/settings.py`. Database settings are validated only when a connection is requested, and connection details are never included in `repr()`, logs, or error messages.

The CI workspace must not contain a `.env` file; the pipeline fails if one is found.

CI database configuration (no values are stored in the repository):

| What | Where in Jenkins | Provides |
|---|---|---|
| Credential `postgres-etl-api`, kind **Username with password** | Manage Jenkins -> Credentials | `DB_USER`, `DB_PASSWORD` |
| Environment variables `DB_HOST`, `DB_PORT`, `DB_NAME` | Windows agent node -> Configure -> Node Properties -> Environment variables | connection target as seen from that agent (not secret) |

The credential is bound with `withCredentials` only around the steps that connect to PostgreSQL (Environment Validation, Load, Target and Reconciliation), so Jenkins masks both values in the log. Ruff, Smoke, PR Offline, Source Critical, Extract, Transform, the Quality Gate, the approval and the deployment stages never receive it.

---

## Git Workflow

Development changes are implemented using feature branches instead of being committed directly to `main`.

The current workflow follows:

```text
main
 |
 +---- feature branch
          |
          v
       Changes
          |
          v
        Commit
          |
          v
         Push
          |
          v
     Pull Request
          |
          v
     CI Validation
          |
          v
      Quality Gate
          |
          v
        Merge
          |
          v
         main
```

Example feature branch:

```text
feature/jenkins-ci
```

Changes are reviewed and validated before being integrated into the `main` branch.

---

## Pull Request Workflow

Changes pushed to a feature branch are associated with a Pull Request targeting `main`.

Additional commits pushed to the same feature branch automatically update the existing Pull Request.

The Pull Request provides a controlled integration point where changes can be reviewed and validated before merge.

Current flow:

```text
feature/jenkins-ci
        |
        v
      GitHub
        |
        v
  Pull Request
        |
        v
     Jenkins (PR-<n>)
        |
        v
 Ruff -> PR Offline -> Source -> Extract -> Transform -> Load
 -> Target and Reconciliation (ETL Regression)
        |
        v
 Required Quality Gate (continuous-integration/jenkins/pr-merge)
        |
        v
       main -> Main Evidence -> Manual Deployment Approval -> Fake Deployment
```

---

## CI/CD

The project uses Jenkins for Continuous Integration and a simulated, manually approved Continuous Delivery step.

Changes pushed to the development branch are automatically detected by Jenkins through SCM polling.

The CI/CD workflow is designed to:

1. Detect source-control changes.
2. Retrieve the latest code from GitHub.
3. Read the version-controlled `Jenkinsfile` and select the lifecycle from the build event (feature branch, Pull Request or `main`).
4. Create a fresh Python environment and install the pinned dependencies.
5. Push builds: Ruff + Smoke (18 offline tests).
6. Pull Request builds: Ruff + PR Offline (37) + one real ETL into PostgreSQL with the source contract (3) and the target and reconciliation evidence (17): 57 tests.
7. `main`: prove the merged tree is the PR-validated tree (0 tests; otherwise Ruff + Smoke), wait for manual deployment approval and run the Fake Deployment.
8. Run the Required Quality Gate, publish JUnit results and report the result to GitHub.

The Full Regression (151 tests) is never part of CI; QA runs it locally.

The Pull Request build therefore acts as the **Quality Gate** before changes are integrated into the `main` branch.

---

## CI Trigger Strategy

Because the Jenkins controller is running locally, SCM polling is currently used to detect repository changes.

Jenkins periodically checks the configured Git branch for new commits.

```text
Developer / QA
      |
      v
   Git Commit
      |
      v
   Git Push
      |
      v
    GitHub
      |
      v
Jenkins SCM Polling
      |
      v
 Change Detected
      |
      v
   CI Pipeline
```

This simulates automated CI execution within the limitations of a local development environment.

In a remotely accessible Jenkins environment, this workflow could be evolved to use GitHub webhooks for event-driven pipeline execution.

---

## Scheduled Execution

No time-based trigger is configured, and the Full Regression (including the ETL re-run for idempotency) is intentionally not a Jenkins job: QA runs it locally (see [QA local testing](#qa-local-testing-and-the-full-regression)).

---

## Pipeline Quality Gate

Expected behavior of a Pull Request build (see [Required Quality Gate](#required-quality-gate)):

```text
Ruff -> PR Offline -> Environment -> Source -> Extract -> Transform -> Load -> Target and Reconciliation
  |
  v
Required Quality Gate
  |
  +---- every required stage completed and exactly the
  |     57 pinned tests passed ----------------------------> SUCCESS -> pr-merge green -> merge allowed
  |
  +---- any failure, error, skip, missing/extra test,
        missing report or stage, missing DB config --------> FAILURE -> pr-merge not green -> merge blocked
```

A successful Pull Request build reports:

```text
REQUIRED QUALITY GATE - profile: pr
  stage  Ruff ... Target and Reconciliation   COMPLETED (8 stages)
  suite  pr-offline   expected  37  passed  37  PASS
  suite  pr-source    expected   3  passed   3  PASS
  suite  pr-target    expected  17  passed  17  PASS
  total  expected 57, passed 57
Quality Gate PASSED (pr): 8 stages, 57 tests
```

---

## Failure Handling

The pipeline is designed to fail when automated validation identifies a problem.

During CI implementation, database authentication failures were correctly detected by the automated test suite when database credentials were unavailable to the Jenkins workspace.

The issue was resolved by moving CI database authentication to Jenkins Credentials rather than exposing the local `.env` file through Git.

This demonstrates an important CI principle:

> A pipeline failure is useful when it prevents an unvalidated change from being treated as production-ready.

---

## Business Validation

Technical validation is complemented by a business-facing validation layer using Power BI.

Current KPIs include:

- Total Sales
- Total Customers
- Total Orders
- Average Sales per Customer
- Top 10 Customers by Sales

Power BI results are validated against SQL queries executed directly against PostgreSQL.

This provides validation across multiple layers:

```text
Source API
    |
    v
ETL Processing
    |
    v
PostgreSQL
    |
    +---- Automated Data Quality Tests
    |
    +---- SQL Validation
    |
    v
Power BI
    |
    v
Business Validation
```

---

## QA Responsibilities Simulated by This Project

From a QA/Data QA perspective, this project covers activities commonly performed in ETL, Data Warehouse, and CI/CD testing:

- Understanding source and target structures
- Validating ETL mappings
- Creating Data Quality checks
- Writing SQL validation queries
- Performing source-to-target reconciliation
- Testing referential integrity
- Validating transformation rules
- Investigating data discrepancies
- Maintaining automated regression tests
- Monitoring scheduled ETL executions
- Reviewing Jenkins execution logs
- Working with Git feature branches
- Creating and validating Pull Requests
- Managing CI Quality Gates
- Validating business KPIs against database results
- Supporting controlled integration into the main branch

---

## Current Status

The current implementation supports:

- [x] REST API extraction
- [x] Data transformation
- [x] PostgreSQL loading
- [x] Source-to-target reconciliation
- [x] Automated Data Quality testing
- [x] 151-test risk-based suite (independent oracles, boundary reconciliation, control totals)
- [x] Push Smoke (Ruff + 18 offline tests)
- [x] PR ETL Regression (57 tests, one real ETL run) as the required merge gate
- [x] Main Evidence (tree identity; Smoke fallback), Manual Deployment Approval and Fake Deployment (simulated CD)
- [x] Fail-closed Quality Gate with pinned profiles and stage evidence
- [x] Full Regression (151 tests) as a local QA procedure, never in Jenkins
- [x] Load freshness and UPSERT contract guards
- [x] Versioned test snapshot separated from runtime ETL artifacts
- [x] JUnit test reports in Jenkins
- [x] Jenkinsfile stored in source control
- [x] Windows Jenkins agent
- [ ] Scheduled ETL execution
- [x] Git repository
- [x] GitHub integration
- [x] Feature branch workflow
- [x] Pull Request workflow
- [x] CI Quality Gate
- [x] Power BI business validation
- [x] SQL-based KPI reconciliation
- [x] SCM polling configuration

---

## Next Steps

Planned improvements include:

- Automatic validation of new commits through SCM polling
- CI result visibility directly in Pull Requests
- Branch protection rules
- Improved automated test reporting
- Scheduled (time-based) ETL execution
- Simulated DEV / QA / UAT promotion flow
- Environment-specific configuration
- Pipeline failure notifications
- GitHub webhook integration when Jenkins is externally accessible

---

## Purpose

This repository is a practical Data QA laboratory designed to demonstrate how QA activities can be integrated throughout an ETL lifecycle and CI/CD workflow.

The project focuses on the principle that successful data delivery requires validation at multiple levels:

**Pipeline execution, data integrity, transformation accuracy, source-to-target reconciliation, automated regression testing, CI Quality Gates, and business-level validation.**
