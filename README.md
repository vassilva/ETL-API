# ETL API Pipeline – Data Quality & CI/CD Automation

## Overview

This project implements an end-to-end ETL pipeline designed to simulate a production-like Data Engineering and Data Quality workflow.

The solution extracts data from external REST APIs, applies transformation and data quality rules, loads the processed data into PostgreSQL, and automatically validates the resulting datasets through an automated test suite.

Jenkins is the CI/CD layer. A single Multibranch Pipeline (one root `Jenkinsfile`) selects the lifecycle from the build event alone: a feature-branch push runs **Sanity**; a Pull Request runs **Sanity -> Smoke -> Pre-Merge Regression -> Required Quality Gate** (the required merge status); `main` runs **Sanity**, then a **Manual Deployment Approval** and a **Fake Deployment** (see [CI/CD Lifecycle](#cicd-lifecycle)).

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
├── support/                # ETL contract (independent oracle), reconciliation engine, DB helpers, Load baseline, Quality Gate
├── fixtures/               # Synthetic data + snapshot/ (versioned copy of one real run)
├── api/                    # API client unit tests (mocked HTTP)
├── pipeline/               # Entry-point orchestration unit tests
├── extract/                # Live source quality + offline extract unit tests
├── transform/              # Snapshot contract/rule/golden tests + synthetic unit tests
├── load/                   # UPSERT/row-alignment contract + DB infrastructure unit tests
├── target/                 # Post-load integrity and business rules (set-based SQL)
├── reconciliation/         # Completeness, boundary reconciliation, control totals, drift
└── e2e/                    # Idempotency: re-runs the ETL (Pre-Merge Regression, --run-e2e)

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

Business-data changes are not ignored: `test_business_data_drift` (Pre-Merge Regression) compares the loaded (processed) data with the snapshot and fails, reporting only the differing record IDs, if the source business data changes. Untransformed metadata is not part of the processed data and cannot trigger it. To accept a reviewed source change, run the ETL and copy `data/raw/*.json` and `data/processed/*.json` into `tests/fixtures/snapshot/raw` and `.../processed`, then commit the snapshot.

---

## Running Tests

Every test carries markers for **what it validates** (boundary) and **what it needs** (dependency), and belongs to exactly one **pipeline gate**.

| Marker | Meaning |
|---|---|
| `extract` / `transform` / `load` | ETL boundary validated |
| `unit` | Offline, synthetic data only |
| `api` | Offline tests of our API client (mocked HTTP) |
| `live_api` | Calls the real source API |
| `database` | Needs PostgreSQL (read-only session) |
| `artifacts` | Needs the **runtime** output of a real ETL run in `data/` |
| `integration` | Derived automatically from `live_api`, `database` or `artifacts`; offline selections exclude it |
| `sanity` | **Gate, derived automatically**: every offline test (not `integration`) |
| `smoke` | **Gate, applied by hand**: the PR critical path on the real ETL run; only valid on `integration` tests |
| `regression` | **Gate, derived automatically**: every `integration` test not marked `smoke` |
| `e2e` | Re-runs the ETL (writes `data/` and PostgreSQL); skipped unless `--run-e2e` |

`sanity` and `regression` are derived in `tests/conftest.py`, so a new test can never be left out of every gate. Applying either by hand, or `smoke` to an offline test, stops the collection with an error.

Test layers (disjoint selections, 151 tests in total):

| Gate | Layer | Selection | Tests | Needs |
|---|---|---|---|---|
| Sanity | API Client | `-m "sanity and api"` | 9 | nothing |
| Sanity | Unit | `-m "sanity and unit and not api"` | 52 | nothing |
| Sanity | Offline Data Quality | `-m "sanity and not unit"` | 13 | committed snapshot |
| Smoke | Source Smoke | `-m "smoke and live_api and not database and not artifacts"` | 7 | network |
| Smoke | Target Smoke | `-m "smoke and (database or artifacts)"` | 24 | ETL run + PostgreSQL + Load baseline + network |
| Regression | Source Quality | `-m "regression and live_api and not database and not artifacts"` | 8 | network |
| Regression | Target Quality & Reconciliation | `-m "regression and (database or artifacts) and not e2e"` | 29 | ETL run + PostgreSQL + network |
| Regression | Idempotency | `-m "regression and e2e" --run-e2e` | 9 | ETL run + PostgreSQL + network; re-runs the ETL |

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

Automated Data Quality checks are implemented using Pytest: **151 tests**, distributed over three gates by purpose, cost and risk (see [CI/CD Lifecycle](#cicd-lifecycle)).

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
| UPSERT contract (`tests/load/test_load_contract_unit.py`) | Sanity (offline) | Inserted columns = DDL business columns; conflict target = business key (backed by PK/UNIQUE); every non-key column updated from its own `EXCLUDED` value | Runtime behaviour |
| Load freshness (`test_load_freshness`) | Smoke | This run's Load wrote a new row version (`xmin`) for every target row, compared with a baseline captured just before the Load; a no-op Load fails even when the database already held identical rows | Who wrote the row (see [Build isolation](#build-isolation)) |
| Idempotency re-run (`tests/e2e`) | Pre-Merge Regression | A second ETL run leaves every table's content unchanged (hash of every column of every row, including the `cart_items` identity key) while rewriting every row | That the UPDATE writes changed source values (both runs load the same data): covered by the UPSERT contract |

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
Developer
    |
    v
git push (feature branch, no Pull Request yet)
    |
    v
SANITY ---------------------------------------------> Required Quality Gate (no deployment)
    |
    v
Pull Request (opened, or any new push to it)
    |
    v
SANITY -> SMOKE -> PRE-MERGE REGRESSION -> Required Quality Gate
    |
    v
GitHub status continuous-integration/jenkins/pr-merge = SUCCESS (required by branch protection)
    |
    v
Merge to main
    |
    v
SANITY -> Required Quality Gate
    |
    v
Manual Deployment Approval (Jenkins input, 30 minutes)
    |
    v
Fake Deployment
```

The build event alone selects the lifecycle; the pipeline has **no build parameters**, so nothing can make a feature branch skip a gate or deploy.

| Event | Jenkins job | Gates | ETL runs | Tests | Deployment |
|---|---|---|---|---|---|
| Push to a branch without a Pull Request | branch job | Sanity | 0 | 74 | never |
| Pull Request opened or updated | `PR-<n>` | Sanity -> Smoke -> Pre-Merge Regression | 2 | 151 | never |
| Merge to `main` | `main` | Sanity | 0 | 74 | only after manual approval |

The active gate is printed as `Pipeline gate: <SANITY|PRE_MERGE|MAIN>` together with its lifecycle and required suites.

### Gate purposes

| Gate | Question it answers | What runs | Needs | Cost |
|---|---|---|---|---|
| **Sanity** | Is the code structurally healthy enough to continue? | Ruff and every offline test: API client, unit contracts, UPSERT contract and row alignment, orchestration, transform against the independent contract on the committed snapshot | nothing external (the API URL points to a local tripwire; no credentials) | LOW |
| **Smoke** | Does the critical ETL flow still work correctly? | Source reachable, complete and loadable; one real Extract -> Transform -> Load; Load freshness; completeness at every boundary; Processed -> Database on every column; mandatory fields; referential integrity; normalized business keys; the three rules the ETL implements (`full_name`, `" - RP"` suffix, `discounted_price`) | live API, PostgreSQL, one ETL run | MEDIUM |
| **Pre-Merge Regression** | Is the data correct in depth, and is the Load idempotent? | Source data quality; Source -> RAW; RAW -> Processed; Source -> Database; all business rules; control totals (stock, cart totals); business-data drift; ETL re-run for idempotency (last) | live API, PostgreSQL, a second ETL run | MEDIUM (post-load checks reuse Smoke's ETL run), HIGH (idempotency) |

Why three different gates, and why the complete suite does not run on every push:

- A push only has to prove that the code is structurally sound. Sanity answers that in seconds, without the shared database, the external API or any credential. Running the ETL on every push would load the shared database with work in progress and make feedback depend on DummyJSON, without improving the decision a push has to make.
- Smoke proves the critical path end to end on one real run and fails fast: when it fails, the regression (including the ETL re-run) is not spent and the failure is reported as "critical path broken".
- Pre-Merge Regression holds the broad and expensive checks. It runs where it can still block the change (before merge) and is **not** repeated on `main`: the merge is already protected by it.
- Every test belongs to exactly one gate, so no expensive validation runs twice. Some protections are deliberately layered across gates because each layer catches a different failure mode: the static row/column alignment (Sanity) and the runtime Processed -> Database reconciliation (Smoke); fail-fast completeness (Smoke) and the full-value Source -> Database oracle (Regression).

### Why Smoke and Pre-Merge Regression run in the same Pull Request build

Jenkins (GitHub Branch Source) knows a single Pull Request event; it has no separate "pre-merge" event. Both gates therefore run in the `PR-<n>` build, one after the other, and the required GitHub status `continuous-integration/jenkins/pr-merge` is the result of **the whole build**. It can only be SUCCESS when Sanity, Smoke, Pre-Merge Regression and the Required Quality Gate all passed; a green Smoke alone never makes it green.

"Exclude branches that are also filed as PRs" is part of this design: before a Pull Request exists a push builds the branch job (Sanity); once it exists, every push builds only the `PR-<n>` job, which runs Sanity itself as its first gate. The same change is never built as branch and PR at the same time.

### Stages

```text
CI (Windows agent, 20-minute timeout)
  Build Information -> Pipeline Gate -> Workspace Guard -> Setup Python -> Install Dependencies
  SANITY                 Ruff -> API Client -> Unit -> Offline Data Quality            every build
  SMOKE                  Environment Validation -> Source Smoke -> Extract              Pull Request
                         -> Transform -> Load (baseline first) -> Target Smoke
  PRE-MERGE REGRESSION   Source Quality -> Target Quality & Reconciliation             Pull Request
                         -> Idempotency (ETL re-run, always last)
  Required Quality Gate                                                                 every build
  Publish JUnit (always) -> Cleanup
Manual Deployment Approval (no agent, 30 minutes)                                       main
Fake Deployment (Windows agent)                                                         main, approved
```

| Gate | Stage | Selection | Tests | JUnit suite |
|---|---|---|---|---|
| Sanity | API Client | `-m "sanity and api"` | 9 | `sanity-api` |
| Sanity | Unit | `-m "sanity and unit and not api"` | 52 | `sanity-unit` |
| Sanity | Offline Data Quality | `-m "sanity and not unit"` | 13 | `sanity-offline-data` |
| Smoke | Source Smoke | `-m "smoke and live_api and not database and not artifacts"` | 7 | `smoke-source` |
| Smoke | Target Smoke | `-m "smoke and (database or artifacts)"` | 24 | `smoke-target` |
| Regression | Source Quality | `-m "regression and live_api and not database and not artifacts"` | 8 | `regression-source` |
| Regression | Target Quality & Reconciliation | `-m "regression and (database or artifacts) and not e2e"` | 29 | `regression-target` |
| Regression | Idempotency | `-m "regression and e2e" --run-e2e` | 9 | `regression-idempotency` |

Per gate: Sanity 74, Smoke 31, Pre-Merge Regression 46 (151 in total).

Behavior:

- Dependency installation failures stop the build (FAILURE) before any test runs.
- A Ruff failure skips the Sanity tests; a Sanity failure skips Smoke; any Smoke failure (including Environment Validation, Extract, Transform or Load) skips the rest of Smoke and the whole Regression. Inside Sanity and Regression every group runs and publishes its JUnit suite once the gate has started.
- In a Pull Request build, missing CI database configuration or unreachable PostgreSQL is a **FAILURE**: a required gate that cannot run never passes as a skip.
- During Sanity `API_BASE_URL` points to an unreachable local address, so an accidental API request fails immediately.
- The CI part times out after 20 minutes (ABORTED); builds of one job never run concurrently; the last 30 builds are kept.

### Required Quality Gate

The last CI stage runs in every build and fails it unless **all** of the following hold:

- no required stage failed (every guarded stage records its own failure);
- every required JUnit suite exists (a stage that never ran leaves no report) and belongs to the expected suite;
- every required suite collected at least one test;
- no required suite has failures, errors or **skipped** tests (a skipped test proves nothing, e.g. idempotency without `--run-e2e`).

Required suites: the three `sanity-*` suites in every build; in Pull Request builds also `smoke-source`, `smoke-target`, `regression-source`, `regression-target` and `regression-idempotency`. The check is `tests/support/quality_gate.py` (standard library only; prints counts and suite names, never test output):

```text
set PYTHONPATH=tests
python -m support.quality_gate reports sanity-api sanity-unit sanity-offline-data
```

Because the gate fails the build, `continuous-integration/jenkins/pr-merge` cannot be SUCCESS unless Sanity, Smoke, Pre-Merge Regression and the gate itself passed.

### Manual Deployment Approval

- Only a `main` build (never a Pull Request or feature branch) whose CI part passed reaches it; the stage condition and a second scripted guard both enforce this.
- Uses the standard Jenkins `input` step with a **30-minute** timeout. The stage has no agent, so no executor is held while waiting.
- Approver restriction (optional, configured in Jenkins, never in this repository): the global environment variable `DEPLOY_APPROVERS` (Manage Jenkins -> System -> Global properties -> Environment variables) with comma-separated Jenkins user IDs and/or group names. When it is not set, the log prints a warning and any user with Build permission on the job (and administrators) can approve.
- Rejected, aborted or timed out: the build ends **ABORTED**, its description reads `NOT DEPLOYED: ...`, the log prints `DEPLOYMENT DID NOT OCCUR`, and Fake Deployment does not run.
- Builds of `main` are serialized: a newer merge waits until the pending approval is decided or times out.

### Fake Deployment

A laboratory simulation, separate from pytest and from every test: no external system is contacted and nothing is installed. After approval it prints and archives `deployment/deployment-record.txt` (Jenkins build artifact) and sets the build description to `DEPLOYED (simulated): <sha> approved by <user>`. The record contains:

- commit SHA and branch
- Jenkins job, build number and build URL
- the gate that qualified the commit: Pre-Merge Regression and Required Quality Gate of the merged Pull Request (PR number read from the merge commit subject; enforced through the required `pr-merge` status), plus this build's Sanity and Quality Gate
- approver and deployment time (UTC)

No credential is bound in the approval or deployment stages, and no environment is printed.

### Jenkins and GitHub configuration (manual, not changed by this repository)

| Where | Setting | Why |
|---|---|---|
| GitHub branch protection on `main` | Keep `continuous-integration/jenkins/pr-merge` as a required status check | It now reports Sanity + Smoke + Pre-Merge Regression + Quality Gate |
| GitHub branch protection on `main` | Recommended: "Require branches to be up to date before merging" | The tested merge result then equals what lands on `main` |
| Jenkins Multibranch (GitHub Branch Source) | Keep "Exclude branches that are also filed as PRs"; discover Pull Requests by merging with the target branch only | One build per change; no duplicate `pr-head` build |
| Jenkins global properties | Optional `DEPLOY_APPROVERS` | Restricts who may approve deployments |
| Windows agent | Keep a single executor | Build isolation (below) |

### Build isolation

All Pull Request builds share one PostgreSQL database; feature-branch and `main` builds never touch it. Load freshness and idempotency assume that no other build loads it while they run. Assumptions (not enforced by this repository): the Multibranch configuration excludes branch builds for branches that are also Pull Requests, and builds are serialized on the Windows agent (a single executor). Two concurrent Pull Request builds could otherwise interleave their Loads. If that becomes possible, add a Jenkins lock around the SMOKE and PRE-MERGE REGRESSION stages.

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

The credential is bound with `withCredentials` only around the steps that connect to PostgreSQL (Environment Validation, Load, Target Smoke, Target Quality & Reconciliation, Idempotency), so Jenkins masks both values in the log. Sanity, Source Smoke, Source Quality, the approval and the deployment stages never receive it.

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
 Sanity -> Smoke -> Pre-Merge Regression
        |
        v
 Required Quality Gate (continuous-integration/jenkins/pr-merge)
        |
        v
       main -> Manual Deployment Approval -> Fake Deployment
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
5. Run Sanity (Ruff + 74 offline tests) in every build.
6. In Pull Request builds, run Smoke (one real ETL into PostgreSQL + 31 critical-path checks) and Pre-Merge Regression (46 deep checks, including an ETL re-run for idempotency).
7. Run the Required Quality Gate, publish JUnit results and report the result to GitHub.
8. On `main`, wait for manual deployment approval and run the Fake Deployment.

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

No time-based trigger is configured yet. The complete regression, including the ETL re-run for idempotency, runs in every Pull Request build.

---

## Pipeline Quality Gate

Expected behavior of a Pull Request build (see [Required Quality Gate](#required-quality-gate)):

```text
Sanity (Ruff + offline tests)
  |
  v
Smoke (one real ETL + critical-path checks)
  |
  v
Pre-Merge Regression (deep reconciliation + idempotency)
  |
  v
Required Quality Gate
  |
  +---- every required stage passed and every
  |     required suite ran completely ---------> SUCCESS -> pr-merge green -> merge allowed
  |
  +---- any failure, missing/empty suite,
        skipped test or missing DB config -----> FAILURE -> pr-merge red  -> merge blocked
```

A successful Pull Request build reports:

```text
Pipeline gate: PRE_MERGE
REQUIRED QUALITY GATE
suite                     tests  failed  errors  skipped  verdict
sanity-api                    9       0       0        0  PASS
sanity-unit                  52       0       0        0  PASS
sanity-offline-data          13       0       0        0  PASS
smoke-source                  7       0       0        0  PASS
smoke-target                 24       0       0        0  PASS
regression-source             8       0       0        0  PASS
regression-target            29       0       0        0  PASS
regression-idempotency        9       0       0        0  PASS
Quality Gate PASSED: 8 required suites complete
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
- [x] Sanity gate on every build (Ruff + 74 offline tests)
- [x] Event-based lifecycle in one Jenkinsfile: Sanity (push), Smoke + Pre-Merge Regression (Pull Request), Required Quality Gate
- [x] Manual Deployment Approval and Fake Deployment from `main` (simulated CD)
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
