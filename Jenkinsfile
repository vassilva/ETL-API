// ETL-API CI/CD pipeline (single Jenkinsfile, single Multibranch Pipeline)
//
// The build event alone selects the lifecycle; there are no build parameters
// (see README "CI/CD Lifecycle"):
//
//   Feature branch push (no PR)  SANITY -> Required Quality Gate. No deployment.
//   Pull Request (PR-N job)      SANITY -> SMOKE -> PRE-MERGE REGRESSION
//                                -> Required Quality Gate. No deployment.
//                                This build is the required GitHub status
//                                continuous-integration/jenkins/pr-merge.
//   main                         SANITY -> Required Quality Gate
//                                -> Manual Deployment Approval -> Fake Deployment
//
// Jenkins (GitHub Branch Source) has a single Pull Request event, so SMOKE
// and PRE-MERGE REGRESSION are two gates of the same PR build: pr-merge is the
// result of the whole build and can never be SUCCESS after Smoke alone. The
// Required Quality Gate fails the build when a required stage failed or a
// required suite is missing, collected zero tests or skipped tests.
//
// Deployment is simulated and never automatic: main only, after the Quality
// Gate and after explicit approval (Jenkins input, 30 minutes). No executor is
// held while waiting. Optional approver restriction: DEPLOY_APPROVERS (see
// README "Manual Deployment Approval").
//
// Database configuration (values never live in this file):
//   DB_HOST, DB_PORT, DB_NAME  environment variables of the Windows agent
//                              (Jenkins node properties; not secrets)
//   DB_USER, DB_PASSWORD       Jenkins credential DB_CREDENTIALS_ID
//                              ("Username with password"), bound only to the
//                              steps that connect to PostgreSQL
//
// Build isolation: only Pull Request builds touch the shared PostgreSQL
// database. Load freshness and idempotency assume no other build loads it at
// the same time; see README "Build isolation".

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

                            // Only main uses it: the PR whose pr-merge gate qualified the merge
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
                            def sanitySuites = 'sanity-api sanity-unit sanity-offline-data'

                            if (env.CHANGE_ID) {
                                env.PIPELINE_GATE = 'PRE_MERGE'
                                env.GATE_FLOW = 'SANITY -> SMOKE -> PRE-MERGE REGRESSION -> REQUIRED QUALITY GATE (GitHub status continuous-integration/jenkins/pr-merge). No deployment.'
                                env.REQUIRED_SUITES = "${sanitySuites} smoke-source smoke-target regression-source regression-target regression-idempotency"
                            } else if (env.BRANCH_NAME == 'main') {
                                env.PIPELINE_GATE = 'MAIN'
                                env.GATE_FLOW = 'SANITY -> REQUIRED QUALITY GATE -> MANUAL DEPLOYMENT APPROVAL -> FAKE DEPLOYMENT'
                                env.REQUIRED_SUITES = sanitySuites
                            } else {
                                env.PIPELINE_GATE = 'SANITY'
                                env.GATE_FLOW = 'SANITY -> REQUIRED QUALITY GATE. No deployment.'
                                env.REQUIRED_SUITES = sanitySuites
                            }

                            echo "Pipeline gate: ${env.PIPELINE_GATE}"
                            echo "Lifecycle: ${env.GATE_FLOW}"
                            echo "Required suites: ${env.REQUIRED_SUITES}"
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

                        // Remove stale JUnit reports (git-ignored, never tracked)
                        bat 'if exist reports\\*.xml del /q reports\\*.xml'
                    }
                }

                stage('Setup Python') {
                    steps {
                        bat 'python --version'
                        bat 'if exist .venv rmdir /s /q .venv'
                        bat 'python -m venv .venv'
                    }
                }

                stage('Install Dependencies') {
                    steps {
                        bat '%VENV_PY% -m pip install -r requirements-dev.txt'
                        bat '%VENV_PY% -m pip check'
                    }
                }

                // Push gate: structural health, offline only (no network,
                // database or runtime artifacts; no credentials)
                stage('SANITY') {
                    environment {
                        // Tripwire: an accidental API request fails locally
                        // instead of reaching the real external API.
                        API_BASE_URL = 'http://127.0.0.1:9'
                    }

                    stages {
                        stage('Ruff') {
                            steps {
                                script {
                                    def passed = runGuarded { bat '%VENV_PY% -m ruff check src tests --no-cache' }
                                    env.RUFF_PASSED = passed ? 'true' : 'false'
                                }
                            }
                        }

                        // Three disjoint offline selections; after Ruff passed,
                        // each always runs and publishes its results.
                        stage('API Client') {
                            when { environment name: 'RUFF_PASSED', value: 'true' }
                            steps {
                                script { runPytest('sanity and api', 'sanity-api') }
                            }
                        }

                        stage('Unit') {
                            when { environment name: 'RUFF_PASSED', value: 'true' }
                            steps {
                                script { runPytest('sanity and unit and not api', 'sanity-unit') }
                            }
                        }

                        stage('Offline Data Quality') {
                            when { environment name: 'RUFF_PASSED', value: 'true' }
                            steps {
                                script { runPytest('sanity and not unit', 'sanity-offline-data') }
                            }
                        }
                    }
                }

                // PR gate: the critical ETL path on one real run. Runs only
                // when Sanity passed; every step requires the previous ones.
                stage('SMOKE') {
                    when { expression { env.PIPELINE_GATE == 'PRE_MERGE' && ciHealthy() } }

                    stages {
                        stage('Environment Validation') {
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

                        // Source reachable, complete and loadable, before the ETL
                        stage('Source Smoke') {
                            when { expression { ciHealthy() } }
                            steps {
                                script { runPytest('smoke and live_api and not database and not artifacts', 'smoke-source') }
                            }
                        }

                        // Extract -> Transform -> Load run the real pipeline once,
                        // one stage at a time. A failure stops the remaining stages.
                        stage('Extract') {
                            when { expression { ciHealthy() } }
                            steps {
                                script { runGuarded { bat '%VENV_PY% src\\main.py --stage extract' } }
                            }
                        }

                        stage('Transform') {
                            when { expression { ciHealthy() } }
                            steps {
                                script { runGuarded { bat '%VENV_PY% src\\main.py --stage transform' } }
                            }
                        }

                        stage('Load') {
                            when { expression { ciHealthy() } }
                            steps {
                                script {
                                    runGuarded {
                                        withDatabaseCredentials {
                                            // Row versions before the Load (read-only), so the
                                            // smoke checks can prove this Load wrote every row
                                            bat 'set PYTHONPATH=src;tests&& %VENV_PY% -m support.load_freshness'
                                            bat '%VENV_PY% src\\main.py --stage load'
                                        }
                                    }
                                }
                            }
                        }

                        stage('Target Smoke') {
                            when { expression { ciHealthy() } }
                            steps {
                                script {
                                    withDatabaseCredentials { runPytest('smoke and (database or artifacts)', 'smoke-target') }
                                }
                            }
                        }
                    }
                }

                // Pre-merge gate: deep data quality and reconciliation on the
                // same ETL run, then idempotency. Runs only when Smoke passed;
                // after that each group always runs and publishes its results.
                stage('PRE-MERGE REGRESSION') {
                    when { expression { env.PIPELINE_GATE == 'PRE_MERGE' && ciHealthy() } }

                    stages {
                        stage('Source Quality') {
                            steps {
                                script { runPytest('regression and live_api and not database and not artifacts', 'regression-source') }
                            }
                        }

                        stage('Target Quality & Reconciliation') {
                            steps {
                                script {
                                    withDatabaseCredentials {
                                        runPytest('regression and (database or artifacts) and not e2e', 'regression-target')
                                    }
                                }
                            }
                        }

                        // Last: re-runs the ETL (writes data/ and PostgreSQL), so
                        // every other check has already read this build's Load
                        stage('Idempotency') {
                            steps {
                                script {
                                    withDatabaseCredentials {
                                        runPytest('regression and e2e', 'regression-idempotency', '--run-e2e')
                                    }
                                }
                            }
                        }
                    }
                }

                // Always evaluated: the build (and therefore pr-merge) can only
                // be SUCCESS when every required stage passed and every
                // required suite really executed
                stage('Required Quality Gate') {
                    steps {
                        script {
                            def reportsStatus = bat(
                                returnStatus: true,
                                script: "set PYTHONPATH=tests&& %VENV_PY% -m support.quality_gate reports ${env.REQUIRED_SUITES}"
                            )

                            echo "Failed required stages: ${env.FAILED_STAGES ?: 'none'}"

                            if (reportsStatus != 0 || !ciHealthy() || currentBuild.currentResult != 'SUCCESS') {
                                currentBuild.description = "QUALITY GATE FAILED (${env.PIPELINE_GATE})"
                                error("REQUIRED QUALITY GATE FAILED (${env.PIPELINE_GATE}): see the suite table and the failed stages above.")
                            }

                            currentBuild.description = "Quality Gate passed (${env.PIPELINE_GATE})"
                            echo "REQUIRED QUALITY GATE PASSED (${env.PIPELINE_GATE})"
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
                        ? "PRE-MERGE REGRESSION + Required Quality Gate of PR #${env.QUALIFYING_PR}"
                        : 'PRE-MERGE REGRESSION + Required Quality Gate of the merged PR (number not found in the merge commit subject)'

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
                     + MAIN SANITY + Required Quality Gate in build #${env.BUILD_NUMBER}
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
                    echo "main: Sanity and Quality Gate passed; commit ${shortSha()} DEPLOYED (simulated) after approval by ${env.DEPLOY_APPROVER}."
                } else {
                    echo "Pipeline gate ${env.PIPELINE_GATE}: all required validations passed. No deployment (only main can deploy)."
                }
            }
        }

        failure {
            echo "Pipeline gate ${env.PIPELINE_GATE}: FAILED. Check the Required Quality Gate table and the stage logs. No deployment occurred."
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

// Runs body and returns true when it succeeded. A failure records the stage
// for the Required Quality Gate, marks the stage and the build FAILURE (the
// original error is logged by catchError) and lets the pipeline reach the
// gate. Aborts (timeout, manual abort) are never swallowed.
def runGuarded(Closure body) {
    try {
        body()
        return true
    } catch (InterruptedException interruption) {
        throw interruption
    } catch (failure) {
        env.FAILED_STAGES = env.FAILED_STAGES ? "${env.FAILED_STAGES}, ${env.STAGE_NAME}" : env.STAGE_NAME

        catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
            throw failure
        }

        return false
    }
}

// True while no required stage of this build has failed
def ciHealthy() {
    return !env.FAILED_STAGES
}

// Runs one pytest marker selection as its own JUnit suite (reports/<suite>.xml,
// verified by the Required Quality Gate)
def runPytest(String markers, String suite, String extraArgs = '') {
    return runGuarded {
        bat "%VENV_PY% -m pytest -m \"${markers}\" ${extraArgs} %PYTEST_OPTS% -o junit_suite_name=${suite} --junitxml=reports\\${suite}.xml"
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
    if (env.CHANGE_ID || env.BRANCH_NAME != 'main' || env.PIPELINE_GATE != 'MAIN') {
        error("Deployment refused: only main builds can deploy (branch ${env.BRANCH_NAME}, change ${env.CHANGE_ID ?: 'none'}).")
    }
}

def shortSha() {
    def sha = env.COMMIT_SHA ?: ''

    return sha.length() > 7 ? sha.substring(0, 7) : sha
}

// PR number from a GitHub merge commit subject: "Merge pull request #N from ..."
// (merge commit) or "Title (#N)" (squash merge); '' when not found
@NonCPS
def pullRequestNumber(String subject) {
    def matcher = subject =~ /Merge pull request #(\d+)|\(#(\d+)\)\s*$/

    return matcher.find() ? (matcher.group(1) ?: matcher.group(2)) : ''
}
