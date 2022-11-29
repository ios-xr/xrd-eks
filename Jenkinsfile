pipeline {
    agent any

    parameters {
        string(name: "region")
        string(name: "control_plane_repository")
        string(name: "control_plane_tags")
        string(name: "vrouter_repository")
        string(name: "vrouter_tags")
    }

    stages {
        stage("Publish CF templates and Helm charts") {
            steps {
                sh "./publish-s3-bucket"
            }
        }

        stage("Run tests") {
            steps {
                sh "nox -f test/noxfile.py --                                \
                        --region ${params.region}                            \
                        --control-plane-repository ${params.control_plane_repository} \
                        --control-plane-tags ${params.control_plane_tags}    \
                        --vrouter-repository ${params.vrouter_repository}    \
                        --vrouter-tags ${params.vrouter_tags}                \
                        --junitxml results.xml"
            }
        }
    }

    post {
        always {
            junit "test/results.xml"
            sh "rm -f test/results.xml"
        }
    }
}
