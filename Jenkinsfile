pipeline {
    agent any

    parameters {
        string(name: "aws_region")
        string(name: "eks_kubernetes_version")
        string(name: "xrd_control_plane_repository")
        string(name: "xrd_control_plane_tags")
        string(name: "xrd_vrouter_repository")
        string(name: "xrd_vrouter_tags")
    }

    stages {
        stage("Publish CF templates and Helm charts") {
            steps {
                sh "./publish-s3-bucket"
            }
        }

        stage("Run tests") {
            steps {
                sh "nox -f test/noxfile.py --                                  \
                        --aws-region ${params.aws_region}                      \
                        --eks-kubernetes-version ${params.eks_kubernetes_version} \
                        --xrd-control-plane-repository ${params.xrd_control_plane_repository} \
                        --xrd-control-plane-tags ${params.xrd_control_plane_tags} \
                        --xrd-vrouter-repository ${params.xrd_vrouter_repository} \
                        --xrd-vrouter-tags ${params.xrd_vrouter_tags}          \
                        --log-file all.log                                     \
                        --log-file-level debug                                 \
                        --junitxml results.xml"
            }
        }
    }

    post {
        always {
            archiveArtifacts "test/all.log"
            sh "rm -f test/all.log"
            junit "test/results.xml"
            sh "rm -f test/results.xml"
        }
    }
}
