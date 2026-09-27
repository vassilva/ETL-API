# ETL API Pipeline – Data Quality & CI/CD Automation

## Overview

This project implements an end-to-end ETL pipeline designed to simulate a production-like Data Engineering and Data Quality workflow.

The solution extracts data from external REST APIs, applies transformation and data quality rules, loads the processed data into PostgreSQL, and automatically validates the resulting datasets through an automated test suite.

Jenkins is used as the orchestration and Continuous Integration layer to execute the ETL pipeline and its associated Data Quality tests.

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

The current pipeline contains two primary stages:

```text
Run ETL
   |
   v
Run Tests
```

The execution flow is:

```text
GitHub Repository
        |
        v
    Jenkins
        |
        v
 Windows Agent
        |
        v
   Checkout Code
        |
        v
     Run ETL
        |
        v
   PostgreSQL
        |
        v
 Run Automated Tests
        |
        v
   Quality Gate
```

The pipeline executes on a dedicated Windows Jenkins agent.

The target staged layout (not yet applied to the `Jenkinsfile`) is:

| Stage | Command | DB credentials |
|---|---|---|
| Lint | `ruff check src tests` | no |
| Unit | `pytest -m unit` | no |
| Extract | `pytest -m live_api` | no |
| Run ETL | `python src/main.py` (extract + transform only) | no |
| Transform | `pytest -m "transform and artifacts"` | no |
| DB Validation | `pytest -m database` (read-only) | yes, this stage only |
| Reports | `--junitxml=reports/junit-<stage>.xml` + JUnit publish | no |

The load step is intentionally not part of CI.

---

## Credentials Management

Database credentials are not stored in the source code or committed to GitHub.

Local development uses a `.env` file excluded from Git through `.gitignore`. Copy `.env.example` (placeholders only) to `.env` and fill in local values.

All environment access is centralized in `src/config/settings.py`. Database settings are validated only when a connection is requested, and connection details are never included in `repr()`, logs, or error messages.

For CI execution, PostgreSQL credentials are securely managed by Jenkins Credentials using the credential ID:

```text
postgres-etl-api
```

During pipeline execution, Jenkins injects the required credentials as environment variables.

This prevents sensitive database credentials from being exposed in the Git repository.

```text
Jenkins Credentials
        |
        +---- Username
        |
        +---- Password
        |
        v
Environment Variables
        |
        v
Python / Pytest
        |
        v
PostgreSQL
```

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
   ETL Execution
        |
        v
 Automated Tests
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
4. Execute the ETL process.
5. Connect to PostgreSQL using Jenkins-managed credentials.
6. Execute the automated Data Quality regression suite.
7. Fail the pipeline if ETL execution or automated validation fails.
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

In addition to CI execution, Jenkins supports scheduled ETL execution.

The scheduled pipeline simulates a batch ETL process commonly found in enterprise Data Warehouse environments.

During scheduled execution Jenkins automatically:

1. Starts the Windows agent execution.
2. Retrieves the pipeline definition.
3. Executes the ETL process.
4. Extracts source datasets.
5. Applies transformation rules.
6. Loads target PostgreSQL tables.
7. Executes the automated Data Quality regression suite.
8. Reports the final pipeline status.

This allows the project to simulate both:

```text
Scheduled ETL Processing
```

and:

```text
Change-Driven CI Validation
```

---

## Pipeline Quality Gate

The automated regression suite acts as a Quality Gate for the ETL process.

Expected behavior:

```text
ETL Execution
      |
      v
Run Data Quality Tests
      |
      +---- All tests passed ----> Pipeline SUCCESS
      |
      +---- Test failure --------> Pipeline FAILURE
```

A pipeline is not considered successfully validated simply because the ETL execution completed.

The resulting data must also pass the automated Data Quality checks.

A successfully validated CI execution currently produces:

```text
141 passed

ETL pipeline completed successfully.

Finished: SUCCESS
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
- [x] Jenkins pipeline execution
- [x] Jenkinsfile stored in source control
- [x] Windows Jenkins agent
- [x] Jenkins Credentials integration
- [x] Scheduled Jenkins execution
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
- JUnit test reports in Jenkins
- Simulated DEV / QA / UAT promotion flow
- Environment-specific configuration
- Pipeline failure notifications
- GitHub webhook integration when Jenkins is externally accessible

---

## Purpose

This repository is a practical Data QA laboratory designed to demonstrate how QA activities can be integrated throughout an ETL lifecycle and CI/CD workflow.

The project focuses on the principle that successful data delivery requires validation at multiple levels:

**Pipeline execution, data integrity, transformation accuracy, source-to-target reconciliation, automated regression testing, CI Quality Gates, and business-level validation.**
