pipeline {
    agent { label 'windows' }

    stages {

        stage('Run ETL') {
            steps {
                bat '''
                call C:\\Vicente\\QA\\Projetos\\ETL-API\\.venv\\Scripts\\activate.bat
                python src\\main.py
                '''
            }
        }

        stage('Run Tests') {
            steps {
                bat '''
                call C:\\Vicente\\QA\\Projetos\\ETL-API\\.venv\\Scripts\\activate.bat
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