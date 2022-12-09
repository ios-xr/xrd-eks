# XRd on AWS EKS

This repository contains resources and samples for using XRd with AWS EKS.

These are intended to be used for two purposes:
  - As an illustrative example of what's needed to set up XRd in AWS EKS.
  - As a simple way to launch a dummy XRd deployment in AWS for
    experimentation and exploration.

The resources are  __not__ intended for use in production deployments.

This readme covers the resources in detail.
To skim over this and just launch a dummy XRd deployment with the default
configuration, the [QuickStart](QuickStart) page is has simple instructions
to follow.

## Getting Started

Sample CloudFormation templates to run XRd in EKS can be found in the
`cf-templates` folder of this repository. These have several requirements
that are outlined in the next section.

### Prerequisites

This section covers the preparatory steps required before you can instantiate
XRd via the CloudFormation templates.

The following are mandatory requirements:

 * [X] An AWS account with administrator permissions (must be able to create
   IAM roles and EKS clusters)
 * [X] An [ECR Image Repository](#ecr-repository) with XRd images loaded
 * [X] An [S3 Bucket](#s3-bucket) containing the following resources from
   this repository:
   * CloudFormation templates
   * AMI Assets
 * [X] An [AWS key pair name](#aws-key-pair-name)
 * [X] The following [Tooling](#tooling)
   * The `aws` CLI

The following are optional:

 * [X] An additional [User or Role ARN](#additional-arns) with EKS admin
       privileges, if the users other than the user creating the cluster
       require access to it.
 * [X] Additional [tooling](#tooling):
   * `helm` (recommended)
   * `kubectl` (recommended)
   * `skopeo` (recommended)
   * `docker`
   * `podman`

More details are provided for each below.

#### AWS Account

The example CloudFormation templates create a new VPC and EKS cluster to
run XRd in. This means the user running the templates must have the
appropriate permissions to create a new EKS cluster, which in this case
also means creating an IAM role for the cluster.

These permissions are known to be covered by the default `AdministratorAccess`
IAM policy, it may also be possible to restrict permissions further.

#### ECR Repository

EKS needs to pull the XRd image from a container image repository which is
accessible to AWS EC2 worker nodes.

Cisco does not currently provide an external container registry, so the
approach here involves creating a repository using AWS's
ECR (Elastic Container Registry) service.

Users will need to download XRd images from
[Cisco](https://www.cisco.com/c/en/us/support/routers/ios-xrd/series.html#~tab-downloads)
and upload them to the ECR repo.

The `publish-ecr` script is provided in this repo to create an ECR bucket
with the recommended name and upload a user-provided image to it.

#### S3 Bucket

The CloudFormation templates require an AWS S3 bucket containing:
  - The CloudFormation templates
  - The AMI assets

The CloudFormation templates are required in S3 both to open/download the
starting template, and also as the resources make use of nested stacks.

The AMI Assets are required so an AMI suitable for running XRd vRouter
can be created as part of the CloudFormation stack.

The `publish-s3-bucket` script is provided in this repo to set up an
S3 bucket, including creating it and configuring permissions if required,
and then populating it.
The script outputs values to be used in the CloudFormation templates.

The main CloudFormation template is subsequently available at a location
similar to `https://<userid>-xrd-quickstart.s3.<region>.amazonaws.com/xrd-eks/cf-templates/xrd-example-cf.yaml`.
Other templates are in the same directory.

#### AWS Key Pair name

An AWS key pair is required to access to Bastion and Worker nodes created by
the stack, and indeed is a standard AWS requirement to launch any EC2 instance.

See https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/create-key-pairs.html for more details.

#### Additional ARNs

By default only the user which creates an EKS cluster has admin privileges to
this cluster.

If required, an additional user and/or role with EKS admin rights can be
specified in the CF template to allow wider interaction with the cluster.

#### Tooling

The `publish-s3-bucket` and `publish-ecr` scripts require the `aws` CLI
tool to be installed.

The `publish-ecr` script also requires one of `skopeo`, `docker`, or `podman`
to be installed to upload images to the ECR repo.

In addition to these requirements, it can be helpful to have `helm` and
`kubectl` installed to interact with the cluster once it's up and running.

The tools must be set up correctly, including setting the AWS context.

### Launching the example XRd stack

This section covers launching the `xrd-example` stack.

The user has the choice of two applications:

* Singleton - A single XRd instance of desired platform type (vRouter or Control Plane)
* Overlay - Two XRd routers illustrating an L3VPN overlay over the AWS network.

The next section covers launching this using the AWS console. This
repository also contains a helper script (`create-stack`) to launch
and example stack using some default values, as described on the
[Quick Start](QuickStart) page.

#### AWS Console

* Navigate to 'Create Stack' within the AWS console
* Fill in the Amazon S3 URL field specifying the name of the bucket you created
  e.g. `<https://<userid>-xrd-quickstart.s3.<region>.amazonaws.com/xrd-eks/cf-templates/xrd-example.yaml>`

* Click Next
* Fill in the following parameters:
  * VPC Availability Zones - Choose any two offered AZs.
  * Additional EKS admin user ARN - (optional) to allow additional users to access the cluster.
  * Additional EKS admin role ARN - (optional) as above.
  * EKS public access endpoint - Chose 'Enabled' to allow external access to the cluster API.
  * EKS remote access CIDR - Choose an IP subnet to allow external access from (or 0.0.0.0/0 to allow access from everywhere).
  * EC2 key pair - Choose the EC2 key pair to install to the bastion and worker nodes (per above).
  * Application - Choose 'Overlay'
  * XRd image repository URL - Specify the container image repository to pull the XRd image from.
  * XRd image tag - Specify the container image tag to pull.
  * XR root user name - Specify the root user name for XRd instances.
  * XR root user password - Specify the root user password for XRd instances.
  * XRd resource S3 bucket name - from the `publish-s3-bucket` script output.
  * XRd resource S3 bucket region - as previous.
  * XRd resource S3 bucket key prefix - as previous.

* Click Next
* Click Next
* Accept:
  * I acknowledge that AWS CloudFormation might create IAM resources with custom names.
  * I acknowledge that AWS CloudFormation might require the following capability: CAPABILITY_AUTO_EXPAND

* Click Create Stack

Once the stack has completed, you can access the cluster and XRd instance
as follows:

  * `aws eks update-kubeconfig --name xrd-cluster`
  * `kubectl exec xrd-example-0 -it -- xr`
    * For lab usage only - use ssh in deployment

## List of Templates

This resource provides a number of CloudFormation templates to assist with
deploying XRd on AWS.

N.B. The CloudFormation templates here makes used of existing
[Amazon EKS Quick Start](https://aws-quickstart.github.io/quickstart-amazon-eks/)
templates, which create more underlying infrastructure than strictly necessary
for an XRd deployment. These are provided as a purely illustrative example,
and are __not__ expected to be used in a production deployment.

There are three types of template:

* *Atomic Building Block* - elements used to build a full deployment stack.
* *Composite Building Block* - convenient combinations of the atomic building block templates.
* *Application* - example XRd deployments.

The Application templates are illustrative and useful to explore and experiment
but are not expected to meet the needs for actual deployments.
At some point a user will need to create their own application stack, likely
reusing the building blocks (including composites) directly.
Use of the SDK may be helpful at this point as it adds the power of programming
expression, as opposed to being limited to a static template.

**Atomic building blocks:**

* `xrd-vpc` - Create VPC suitable for running XRd.
  * Augments `aws-vpc` with additional subnets to build network topologies with.
  * These subnets are tagged so that topologies can be built referring to the tag rather than the SubnetId which varies every time a new VPC is created.
* `xrd-eks-existing-vpc` - Create EKS control plane suitable for running XRd using an existing VPC.
  * Augments `amazon-eks-entrypoint-existing-vpc` with XRd K8S settings and installs Multus.
  * Includes provisioning a Bastion for access to worker nodes
* `xrd-eks-ami` - Creates an AMI for the EKS worker node which is able to run XRd vRouter.
  * Builds and installs a patched version of the `igb_uio` driver to add `write-combine` supported which in turn is needed to achieve high volume and low latency on AWS ENA interfaces.
  * Installs a `tuned` profile to isolate cores and prevent interrupts from running on data processing cores etc.
* `xrd-eks-node-launch-template` - Create a node launch template suitable for running XRd.
* `xrd-ec2-network-interface`
  * Create a network interface on a subnet and attach it to an EC2 instance.
  * The subnet is identified by tag rather than SubnetId.   The tag is constant across VPCs, whereas the SubnetId varies.

**Composite building blocks:**

* `xrd-eks-new-vpc`
  * Create EKS control plane and VPC.  Composite of `xrd-vpc` and `xrd-eks-existing-vpc`.

* `xrd-eks-node` - Create an EKS worker node suitable for hosting an XRd instance.
  * Brings together `xrd-eks-node-launch-template` and `xrd-ec2-network-interface` to create a worker node with interfaces attached to the desired subnets.
  * The EC2 instance is labelled to provide a target for the associated XRd instance.

**Applications:**

* `xrd-overlay-example-existing-eks`
  * Two routers connected via an overlay constructed using GRE, IS-IS and L3VPN.
  * Each router is connected to a simple container workload emulating a NF in an isolated VRF.
* `xrd-singleton-existing-eks`
  * Single XRd instance of desired platform type.
  * This template can also be a useful building block.
* `xrd-example`
  * Creates a complete stack, including a parameter to choose either 'overlay' or 'singleton'
