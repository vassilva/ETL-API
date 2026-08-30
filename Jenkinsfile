pipeline {
    agent { label 'windows' }

    environment {
        DB_CREDENTIALS = credentials('postgres-etl-api')

        DB_HOST = 'localhost'
        DB_PORT = '5432'
        DB_NAME = 'etl_api'
    }

    stages {

        stage('Run ETL') {
            steps {
                bat '''
                call C:\\Vicente\\QA\\Projetos\\ETL-API\\.venv\\Scripts\\activate.bat

                set DB_USER=%DB_CREDENTIALS_USR%
                set DB_PASSWORD=%DB_CREDENTIALS_PSW%

                python src\\main.py
                '''
            }
        }

        stage('Run Tests') {
            steps {
                bat '''
                call C:\\Vicente\\QA\\Projetos\\ETL-API\\.venv\\Scripts\\activate.bat

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