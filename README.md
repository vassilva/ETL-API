# ETL API Pipeline – Data Quality & CI/CD Automation

## Overview

This project implements an end-to-end ETL pipeline designed to simulate a production-like Data Engineering and Data Quality workflow.

The solution extracts data from external REST APIs, applies transformation and data quality rules, loads the processed data into PostgreSQL, and automatically validates the resulting datasets through an automated test suite.

Jenkins is used as the Continuous Integration layer. A single Multibranch Pipeline (one root `Jenkinsfile`) runs an offline quality gate (lint + offline tests) followed by the real Integration / E2E layer: live API checks, the real ETL into PostgreSQL, database validation and idempotency.

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
├── conftest.py             # Shared fixtures, regression marker
├── support/                # Test helpers (read-only DB queries, value-hiding assertions)
├── fixtures/               # Synthetic data + snapshot/ (versioned copy of one real run)
├── api/                    # API client unit tests (mocked HTTP)
├── extract/                # Live API data quality + offline extract unit tests
├── transform/              # Mapping/rule tests on generated files + synthetic unit tests
├── load/                   # PostgreSQL reconciliation (read-only) + offline DB unit tests
└── e2e/                    # Opt-in end-to-end ETL run + idempotency (writes data/ and PostgreSQL)

data/raw, data/processed    # Runtime ETL artifacts (git-ignored, rewritten by every run)
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

Business-data changes are not ignored: the E2E test `test_processed_matches_versioned_snapshot` compares the loaded (processed) data with the snapshot and fails, reporting only the differing record IDs, if the source business data changes. Untransformed metadata is not part of the processed data and cannot trigger it. To accept a reviewed source change, run the ETL and copy `data/raw/*.json` and `data/processed/*.json` into `tests/fixtures/snapshot/raw` and `.../processed`, then commit the snapshot.

---

## Running Tests

Tests are grouped by ETL stage and tagged with Pytest markers (similar to tags in Cypress/Playwright):

| Command | Runs |
|---|---|
| `pytest` / `pytest -m regression` | Complete suite |
| `pytest -m smoke` | One record-count check per stage and dataset (10 tests) |
| `pytest -m unit` | Offline tests: no network, database, credentials, or generated files |
| `pytest -m "not integration"` | Everything that runs without network or PostgreSQL (safe offline run) |
| `pytest -m integration` | Everything that needs an external system (`live_api` + `database`) |
| `pytest -m api` | Offline tests of our API client (mocked HTTP, no network) |
| `pytest -m live_api` | Source data checks with real GET requests to the external API |
| `pytest -m database` | PostgreSQL reconciliation (read-only session) |
| `pytest -m extract` / `transform` / `load` | One ETL stage |
| `pytest -m e2e --run-e2e` | Real end-to-end ETL run (API -> data/ -> PostgreSQL), run twice to validate idempotency |

Test layers:

| Layer | Selection | Tests | Needs |
|---|---|---|---|
| Offline: API Client | `-m api` | 11 | nothing |
| Offline: Unit | `-m "unit and not api"` | 43 | nothing |
| Offline: Data Quality | `-m "not integration and not unit"` | 38 | versioned snapshot |
| Integration: live API | `-m "live_api and not e2e"` | 21 | network |
| Integration: PostgreSQL | `-m "database and not e2e"` | 28 | PostgreSQL + runtime artifacts from a real ETL run |
| E2E | `-m e2e --run-e2e` | 65 | network + PostgreSQL; writes `data/` and the database |

Marker meaning:

- `api` vs `live_api`: `api` tests *our client code* offline; `live_api` calls the *real source API*.
- `integration`: requires an external system. Added automatically (in `tests/conftest.py`) to every `live_api` and `database` test, so it never needs to be written by hand.
- `artifacts`: uses pipeline files. Offline tests read the versioned snapshot in `tests/fixtures/snapshot`; database tests read the runtime files in `data/processed` (what the last `python src/main.py --load` loaded) and fail with a clear message if they are missing.
- `database`: uses a read-only PostgreSQL session; tests cannot modify data.
- `e2e`: executes `python src/main.py --load` twice, checks the loaded data against the versioned snapshot (business-data drift), then validates row counts against the live API, key uniqueness, referential integrity, mandatory fields, business rules, source-to-database values, and idempotency (no duplicates, unchanged content, every row upserted in place). It **writes** to `data/` and upserts into PostgreSQL, so it is skipped unless `--run-e2e` is given. It is also `live_api` + `database`, so it is never part of the offline selections.
- Apart from `e2e`, tests never write to `data/` or to the database.
- Assertions on personal-data fields report only the record ID and field name, never the values.

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

Automated Data Quality checks are implemented using Pytest.

The regression suite contains **206 automated tests** covering the Extract, Transform, and Load layers:

- 87 data quality tests against the live API, generated pipeline files, and PostgreSQL
- 54 offline unit tests using synthetic data (API client, extract, transform, database/load infrastructure)
- 65 opt-in end-to-end tests that run the real ETL twice (skipped without `--run-e2e`)

The validations include:

- Record count validation
- Mandatory field validation
- Primary key uniqueness
- Referential integrity
- Source-to-target reconciliation
- Transformation rule validation
- Calculation validation
- Product and cart consistency
- User-to-cart relationship validation
- Cart-to-product relationship validation

The objective is not only to verify that the ETL process executes successfully, but also to ensure that the data produced by the pipeline remains accurate, complete, consistent, and traceable.

---

## Idempotency

The load is an UPSERT per table (`INSERT ... ON CONFLICT (key) DO UPDATE`), keyed by `user_id`, `product_id`, `cart_id` and `(cart_id, item_position)`. The E2E suite runs the complete ETL twice against the same database and proves that the second run:

- keeps every row count unchanged (and equal to the live API totals);
- creates no duplicate primary or business keys (`user_id`, `email`, `product_id`, `sku`, `cart_id`, `cart_item_id`, `(cart_id, item_position)`);
- keeps referential integrity (carts -> users, cart_items -> carts, cart_items -> products);
- leaves the content of every table identical (hash of every column of every row, including the `cart_items` identity key, so rows are updated in place, not deleted and re-inserted);
- really takes the UPSERT update path for every existing row (each row gets a new PostgreSQL row version, `xmin`).

The E2E tests only read the database (read-only session); all writes go through the real ETL entry point.

---

## Source-to-Target Reconciliation

Data reconciliation is an important part of the QA strategy.

Automated tests compare source and target datasets to identify potential issues such as:

- Missing records
- Unexpected records
- Incorrect transformations
- Duplicate identifiers
- Broken relationships
- Incorrect calculated values

This provides an additional validation layer beyond simply checking whether the ETL job completed successfully.

---

## Jenkins Pipeline

The Jenkins pipeline definition is stored as code in the repository using a `Jenkinsfile`.

This allows the CI configuration to be version-controlled together with the application and test code.

There is **one** Jenkins Multibranch Pipeline (`ETL-API-Pipeline`) and **one** root `Jenkinsfile`, with clearly separated test layers:

```text
Checkout
   |
   v
Build Information
   |
   v
Workspace Guard          (fails if a .env file exists; removes stale reports)
   |
   v
Setup Python             (fresh .venv every build)
   |
   v
Install Dependencies     (requirements-dev.txt + pip check)
   |
   v
Ruff
   |
   v
Offline Tests            (no API, no database, no credentials)
   +---- API Client
   +---- Unit
   +---- Offline Data Quality
   |
   v
Real Integration / E2E   (only after the offline gate passed)
   +---- Environment Validation   (config present? credential present? DB reachable?)
   +---- Live DummyJSON
   +---- Extract
   +---- Transform
   +---- Load                     (DB credentials bound here)
   +---- PostgreSQL Validation    (DB credentials bound here)
   +---- E2E + Idempotency        (DB credentials bound here)
   |
   v
Publish JUnit results    (always)
   |
   v
GitHub Checks            (final build result, reported by the Multibranch GitHub integration)
   |
   v
Cleanup                  (workspace deleted, including runtime data/)
```

The pipeline executes on the dedicated Windows Jenkins agent.

| Stage | Command | Tests | JUnit report (suite name) |
|---|---|---|---|
| Ruff | `ruff check src tests --no-cache` | - | - |
| API Client | `pytest -m api` | 11 | `reports/api.xml` (`api`) |
| Unit | `pytest -m "unit and not api"` | 43 | `reports/unit.xml` (`unit`) |
| Offline Data Quality | `pytest -m "not integration and not unit"` | 38 | `reports/offline-data.xml` (`offline-data`) |
| Environment Validation | agent variables + credential check + read-only `python -m database.connection` | - | - |
| Live DummyJSON | `pytest -m "live_api and not e2e"` | 21 | `reports/integration-live-api.xml` (`integration-live-api`) |
| Extract / Transform / Load | `python src/main.py --stage extract` / `transform` / `load` | - | - |
| PostgreSQL Validation | `pytest -m "database and not e2e"` | 28 | `reports/integration-database.xml` (`integration-database`) |
| E2E + Idempotency | `pytest -m e2e --run-e2e` | 65 | `reports/e2e.xml` (`e2e`) |

The offline selections do not overlap (92 tests), and the integration and E2E selections do not overlap with them or with each other: a full build executes **206 tests**, each once. Each layer is a separate JUnit suite, so API Client, Unit, Offline Data Quality, Integration and E2E results are distinguishable in Jenkins.

Behavior:

- Dependency installation or Ruff failures stop the pipeline before any test runs.
- All three offline test groups always run; a failing group marks its stage and the build as FAILURE.
- During the offline stages `API_BASE_URL` points to an unreachable local address, so an accidental API request fails immediately instead of reaching the real API.
- Real Integration / E2E runs only when the offline gate passed; otherwise it is reported as not run (the build is already FAILURE).
- If the CI database configuration is missing (agent variables or Jenkins credential), the stages are skipped **explicitly**: the log names what is missing and the build is marked **UNSTABLE**, never a silent SUCCESS.
- If the configuration exists but PostgreSQL is unreachable, Environment Validation fails and the build is **FAILURE**.
- An Extract, Transform or Load failure stops the remaining stages (FAILURE). A failing integration or E2E test group marks its stage and the build as FAILURE.
- JUnit results are published after every build, including failed ones; the final result is reported to GitHub Checks; the workspace is always deleted.
- Builds time out after 20 minutes, never run concurrently per branch, and the last 30 builds are kept.

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

The credential is bound with `withCredentials` only around the steps that connect to PostgreSQL (Environment Validation, Load, PostgreSQL Validation, E2E), so Jenkins masks both values in the log. The offline stages never receive it.

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
     Jenkins
        |
        v
 Ruff + Offline Tests
 + Integration / E2E
        |
        v
   Quality Gate
        |
        v
       main
```

---

## CI/CD

The project uses Jenkins for Continuous Integration.

Changes pushed to the development branch are automatically detected by Jenkins through SCM polling.

The CI workflow is designed to:

1. Detect source-control changes.
2. Retrieve the latest code from GitHub.
3. Read the version-controlled `Jenkinsfile`.
4. Create a fresh Python environment and install the pinned dependencies.
5. Run Ruff.
6. Execute the 92 offline tests (API Client, Unit, Offline Data Quality).
7. Run the real Integration / E2E layer: live API tests, the real ETL into PostgreSQL, database validation and idempotency.
8. Publish JUnit results and report the result to GitHub Checks.
9. Mark the pipeline as successful only when all validation steps pass.

The pipeline therefore acts as a **Quality Gate** before changes are considered ready for integration into the `main` branch.

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

The `Jenkinsfile` is change-driven: every build runs the real ETL once stage by stage and twice more inside the E2E suite, against the CI database.

A time-based trigger for batch ETL processing (simulating a scheduled Data Warehouse load) is not configured.

---

## Pipeline Quality Gate

The offline test suite acts as a Quality Gate for every change.

Expected behavior:

```text
Ruff
  |
  v
Offline Tests (API Client, Unit, Offline Data Quality)
  |
  v
Real Integration / E2E (live API, ETL, PostgreSQL, idempotency)
  |
  +---- All tests passed ------------------> Pipeline SUCCESS
  |
  +---- CI database config missing --------> Pipeline UNSTABLE (E2E explicitly skipped)
  |
  +---- Any failure -----------------------> Pipeline FAILURE
```

A successfully validated CI execution reports:

```text
API Client:            11 passed
Unit:                  43 passed
Offline Data Quality:  38 passed
Live DummyJSON:        21 passed
PostgreSQL Validation: 28 passed
E2E + Idempotency:     65 passed

Offline quality gate and real Integration / E2E passed.
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
- [x] 206-test regression suite (87 data quality + 54 unit + 65 E2E)
- [x] Jenkins offline quality gate (Ruff + 92 offline tests)
- [x] Real Integration / E2E layer in the same Jenkins pipeline (live API, ETL, PostgreSQL, idempotency)
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
