# Development

This page is __not__ intended for long-term XRd deployments (which shouldn't
use the CloudFormation samples anyway), it is aimed at XRd developers and
testers wanting flexible deployments in AWS.

Before continuing, make sure you've read the [README](REAMDE.md).

The general recommendation for development is to use AWS's
[taskcat](https://github.com/aws-ia/taskcat) tool.

## Taskcat

To use taskcat you first need to do some initial setup:
  - Take `.user_taskcat.yml` and either copy it to `~/.taskcat.yml` or
    integrate it with your existing one as appropriate. Then fill in the
    missing fields. This file contains general settings.
  - Fill in the missing fields in `.taskcat.yml` in the repository.
    This file defines all the taskcat deployments and has some
    deployment-specific configuration.

After that you can use the `tc` script in the repository to wrap some
simple taskcat commands to bring up and tear down tests.

## Recommended workflow

The recommended flow for development is as follows:
  1. Set up taskcat as above.
  2. Publish everything to an S3 bucket using `./publish-s3-bucket`.
  3. Publish the ECR image if necessary using `./publish-ecr`.
  4. Start the overlay example deployment by running `./create-stack`.
  5. Create additional worker nodes and deployments in the cluster by
     updating the taskcat settings with the details from the example
     deployment created by `./create-stack` and deploying/deleting extra
     taskcat stacks as appropriate. The most helpful definitions are
     probably:
     - `xrd-singleton-control-plane` and `xrd-singleton-vrouter` to
       launch simple worker nodes with each XRd platform
     - `xrd-singleton-vrouter-14interfaces` to launch a 24xlarge instance
       with 14 interfaces for XRd vRouter scale testing
    A sample command to do this is: `./tc deploy xrd-singleton-vrouter`.
  6. When development is paused, stop - but don't terminate - the worker nodes.
     This is the major AWS cost for the deployment so stopping them can
     reduce this substantially (especially if using expensive EC2 instance
     types such as m5.24xlarge). When development starts again simply
     start the nodes again and the cluster shoudl recover.
     Obviously for longer-term stoppages the whole cluster should be torn
     down.
