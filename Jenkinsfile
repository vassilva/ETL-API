pipeline {
    agent { label 'windows' }

    environment {
        DB_CREDENTIALS = credentials('postgres-etl-api')
        DB_HOST = 'localhost'
        DB_PORT = '5432'
        DB_NAME = 'etl_api'
    }

    stages {
        stage('Build Information') {
            steps {
                bat '''
                echo ========================================
                echo CI BUILD INFORMATION
                echo ========================================

                for /f "delims=" %%i in ('git branch --show-current') do set CURRENT_BRANCH=%%i
                for /f "delims=" %%i in ('git rev-parse --short HEAD') do set CURRENT_COMMIT=%%i

                echo Branch: %CURRENT_BRANCH%
                echo Commit: %CURRENT_COMMIT%

                echo ========================================
                '''
            }
        }

        stage('Run ETL') {
            steps {
                bat '''
                call .venv\\Scripts\\activate.bat

                set DB_USER=%DB_CREDENTIALS_USR%
                set DB_PASSWORD=%DB_CREDENTIALS_PSW%

                python src\\main.py
                '''
            }
        }

        stage('Run Tests') {
            steps {
                bat '''
                call .venv\\Scripts\\activate.bat

                set DB_USER=%DB_CREDENTIALS_USR%
                set DB_PASSWORD=%DB_CREDENTIALS_PSW%

                pytest -v
                '''
            }
        }
    }

    post {
        success {
            echo 'ETL pipeline completed successfully.'
        }

        failure {
            echo 'ETL pipeline failed. Check the console logs.'
        }
    }
}