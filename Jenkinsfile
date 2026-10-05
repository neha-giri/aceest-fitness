pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main', url: 'https://github.com/neha-giri/aceest-fitness.git'
            }
        }
        stage('Clean Build') {
            steps {
                sh 'python3 -m venv venv'
                sh '. venv/bin/activate && pip install -r requirements.txt'
                sh '. venv/bin/activate && python -m py_compile app.py'
            }
        }
        stage('Test') {
            steps {
                sh '. venv/bin/activate && pytest -v'
            }
        }
        stage('Docker Build') {
            steps {
                sh 'docker build -t aceest-fitness:${BUILD_NUMBER} .'
            }
        }
    }
    post {
        always { cleanWs() }
    }
}
