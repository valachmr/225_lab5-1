pipeline {
    agent any 

    environment {
        DOCKER_CREDENTIALS_ID = 'roseaw-dockerhub'  
        DOCKER_IMAGE = 'cithit/valachmr'
        IMAGE_TAG = "build-${BUILD_NUMBER}"
        GITHUB_URL = 'https://github.com/valachmr/225-lab3-9.git'
        KUBECONFIG = credentials('valachmr-225-sp26')                        
    }

    stages {
        stage('Checkout') {
            steps {
                cleanWs()
                checkout([$class: 'GitSCM', branches: [[name: '*/main']],
                          userRemoteConfigs: [[url: "${GITHUB_URL}"]]])
            }
        }

        stage('Security Scan - Bandit') {
            steps {
                sh '''
                    python3 -m pip install bandit
                    python3 -m bandit -r broadcaster.py -f txt -o bandit-report.txt || true
                    cat bandit-report.txt
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'bandit-report.txt', fingerprint: true
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    docker.withRegistry('https://registry-1.docker.io', 'roseaw-dockerhub') {
                        docker.build("${DOCKER_IMAGE}:${IMAGE_TAG}")
                    }
                }
            }
        }

        stage('Push Docker Image') {
            steps {
                script {
                    docker.withRegistry('https://index.docker.io/v1/', "${DOCKER_CREDENTIALS_ID}") {
                        docker.image("${DOCKER_IMAGE}:${IMAGE_TAG}").push()
                    }
                }
            }
        }

        stage('Deploy to Dev Environment') {
            steps {
                withCredentials([file(credentialsId: 'valachmr-225-sp26', variable: 'KUBECONFIG_FILE')]) {
                    sh "sed -i 's|${DOCKER_IMAGE}:latest|${DOCKER_IMAGE}:${IMAGE_TAG}|' deployment-dev.yaml"
                    sh 'kubectl apply --kubeconfig=$KUBECONFIG_FILE -f deployment-dev.yaml'
                }
            }
        }

        stage('Check Kubernetes Cluster') {
            steps {
                withCredentials([file(credentialsId: 'valachmr-225-sp26', variable: 'KUBECONFIG_FILE')]) {
                    sh 'kubectl get all --kubeconfig=$KUBECONFIG_FILE'
                }
            }
        }
    }

    post {
        success {
            slackSend color: "good", message: "Build Completed: ${env.JOB_NAME} ${env.BUILD_NUMBER}"
        }
        unstable {
            slackSend color: "warning", message: "Build Completed: ${env.JOB_NAME} ${env.BUILD_NUMBER}"
        }
        failure {
            slackSend color: "danger", message: "Build Completed: ${env.JOB_NAME} ${env.BUILD_NUMBER}"
        }
    }
}
