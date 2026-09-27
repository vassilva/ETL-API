// Offline CI Quality Gate
//
// Runs lint and the 92 offline tests (no live API, no PostgreSQL, no ETL).
// This pipeline intentionally receives NO database credentials.
// External-system and ETL execution belong in a separate job (future
// Jenkinsfile.etl), not here.

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
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/*.xml'
        }

        success {
            echo 'Offline quality gate passed.'
        }

        failure {
            echo 'Offline quality gate failed. Check the stage logs and test results.'
        }

        cleanup {
            deleteDir()
        }
    }
}
