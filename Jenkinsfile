// ETL-API CI/CD pipeline (single Jenkinsfile, single Multibranch Pipeline)
//
// The build event alone selects the lifecycle; there are no build parameters
// (see README "CI/CD Lifecycle"):
//
//   Feature branch push (no PR)  Ruff -> Smoke (18, offline) -> Push Gate.
//                                No ETL, no API, no database, no deployment.
//   Pull Request (PR-N job)      Ruff -> PR Offline (37) -> Environment
//                                Validation -> Source Critical (3) -> Extract
//                                -> Transform -> Load -> Target and
//                                Reconciliation (17) -> PR Gate. One ETL run.
//                                This build is the required GitHub status
//                                continuous-integration/jenkins/pr-merge.
//   main                         Main Evidence: the merged tree is proven
//                                identical to the PR-validated tree -> 0 tests;
//                                otherwise (unknown = fallback) Ruff + Smoke.
//                                -> Main Gate -> Manual Approval -> Fake Deploy.
//
// The Full Regression (all 151 tests) is LOCAL ONLY: no Jenkins path runs it.
//
// Fail fast: every stage requires all earlier stages to have succeeded; the
// Required Quality Gate always runs and fails the build unless every required
// stage completed and every required test (exact profile in
// tests/support/ci_profiles.py) passed. Required failures end as FAILURE,
// never UNSTABLE or SUCCESS; timeouts and manual aborts end as ABORTED. A
// build that is not SUCCESS never reports a successful pr-merge status and
// never deploys.
//
// Database configuration (values never live in this file):
//   DB_HOST, DB_PORT, DB_NAME  environment variables of the Windows agent
//                              (Jenkins node properties; not secrets)
//   DB_USER, DB_PASSWORD       Jenkins credential DB_CREDENTIALS_ID
//                              ("Username with password"), bound only to the
//                              steps that connect to PostgreSQL
//
// Build isolation: only Pull Request builds touch the shared PostgreSQL
// database. Load freshness assumes no other build loads it at the same time;
// see README "Build isolation".

pipeline {
    // Agents are allocated per stage, so waiting for deployment approval
    // never holds the executor
    agent none

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }

    environment {
        PYTHONUTF8 = '1'
        PYTHONDONTWRITEBYTECODE = '1'
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
        VENV_PY = '.venv\\Scripts\\python.exe'
        PYTEST_OPTS = '-v -p no:cacheprovider'
        DB_CREDENTIALS_ID = 'postgres-etl-api'
    }

    stages {
        stage('CI') {
            agent { label 'windows' }

            options {
                timeout(time: 20, unit: 'MINUTES')
            }

            stages {
                stage('Build Information') {
                    steps {
                        script {
                            env.COMMIT_SHA = bat(returnStdout: true, script: '@git rev-parse HEAD').trim()

                            // main: the PR whose pr-merge gate qualified the merge
                            def subject = bat(returnStdout: true, script: '@git log -1 --format=%%s').trim()
                            env.QUALIFYING_PR = pullRequestNumber(subject)

                            echo """\
========================================
CI BUILD INFORMATION
========================================
Branch:       ${env.BRANCH_NAME}
Pull Request: ${env.CHANGE_ID ? "#${env.CHANGE_ID} (target ${env.CHANGE_TARGET})" : 'none'}
Commit:       ${env.COMMIT_SHA}
========================================"""
                        }
                    }
                }

                stage('Pipeline Gate') {
                    steps {
                        script {
                            if (env.CHANGE_ID) {
                                env.PIPELINE_GATE = 'PR'
                                env.GATE_FLOW = 'Ruff -> PR Offline -> Environment Validation -> Source Critical -> Extract -> Transform -> Load -> Target and Reconciliation -> PR Gate (GitHub status continuous-integration/jenkins/pr-merge). No deployment.'
                            } else if (env.BRANCH_NAME == 'main') {
                                env.PIPELINE_GATE = 'MAIN'
                                env.GATE_FLOW = 'Main Evidence (tree identity; otherwise Ruff + Smoke) -> Main Gate -> Manual Deployment Approval -> Fake Deployment'
                            } else {
                                env.PIPELINE_GATE = 'PUSH'
                                env.GATE_FLOW = 'Ruff -> Smoke -> Push Gate. No deployment.'
                            }

                            echo "Pipeline gate: ${env.PIPELINE_GATE}"
                            echo "Lifecycle: ${env.GATE_FLOW}"
                        }
                    }
                }

                // main only: is this exactly the tree the PR build validated?
                stage('Main Evidence') {
                    when { expression { env.PIPELINE_GATE == 'MAIN' } }
                    steps {
                        script {
                            def evidence = mainEvidence()
                            env.MAIN_TEST_MODE = evidence.mode
                            echo "MAIN_TEST_MODE = ${evidence.mode}: ${evidence.reason}"
                            markCompleted()
                        }
                    }
                }

                stage('Workspace Guard') {
                    steps {
                        // Fail if a local .env exists: CI must never load local credentials.
                        // Only existence is checked; the file is never read or printed.
                        bat '''
                        if exist .env (
                            echo ERROR: a .env file must not exist in the CI workspace.
                            exit /b 1
                        )
                        '''

                        // Runtime artifacts must be produced by THIS build: stale
                        // RAW/Processed files or a stale Load baseline could make
                        // the checks pass on old data
                        bat '''
                        @echo off
                        for %%D in (data\\raw data\\processed data\\state) do (
                            if exist %%D (
                                echo ERROR: stale runtime directory %%D exists before the build.
                                exit /b 1
                            )
                        )
                        echo No stale runtime artifacts.
                        '''

                        // Remove stale JUnit reports (git-ignored, never tracked)
                        bat 'if exist reports\\*.xml del /q reports\\*.xml'
                    }
                }

                stage('Setup Python') {
                    when { expression { needsPython() } }
                    steps {
                        bat 'python --version'
                        bat 'if exist .venv rmdir /s /q .venv'
                        bat 'python -m venv .venv'
                    }
                }

                stage('Install Dependencies') {
                    when { expression { needsPython() } }
                    steps {
                        bat '%VENV_PY% -m pip install -r requirements-dev.txt'
                        bat '%VENV_PY% -m pip check'
                    }
                }

                stage('Ruff') {
                    when { expression { needsPython() && ciHealthy() } }
                    steps {
                        script {
                            runGuarded { bat '%VENV_PY% -m ruff check src tests --no-cache' }
                        }
                    }
                }

                // Push (and main fallback): fundamental offline code contracts
                stage('Smoke') {
                    when { expression { (env.PIPELINE_GATE == 'PUSH' || env.MAIN_TEST_MODE == 'SMOKE_FALLBACK') && ciHealthy() } }
                    environment {
                        // Tripwire: an accidental API request fails locally
                        API_BASE_URL = 'http://127.0.0.1:9'
                    }
                    steps {
                        script { runPytest('smoke', 'smoke') }
                    }
                }

                // PR: Smoke re-run on the merge candidate + offline merge
                // preconditions (defects the runtime checks cannot see)
                stage('PR Offline') {
                    when { expression { env.PIPELINE_GATE == 'PR' && ciHealthy() } }
                    environment {
                        API_BASE_URL = 'http://127.0.0.1:9'
                    }
                    steps {
                        script { runPytest('(smoke or regression) and not integration', 'pr-offline') }
                    }
                }

                stage('Environment Validation') {
                    when { expression { env.PIPELINE_GATE == 'PR' && ciHealthy() } }
                    steps {
                        script {
                            runGuarded {
                                // Only variable names are printed, never values
                                def agentSettingsMissing = bat(returnStatus: true, script: '''
                                    @echo off
                                    set MISSING=
                                    if not defined DB_HOST set MISSING=%MISSING% DB_HOST
                                    if not defined DB_PORT set MISSING=%MISSING% DB_PORT
                                    if not defined DB_NAME set MISSING=%MISSING% DB_NAME
                                    if defined MISSING (
                                        echo Missing agent environment variables:%MISSING%
                                        exit /b 1
                                    )
                                    echo Agent environment variables DB_HOST, DB_PORT and DB_NAME are defined.
                                ''') != 0

                                def credentialFound = true
                                try {
                                    withDatabaseCredentials {
                                        echo "Jenkins credential '${env.DB_CREDENTIALS_ID}' is available."
                                    }
                                } catch (InterruptedException interruption) {
                                    throw interruption
                                } catch (lookupFailure) {
                                    credentialFound = false
                                    echo "Jenkins credential '${env.DB_CREDENTIALS_ID}' was not found or is not of type 'Username with password'."
                                }

                                // A required gate that cannot run is a failure, never a skip
                                if (agentSettingsMissing || !credentialFound) {
                                    error('The CI database configuration is incomplete (see this log). A Pull Request cannot pass the required quality gate without PostgreSQL.')
                                }

                                // Configured but unreachable is a real failure.
                                // Read-only connection; the error message never
                                // contains connection details.
                                withDatabaseCredentials {
                                    bat 'set PYTHONPATH=src&& %VENV_PY% -m database.connection'
                                }
                            }
                        }
                    }
                }

                // Merge-blocking source contract: the complete collection
                stage('Source Critical') {
                    when { expression { env.PIPELINE_GATE == 'PR' && ciHealthy() } }
                    steps {
                        script { runPytest('regression and live_api and not database and not artifacts', 'pr-source') }
                    }
                }

                // Extract -> Transform -> Load run the real pipeline once. Each
                // stage proves its artifacts were written by this run (the
                // workspace started without runtime artifacts).
                stage('Extract') {
                    when { expression { env.PIPELINE_GATE == 'PR' && ciHealthy() } }
                    steps {
                        script {
                            runGuarded {
                                bat '%VENV_PY% src\\main.py --stage extract'
                                requireArtifacts('raw')
                            }
                        }
                    }
                }

                stage('Transform') {
                    when { expression { env.PIPELINE_GATE == 'PR' && ciHealthy() } }
                    steps {
                        script {
                            runGuarded {
                                bat '%VENV_PY% src\\main.py --stage transform'
                                requireArtifacts('processed')
                            }
                        }
                    }
                }

                stage('Load') {
                    when { expression { env.PIPELINE_GATE == 'PR' && ciHealthy() } }
                    steps {
                        script {
                            runGuarded {
                                withDatabaseCredentials {
                                    // Row versions before the Load (read-only), so
                                    // Load freshness can prove this Load wrote every row
                                    bat 'set PYTHONPATH=src;tests&& %VENV_PY% -m support.load_freshness'
                                    bat '%VENV_PY% src\\main.py --stage load'
                                }
                            }
                        }
                    }
                }

                // Freshness, completeness, Source -> Database, control totals
                // and the critical business rules on this run's data
                stage('Target and Reconciliation') {
                    when { expression { env.PIPELINE_GATE == 'PR' && ciHealthy() } }
                    steps {
                        script {
                            withDatabaseCredentials {
                                runPytest('regression and (database or artifacts)', 'pr-target')
                            }
                        }
                    }
                }

                // Always evaluated: the build (and therefore pr-merge and any
                // deployment) can only succeed when every required stage
                // completed and the exact required tests all passed
                stage('Required Quality Gate') {
                    steps {
                        script {
                            def profile = gateProfile()

                            // Standard-library only: runs without the venv (main evidence mode)
                            def gateStatus = bat(
                                returnStatus: true,
                                script: "set PYTHONPATH=tests&& python -m support.quality_gate --profile ${profile} --reports reports --completed-stages \"%COMPLETED_STAGES%\""
                            )

                            echo "Failed required stages: ${env.FAILED_STAGES ?: 'none'}"

                            if (gateStatus != 0 || !ciHealthy() || currentBuild.currentResult != 'SUCCESS') {
                                currentBuild.description = "QUALITY GATE FAILED (${profile})"
                                error("REQUIRED QUALITY GATE FAILED (${profile}): see the gate report and the failed stages above.")
                            }

                            env.QUALITY_GATE_PASSED = 'true'
                            currentBuild.description = "Quality Gate passed (${profile})"
                            echo "REQUIRED QUALITY GATE PASSED (${profile})"
                        }
                    }
                }
            }

            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/*.xml'
                }

                cleanup {
                    deleteDir()
                }
            }
        }

        // No agent: the build waits without holding an executor
        stage('Manual Deployment Approval') {
            when {
                allOf {
                    branch 'main'
                    not { changeRequest() }
                    environment name: 'QUALITY_GATE_PASSED', value: 'true'
                    expression { currentBuild.currentResult == 'SUCCESS' }
                }
            }
            steps {
                script {
                    ensureDeploymentEligible()

                    def request = [
                        message: "Deploy ETL-API commit ${shortSha()} from main to LAB (simulated deployment)?",
                        ok: 'Approve deployment',
                        submitterParameter: 'APPROVER'
                    ]
                    def approvers = env.DEPLOY_APPROVERS?.trim()

                    if (approvers) {
                        request.submitter = approvers
                        echo "Approval restricted to DEPLOY_APPROVERS: ${approvers}"
                    } else {
                        echo 'WARNING: DEPLOY_APPROVERS is not configured, so any user with Build permission on this job (and administrators) can approve. See README "Manual Deployment Approval".'
                    }

                    env.APPROVAL_REQUESTED = 'true'
                    echo 'Waiting up to 30 minutes for manual deployment approval (no executor is held).'

                    try {
                        timeout(time: 30, unit: 'MINUTES') {
                            def answer = input(request)
                            env.DEPLOY_APPROVER = (answer instanceof Map) ? answer.APPROVER : answer
                        }
                    } catch (notApproved) {
                        // Rejected, aborted or timed out: Fake Deployment never runs
                        currentBuild.result = 'ABORTED'
                        currentBuild.description = "NOT DEPLOYED: approval rejected, aborted or timed out (${shortSha()})"
                        echo """\
========================================
DEPLOYMENT DID NOT OCCUR
========================================
Commit:  ${env.COMMIT_SHA}
Reason:  approval rejected, aborted or timed out (30 minutes)
Result:  ABORTED - Fake Deployment was not executed
========================================"""
                        throw notApproved
                    }

                    env.DEPLOYMENT_APPROVED = 'true'
                    echo "Deployment approved by ${env.DEPLOY_APPROVER}"
                }
            }
        }

        // Simulation only: no external system is contacted, nothing is
        // installed. Not a test: pytest is not involved.
        stage('Fake Deployment') {
            agent { label 'windows' }

            options {
                skipDefaultCheckout()
            }

            when {
                beforeAgent true
                allOf {
                    branch 'main'
                    not { changeRequest() }
                    environment name: 'QUALITY_GATE_PASSED', value: 'true'
                    environment name: 'DEPLOYMENT_APPROVED', value: 'true'
                }
            }

            steps {
                script {
                    ensureDeploymentEligible()

                    def deployedAt = powershell(
                        returnStdout: true,
                        script: "[DateTime]::UtcNow.ToString('yyyy-MM-dd HH:mm:ss') + ' UTC'"
                    ).trim()

                    def qualifiedBy = env.QUALIFYING_PR
                        ? "PR ETL Regression + PR Quality Gate of PR #${env.QUALIFYING_PR}"
                        : 'PR ETL Regression + PR Quality Gate of the merged PR (number not found in the merge commit subject)'

                    def mainValidation = env.MAIN_TEST_MODE == 'EVIDENCE_ONLY'
                        ? 'Main Evidence: merged tree identical to the PR-validated tree (0 tests re-run)'
                        : 'Main Evidence not provable: Ruff + Smoke fallback passed'

                    def record = """\
========================================
FAKE DEPLOYMENT (SIMULATION - no external system contacted)
========================================
Application:         ETL-API
Target environment:  LAB (simulated)
Commit SHA:          ${env.COMMIT_SHA}
Branch:              ${env.BRANCH_NAME}
Jenkins job:         ${env.JOB_NAME}
Jenkins build:       #${env.BUILD_NUMBER}
Build URL:           ${env.BUILD_URL ?: '(Jenkins URL not configured)'}
Qualified by:        ${qualifiedBy}
                     (required GitHub status continuous-integration/jenkins/pr-merge,
                     enforced by branch protection on main)
Main validation:     ${mainValidation} + Main Gate in build #${env.BUILD_NUMBER}
Approved by:         ${env.DEPLOY_APPROVER}
Deployment time:     ${deployedAt}
Result:              DEPLOYED (simulated)
========================================
"""

                    writeFile file: 'deployment/deployment-record.txt', text: record, encoding: 'UTF-8'
                    archiveArtifacts artifacts: 'deployment/deployment-record.txt'
                    echo record

                    currentBuild.description = "DEPLOYED (simulated): ${shortSha()} approved by ${env.DEPLOY_APPROVER}"
                }
            }

            post {
                cleanup {
                    deleteDir()
                }
            }
        }
    }

    post {
        success {
            script {
                if (env.PIPELINE_GATE == 'MAIN') {
                    echo "main: Main Gate passed (${env.MAIN_TEST_MODE}); commit ${shortSha()} DEPLOYED (simulated) after approval by ${env.DEPLOY_APPROVER}."
                } else {
                    echo "Pipeline gate ${env.PIPELINE_GATE}: all required validations passed. No deployment (only main can deploy)."
                }
            }
        }

        failure {
            echo "Pipeline gate ${env.PIPELINE_GATE}: FAILED. Check the Required Quality Gate report and the stage logs. No deployment occurred."
        }

        aborted {
            script {
                if (env.APPROVAL_REQUESTED == 'true' && env.DEPLOYMENT_APPROVED != 'true') {
                    echo "main: NOT DEPLOYED. Deployment approval was rejected, aborted or timed out; Fake Deployment did not run (commit ${shortSha()})."
                } else {
                    echo "Pipeline gate ${env.PIPELINE_GATE}: ABORTED (timeout or manual abort). No deployment occurred."
                }
            }
        }
    }
}

// Runs body and returns true when it succeeded. Success records the stage as
// completed evidence for the Required Quality Gate. A failure records the
// stage as failed, marks the stage and the build FAILURE (the original error
// is logged by catchError) and lets the pipeline reach the gate. Aborts
// (timeout, manual abort) are never swallowed.
def runGuarded(Closure body) {
    try {
        body()
    } catch (InterruptedException interruption) {
        throw interruption
    } catch (failure) {
        env.FAILED_STAGES = env.FAILED_STAGES ? "${env.FAILED_STAGES}, ${env.STAGE_NAME}" : env.STAGE_NAME

        catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
            throw failure
        }

        return false
    }

    markCompleted()
    return true
}

def markCompleted() {
    env.COMPLETED_STAGES = env.COMPLETED_STAGES ? "${env.COMPLETED_STAGES},${env.STAGE_NAME}" : env.STAGE_NAME
}

// True while no required stage of this build has failed
def ciHealthy() {
    return !env.FAILED_STAGES
}

// Every lifecycle except a proven main evidence build needs the venv
def needsPython() {
    return env.MAIN_TEST_MODE != 'EVIDENCE_ONLY'
}

def gateProfile() {
    if (env.PIPELINE_GATE == 'PR') {
        return 'pr'
    }

    if (env.PIPELINE_GATE == 'MAIN') {
        return env.MAIN_TEST_MODE == 'EVIDENCE_ONLY' ? 'main-evidence' : 'main-fallback'
    }

    return 'push'
}

// Runs one pytest marker selection as its own JUnit suite (reports/<suite>.xml,
// verified by the Required Quality Gate). No -x: every failure of the suite
// is reported; the next stage is skipped by the fail-fast conditions.
def runPytest(String markers, String suite, String extraArgs = '') {
    return runGuarded {
        bat "%VENV_PY% -m pytest -m \"${markers}\" ${extraArgs} %PYTEST_OPTS% -o junit_suite_name=${suite} --junitxml=reports\\${suite}.xml"
    }
}

// Fails unless the stage wrote all three runtime artifacts in data\<kind>
def requireArtifacts(String kind) {
    bat """
    @echo off
    for %%R in (users products carts) do (
        if not exist data\\${kind}\\%%R.json (
            echo ERROR: data\\${kind}\\%%R.json was not written by this run.
            exit /b 1
        )
    )
    echo This run wrote data\\${kind}: users, products, carts.
    """
}

// main: EVIDENCE_ONLY only when HEAD is a two-parent GitHub PR merge commit
// whose tree is identical to its PR head tree (the tree the PR build
// validated). Anything else, including any error, is SMOKE_FALLBACK:
// unknown never counts as valid. Uses %T (tree hash) instead of HEAD^2
// syntax, because ^ is the escape character of cmd.
def mainEvidence() {
    try {
        def parents = bat(returnStdout: true, script: '@git rev-list --parents -n 1 HEAD').trim().tokenize(' ')

        if (parents.size() != 3) {
            return [mode: 'SMOKE_FALLBACK', reason: "HEAD is not a two-parent merge commit (${parents.size() - 1} parent(s))"]
        }

        if (!env.QUALIFYING_PR) {
            return [mode: 'SMOKE_FALLBACK', reason: 'the merge commit subject names no GitHub pull request']
        }

        def prHead = parents[2]

        if (!isSha(prHead)) {
            return [mode: 'SMOKE_FALLBACK', reason: 'the PR head commit could not be identified']
        }

        def mergeTree = bat(returnStdout: true, script: '@git log -1 --format=%%T HEAD').trim()
        def prTree = bat(returnStdout: true, script: "@git log -1 --format=%%T ${prHead}").trim()

        if (!isSha(mergeTree) || mergeTree != prTree) {
            return [mode: 'SMOKE_FALLBACK', reason: "merged tree ${mergeTree} differs from PR #${env.QUALIFYING_PR} head tree ${prTree}"]
        }

        return [mode: 'EVIDENCE_ONLY', reason: "merged tree ${mergeTree} == PR #${env.QUALIFYING_PR} head tree (validated by its pr-merge build)"]
    } catch (InterruptedException interruption) {
        throw interruption
    } catch (evidenceError) {
        return [mode: 'SMOKE_FALLBACK', reason: 'the evidence could not be determined']
    }
}

// Binds DB_USER and DB_PASSWORD for the enclosed steps only. Jenkins masks
// both values in the build log.
def withDatabaseCredentials(Closure body) {
    withCredentials([usernamePassword(
        credentialsId: env.DB_CREDENTIALS_ID,
        usernameVariable: 'DB_USER',
        passwordVariable: 'DB_PASSWORD'
    )]) {
        body()
    }
}

// Second, independent guard besides the stage 'when': deployment is only
// possible from a main branch build, never from a PR or a feature branch
def ensureDeploymentEligible() {
    if (env.CHANGE_ID || env.BRANCH_NAME != 'main' || env.PIPELINE_GATE != 'MAIN' || env.QUALITY_GATE_PASSED != 'true') {
        error("Deployment refused: only a main build that passed the Main Gate can deploy (branch ${env.BRANCH_NAME}, change ${env.CHANGE_ID ?: 'none'}).")
    }
}

def shortSha() {
    def sha = env.COMMIT_SHA ?: ''

    return sha.length() > 7 ? sha.substring(0, 7) : sha
}

@NonCPS
def isSha(String value) {
    return value ==~ /[0-9a-f]{40}/
}

// PR number from a GitHub merge commit subject: "Merge pull request #N from ..."
// (merge commit) or "Title (#N)" (squash merge); '' when not found
@NonCPS
def pullRequestNumber(String subject) {
    def matcher = subject =~ /Merge pull request #(\d+)|\(#(\d+)\)\s*$/

    return matcher.find() ? (matcher.group(1) ?: matcher.group(2)) : ''
}
