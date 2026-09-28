// ETL-API CI pipeline (single Multibranch Pipeline)
//
// 1. Offline Quality Gate: Ruff + 92 offline tests. No live API, no
//    PostgreSQL, no credentials.
// 2. Real Integration / E2E: live DummyJSON, the real ETL (extract,
//    transform, load into PostgreSQL), database validation and idempotency.
//    Runs only after the offline gate passed and only when the CI database
//    configuration exists. Missing configuration is reported explicitly and
//    marks the build UNSTABLE (never a silent SUCCESS); a configured run that
//    fails marks the build FAILURE.
//
// Database configuration (values never live in this file):
//   DB_HOST, DB_PORT, DB_NAME  environment variables of the Windows agent
//                              (Jenkins node properties; not secrets)
//   DB_USER, DB_PASSWORD       Jenkins credential DB_CREDENTIALS_ID
//                              ("Username with password"), bound only to the
//                              steps that connect to PostgreSQL

pipeline {
    agent { label 'windows' }

    options {
        timeout(time: 20, unit: 'MINUTES')
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
        stage('Build Information') {
            steps {
                bat '''
                echo ========================================
                echo CI BUILD INFORMATION
                echo ========================================
                echo Branch: %BRANCH_NAME%

                for /f "delims=" %%i in ('git rev-parse --short HEAD') do set CURRENT_COMMIT=%%i

                echo Commit: %CURRENT_COMMIT%
                echo ========================================
                '''
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

        stage('Ruff') {
            steps {
                bat '%VENV_PY% -m ruff check src tests --no-cache'
            }
        }

        stage('Offline Tests') {
            environment {
                // Tripwire: an accidental API request fails locally instead of
                // reaching the real external API.
                API_BASE_URL = 'http://127.0.0.1:9'
            }

            // Three disjoint selections: 11 + 43 + 38 = 92 tests, each run once.
            // catchError lets every group run and publish results; any failure
            // still marks its stage and the build as FAILURE.
            stages {
                stage('API Client') {
                    steps {
                        catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                            bat '%VENV_PY% -m pytest -m api %PYTEST_OPTS% -o junit_suite_name=api --junitxml=reports\\api.xml'
                        }
                    }
                }

                stage('Unit') {
                    steps {
                        catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                            bat '%VENV_PY% -m pytest -m "unit and not api" %PYTEST_OPTS% -o junit_suite_name=unit --junitxml=reports\\unit.xml'
                        }
                    }
                }

                stage('Offline Data Quality') {
                    steps {
                        catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                            bat '%VENV_PY% -m pytest -m "not integration and not unit" %PYTEST_OPTS% -o junit_suite_name=offline-data --junitxml=reports\\offline-data.xml'
                        }
                    }
                }
            }
        }

        stage('Real Integration / E2E') {
            stages {
                stage('Environment Validation') {
                    steps {
                        script {
                            env.OFFLINE_GATE_PASSED = currentBuild.currentResult == 'SUCCESS' ? 'true' : 'false'
                            env.E2E_READY = 'false'

                            if (env.OFFLINE_GATE_PASSED != 'true') {
                                echo 'REAL INTEGRATION / E2E NOT RUN: the offline quality gate failed.'
                                return
                            }

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
                            } catch (error) {
                                credentialFound = false
                                echo "Jenkins credential '${env.DB_CREDENTIALS_ID}' was not found or is not of type 'Username with password'."
                            }

                            if (agentSettingsMissing || !credentialFound) {
                                unstable('REAL INTEGRATION / E2E SKIPPED: the CI database configuration is incomplete (see Environment Validation log). The offline quality gate result is not affected.')
                                return
                            }

                            // Configured but unreachable is a real failure, not a skip.
                            // Read-only connection; the error message never contains
                            // connection details.
                            withDatabaseCredentials {
                                bat 'set PYTHONPATH=src&& %VENV_PY% -m database.connection'
                            }

                            env.E2E_READY = 'true'
                        }
                    }
                }

                stage('Live DummyJSON') {
                    when { expression { env.OFFLINE_GATE_PASSED == 'true' } }
                    steps {
                        catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                            bat '%VENV_PY% -m pytest -m "live_api and not e2e" %PYTEST_OPTS% -o junit_suite_name=integration-live-api --junitxml=reports\\integration-live-api.xml'
                        }
                    }
                }

                // Extract -> Transform -> Load run the real pipeline one stage
                // at a time. A failure stops the remaining stages.
                stage('Extract') {
                    when { expression { env.E2E_READY == 'true' } }
                    steps {
                        bat '%VENV_PY% src\\main.py --stage extract'
                    }
                }

                stage('Transform') {
                    when { expression { env.E2E_READY == 'true' } }
                    steps {
                        bat '%VENV_PY% src\\main.py --stage transform'
                    }
                }

                stage('Load') {
                    when { expression { env.E2E_READY == 'true' } }
                    steps {
                        script {
                            withDatabaseCredentials {
                                bat '%VENV_PY% src\\main.py --stage load'
                            }
                        }
                    }
                }

                stage('PostgreSQL Validation') {
                    when { expression { env.E2E_READY == 'true' } }
                    steps {
                        script {
                            catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                                withDatabaseCredentials {
                                    bat '%VENV_PY% -m pytest -m "database and not e2e" %PYTEST_OPTS% -o junit_suite_name=integration-database --junitxml=reports\\integration-database.xml'
                                }
                            }
                        }
                    }
                }

                stage('E2E + Idempotency') {
                    when { expression { env.E2E_READY == 'true' } }
                    steps {
                        script {
                            catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                                withDatabaseCredentials {
                                    bat '%VENV_PY% -m pytest -m e2e --run-e2e %PYTEST_OPTS% -o junit_suite_name=e2e --junitxml=reports\\e2e.xml'
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/*.xml'
        }

        success {
            echo 'Offline quality gate and real Integration / E2E passed.'
        }

        unstable {
            echo 'Build UNSTABLE: check whether Real Integration / E2E was skipped (Environment Validation) or tests were reported unstable.'
        }

        failure {
            echo 'Build failed. Check the stage logs and test results.'
        }

        cleanup {
            deleteDir()
        }
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
