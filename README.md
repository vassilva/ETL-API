# ETL API Pipeline – Data Quality & CI/CD Automation

## Overview

This project implements an end-to-end ETL pipeline designed to simulate a production-like Data Engineering and Data Quality workflow.

The solution extracts data from external REST APIs, applies transformation and data quality rules, loads the processed data into PostgreSQL, and automatically validates the resulting datasets through an automated test suite.

Jenkins is used as the Continuous Integration layer. The main `Jenkinsfile` is an offline quality gate (lint + offline tests); ETL and external-system execution will be handled by a separate Jenkins job in the future.

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
├── main.py                 # Pipeline entry point: extract + transform (no load)
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
├── fixtures/               # Synthetic data only
├── api/                    # API client unit tests (mocked HTTP)
├── extract/                # Live API data quality + offline extract unit tests
├── transform/              # Mapping/rule tests on generated files + synthetic unit tests
└── load/                   # PostgreSQL reconciliation (read-only) + offline DB unit tests

data/raw, data/processed    # Generated pipeline artifacts
sql/                        # DDL reference (never executed automatically)
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

The load step is run manually and only when intended, from the `src` directory:

```text
cd src
python -m load.users
python -m load.products
python -m load.carts
python -m load.cart_items
```

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

Marker meaning:

- `api` vs `live_api`: `api` tests *our client code* offline; `live_api` calls the *real source API*.
- `integration`: requires an external system. Added automatically (in `tests/conftest.py`) to every `live_api` and `database` test, so it never needs to be written by hand.
- `artifacts`: requires generated files in `data/`. Run `python src/main.py` first; the tests fail with a clear message if files are missing.
- `database`: uses a read-only PostgreSQL session; tests cannot modify data.
- Tests never write to `data/` or to the database.
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

The regression suite contains **141 automated tests** covering the Extract, Transform, and Load layers:

- 87 data quality tests against the live API, generated pipeline files, and PostgreSQL
- 54 offline unit tests using synthetic data (API client, extract, transform, database/load infrastructure)

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

The main `Jenkinsfile` is an **offline CI Quality Gate**. It needs no database, no DB credentials, no `.env`, and no access to the source API. Network access is used only to install dependencies from PyPI.

```text
Checkout
   |
   v
Build Information
   |
   v
Workspace Guard        (fails if a .env file exists; removes stale reports)
   |
   v
Setup Python           (fresh .venv every build)
   |
   v
Install Dependencies   (requirements-dev.txt + pip check)
   |
   v
Ruff
   |
   v
Offline Tests
   +---- API Client
   +---- Unit
   +---- Offline Data Quality
   |
   v
Publish JUnit results  (always)
   |
   v
Cleanup                (workspace deleted)
```

The pipeline executes on a dedicated Windows Jenkins agent.

| Stage | Command | Tests | JUnit report |
|---|---|---|---|
| Ruff | `ruff check src tests --no-cache` | - | - |
| API Client | `pytest -m api` | 11 | `reports/api.xml` |
| Unit | `pytest -m "unit and not api"` | 43 | `reports/unit.xml` |
| Offline Data Quality | `pytest -m "not integration and not unit"` | 38 | `reports/offline-data.xml` |

The three test selections do not overlap: **92 tests are executed once per build**.

Behavior:

- Dependency installation or Ruff failures stop the pipeline before any test runs.
- All three test groups always run; a failing group marks its stage and the build as FAILURE.
- JUnit results are published after every build, including failed ones.
- During the test stages `API_BASE_URL` points to an unreachable local address, so an accidental API request fails immediately instead of reaching the real API.
- Builds time out after 20 minutes, never run concurrently, and the last 30 builds are kept.

Intentionally **not** executed by this `Jenkinsfile`:

| Selection | Tests | Reason |
|---|---|---|
| `live_api` | 21 | Requires the external source API |
| `database` | 28 | Requires PostgreSQL and DB credentials |
| `integration` | 49 | `live_api` + `database` |
| `smoke` | 10 | Includes `live_api` and `database` tests |
| `regression` | 141 | Full suite, includes external systems |
| ETL execution (`python src/main.py`) | - | Calls the live API and rewrites `data/` |
| ETL Load | - | Writes to PostgreSQL |

External-system and ETL automation will be handled separately by a future Jenkins job / Jenkinsfile. Until then, these selections run locally only.

---

## Credentials Management

Database credentials are not stored in the source code or committed to GitHub.

Local development uses a `.env` file excluded from Git through `.gitignore`. Copy `.env.example` (placeholders only) to `.env` and fill in local values.

All environment access is centralized in `src/config/settings.py`. Database settings are validated only when a connection is requested, and connection details are never included in `repr()`, logs, or error messages.

The main `Jenkinsfile` (offline quality gate) does not use any database credentials. The CI workspace must not contain a `.env` file; the pipeline fails if one is found.

PostgreSQL credentials for CI remain stored in Jenkins Credentials, outside the repository. They are reserved for the future ETL / external-system job, where they should be bound only to the stage that needs them.

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
7. Publish JUnit results.
8. Mark the pipeline as successful only when all validation steps pass.

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

The main `Jenkinsfile` is a change-driven CI quality gate and does not execute the ETL process.

Scheduled ETL processing (extract, transform, load and external-system validation), simulating a batch ETL process commonly found in enterprise Data Warehouse environments, is planned as a separate Jenkins job and is not implemented yet.

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
  +---- All tests passed ----> Pipeline SUCCESS
  |
  +---- Any failure ---------> Pipeline FAILURE
```

A successfully validated CI execution reports:

```text
API Client:            11 passed
Unit:                  43 passed
Offline Data Quality:  38 passed

Offline quality gate passed.
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
- [x] 141-test regression suite (87 data quality + 54 unit)
- [x] Jenkins offline quality gate (Ruff + 92 offline tests)
- [x] JUnit test reports in Jenkins
- [x] Jenkinsfile stored in source control
- [x] Windows Jenkins agent
- [ ] Separate Jenkins job for ETL and external-system tests (live API, PostgreSQL)
- [ ] Scheduled ETL execution (planned for the separate job)
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
- Separate Jenkins job for ETL execution and external-system tests
- Simulated DEV / QA / UAT promotion flow
- Environment-specific configuration
- Pipeline failure notifications
- GitHub webhook integration when Jenkins is externally accessible

---

## Purpose

This repository is a practical Data QA laboratory designed to demonstrate how QA activities can be integrated throughout an ETL lifecycle and CI/CD workflow.

The project focuses on the principle that successful data delivery requires validation at multiple levels:

**Pipeline execution, data integrity, transformation accuracy, source-to-target reconciliation, automated regression testing, CI Quality Gates, and business-level validation.**
