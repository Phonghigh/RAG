pipeline {
    agent any
    
    options {
        timestamps()
    }
    
    stages {
        stage('Setup') {
            steps {
                sh 'python -m pip install -U pip setuptools wheel'
                sh 'pip install -r requirements.txt'
            }
        }
        
        stage('Lint & Type') {
            steps {
                sh 'ruff check . || true'
                sh 'mypy apps || true'
            }
        }
        
        stage('Unit Tests') {
            steps {
                sh 'pytest -q --junitxml=reports/junit.xml --cov=apps --cov-report=xml || true'
            }
            post {
                always {
                    junit 'reports/junit.xml'
                }
            }
        }
        
        stage('Build Images') {
            steps {
                script {
                    def commitHash = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                    sh "docker build -f deployments/docker/Dockerfile.api -t rca-rag/api:${commitHash} ."
                    sh "docker build -f deployments/docker/Dockerfile.worker -t rca-rag/worker:${commitHash} ."
                }
            }
        }
        
        stage('Deploy Dev') {
            when {
                branch 'main'
            }
            steps {
                sh 'docker compose -f deployments/docker-compose.dev.yml up -d --build || true'
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
    }
}

