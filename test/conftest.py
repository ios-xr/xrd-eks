# conftest.py - Pytest hooks and fixtures

"""Pytest hooks and fixtures."""

import boto3
import subprocess
import warnings
from pathlib import Path
from typing import Optional

import pytest

from . import utils
from ._types import Image, Kubectl, KubernetesVersion, Platform
from .helm import Helm


# `taskcat._amiupdater.AMIUpdater` passes an absolute path to
# `pkg_resources.resource_filename`, which is deprecated.  Ignore this warning
# when importing taskcat modules.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=DeprecationWarning)
    import taskcat
    from taskcat.testing import CFNTest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("aws_and_eks", "AWS and EKS")
    group.addoption(
        "--aws-region",
        required=True,
        help="AWS region in which to run the tests (required)",
    )
    group.addoption(
        "--aws-skip-bringup",
        action="store_true",
        help="Do not bringup the AWS resources",
    )
    group.addoption(
        "--aws-skip-teardown",
        action="store_true",
        help="Do not teardown the AWS resources",
    )
    group.addoption(
        "--eks-kubernetes-version",
        type=KubernetesVersion,
        choices=list(KubernetesVersion),
        help="Kubernetes control plane version",
    )

    group = parser.getgroup("xrd", "XRd")
    group.addoption(
        "--xrd-control-plane-repository",
        help="XRd Control Plane image repository",
    )
    group.addoption(
        "--xrd-control-plane-tags",
        nargs="+",
        default=["latest"],
        help="Space-separated list of XRd Control Plane image tags (default: "
        "'latest')",
    )
    group.addoption(
        "--xrd-vrouter-repository", help="XRd vRouter image repository"
    )
    group.addoption(
        "--xrd-vrouter-tags",
        nargs="+",
        default=["latest"],
        help="Space-separated list of XRd vRouter image tags (default: "
        "'latest')",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    new_items = []
    for item in items:
        if mark := item.get_closest_marker("platform"):
            if (
                mark.args[0] is Platform.XRD_CONTROL_PLANE
                and config.option.xrd_control_plane_repository is None
            ):
                item.add_marker(
                    pytest.mark.skip(
                        "Test is marked for platform xrd-control-plane but "
                        "`--xrd-control-plane-repository` was not provided"
                    )
                )
            elif (
                mark.args[0] is Platform.XRD_VROUTER
                and config.option.xrd_vrouter_repository is None
            ):
                item.add_marker(
                    pytest.mark.skip(
                        "Test is marked for platform xrd-vrouter but "
                        "`--xrd-vrouter-repository` was not provided"
                    )
                )

        # Make sure any items marked 'quickstart' are run first.
        if item.get_closest_marker("quickstart"):
            new_items.insert(0, item)
        else:
            new_items.append(item)

    items[:] = new_items


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """
    Generate parametrized calls to a test function.

    This is used to generate the dynamically parametrized ``image`` fixture.
    This fixture should yield a `_types.Image` for each tag specified in
    ``--xrd-control-plane-tags`` and ``--xrd-vrouter-tags`` respectively.  If
    the test is marked for a specific platform, then yield images for that
    particular platform only as appropriate.

    See https://docs.pytest.org/en/latest/how-to/parametrize.html#pytest-generate-tests
    for more details on this approach to parametrized fixtures.

    """
    if "image" in metafunc.fixturenames:
        images = []
        ids = []

        if mark := metafunc.definition.get_closest_marker("platform"):
            platforms = mark.args
        else:
            platforms = (Platform.XRD_CONTROL_PLANE, Platform.XRD_VROUTER)

        if (
            Platform.XRD_CONTROL_PLANE in platforms
            and metafunc.config.option.xrd_control_plane_repository
        ):
            for tag in metafunc.config.option.xrd_control_plane_tags:
                images.append(
                    Image(
                        Platform.XRD_CONTROL_PLANE,
                        metafunc.config.option.xrd_control_plane_repository,
                        tag,
                    ),
                )
                ids.append(f"{Platform.XRD_CONTROL_PLANE}:{tag}")

        if (
            Platform.XRD_VROUTER in platforms
            and metafunc.config.option.xrd_vrouter_repository
        ):
            for tag in metafunc.config.option.xrd_vrouter_tags:
                images.append(
                    Image(
                        Platform.XRD_VROUTER,
                        metafunc.config.option.xrd_vrouter_repository,
                        tag,
                    ),
                )
                ids.append(f"{Platform.XRD_VROUTER}:{tag}")

        if images:
            metafunc.parametrize(
                "image",
                argvalues=images,
                ids=ids,
            )


@pytest.fixture(scope="session")
def taskcat_config(request: pytest.FixtureRequest) -> taskcat.Config:
    """Returns taskcat configuration."""
    project_root = Path(__file__).resolve().parent.parent
    return taskcat.Config.create(
        project_root=project_root,
        project_config_path=(project_root / "test" / ".taskcat.yml"),
    )


@pytest.fixture(scope="session")
def stack(
    request: pytest.FixtureRequest,
    taskcat_config: taskcat.Config,
) -> None:
    """Bringup and teardown the XRd Overlay stack."""
    # Run the taskcat test to provision the AWS resources.
    test: Optional[CFNTest] = None
    if not request.config.option.aws_skip_bringup:
        test = CFNTest(
            config=taskcat_config,
            test_names="xrd-example-overlay",
            regions=request.config.option.aws_region,
            skip_upload=True,
            dont_wait_for_delete=False,
        )
        # Set any Parameters given as pytest arguments.
        if version := request.config.option.eks_kubernetes_version:
            test.config.config.tests["xrd-example-overlay"].parameters[
                "KubernetesVersion"
            ] = str(version)

        test.run()

    try:
        # Ensure the Kubernetes config is updated.
        utils.run_cmd(
            [
                "aws",
                "eks",
                "update-kubeconfig",
                "--region",
                request.config.option.aws_region,
                "--name",
                taskcat_config.config.general.parameters["ClusterName"],
            ],
        )

        yield

    finally:
        if test is not None and not request.config.option.aws_skip_teardown:
            test.clean_up()

            # Delete the XRd AMI that was created.
            cf = boto3.client("cloudformation")
            version = request.config.option.eks_kubernetes_version.replace(".", "-")
            cf.delete_stack(StackName=f"xrd-quickstart-AMI-{version}")


@pytest.fixture(scope="session")
def kubectl(stack: None) -> Kubectl:
    """
    Fixture which provides a function to run a ``kubectl`` command, within the
    context of the XRd cluster.

    """

    def run_kubectl(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        """
        Run a ``kubectl`` command.

        :param args:
            Arguments to pass to ``kubectl``.

        :param kwargs:
            Keyword arguments to pass to `utils.run_cmd`.

        :returns subprocess.CompletedProcess[str]:
            The completed ``kubectl`` process.

        """
        return utils.run_cmd(["kubectl", *args], **kwargs)

    return run_kubectl


@pytest.fixture(scope="session")
def helm(stack: None) -> Helm:
    """
    Fixture which provides an instance of the `Helm` wrapper, within the
    context of the XRd cluster.

    """
    helm = Helm()
    helm.repo_add(
        "xrd", "https://ios-xr.github.io/xrd-helm", force_update=True
    )
    return helm
