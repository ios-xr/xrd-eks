# conftest.py - Pytest hooks and fixtures

"""Pytest hooks and fixtures."""

import subprocess
from pathlib import Path
from typing import Callable, Optional

import kubernetes.client
import kubernetes.config
import pytest
import taskcat
from taskcat.testing import CFNTest

import _common
import helm


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--region",
        required=True,
        help="AWS region in which to run the tests [required]",
    )
    parser.addoption(
        "--control-plane-repository", help="xrd-control-plane image repository"
    )
    parser.addoption(
        "--control-plane-tags",
        default=["latest"],
        nargs="+",
        help="Space-separated list of xrd-control-plane image tags [default: "
        "latest]",
    )
    parser.addoption(
        "--vrouter-repository", help="xrd-vrouter image repository"
    )
    parser.addoption(
        "--vrouter-tags",
        default=["latest"],
        nargs="+",
        help="Space-separated list of xrd-vrouter image tags [default: "
        "latest]",
    )
    parser.addoption(
        "--taskcat-test-name",
        default="xrd-example-overlay",
        help="Taskcat test to run to provision the required AWS resources",
    )
    parser.addoption(
        "--skip-bringup",
        action="store_true",
        help="Do not bringup the AWS resources",
    )
    parser.addoption(
        "--skip-teardown",
        action="store_true",
        help="Do not teardown the AWS resources",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    new_items = []
    for item in items:
        marks = [m.name for m in item.iter_markers()]

        # Skip any tests marked 'control_plane' or 'vrouter' if the relevant
        # repository is not specified.
        if (
            "control_plane" in marks
            and config.option.control_plane_repository is None
        ):
            item.add_marker(
                pytest.mark.skip(
                    reason="'--control-plane-repository' not provided"
                )
            )
        if "vrouter" in marks and config.option.vrouter_repository is None:
            item.add_marker(
                pytest.mark.skip(reason="'--vrouter-repository' not provided")
            )

        # Make sure any items marked 'quickstart' are run first.
        if "quickstart" in marks:
            new_items.insert(0, item)
        else:
            new_items.append(item)

    items[:] = new_items


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    # Generate the parametrized `tag` fixture.
    if "tag" in metafunc.fixturenames:
        marks = [m.name for m in metafunc.definition.iter_markers()]
        if "control_plane" in marks:
            metafunc.parametrize(
                "tag", metafunc.config.option.control_plane_tags
            )
        if "vrouter" in marks:
            metafunc.parametrize("tag", metafunc.config.option.vrouter_tags)


@pytest.fixture
def repository(request: pytest.FixtureRequest) -> str:
    """Returns the (platform-dependent) image repository."""
    marks = [m.name for m in request.node.iter_markers()]

    assert (
        "control_plane" in marks or "vrouter" in marks,
        "Nodes using the `repository` fixture must be marked `control_plane` "
        "or `vrouter`"
    )

    assert (
        not ("control_plane" in marks and "vrouter" in marks),
        "Nodes using the `repository` fixture must not be marked both "
        "`control_plane` and `vrouter`"
    )

    if "control_plane" in marks:
        repository = request.config.option.control_plane_repository

    if "vrouter" in marks:
        repository = request.config.option.vrouter_repository

    # If the test case using this fixture is not skipped, then
    # `--control-plane-repository` or `--vrouter-repository` as appropriate
    # must have been provided.
    assert repository is not None

    return repository


@pytest.fixture(scope="session")
def taskcat_config(request: pytest.FixtureRequest) -> taskcat.Config:
    """Returns taskcat configuration."""
    project_root = Path(__file__).resolve().parent.parent
    return taskcat.Config.create(
        project_root=project_root,
        project_config_path=(project_root / "test" / ".taskcat.yml"),
    )


@pytest.fixture(scope="session")
def k8s(
    request: pytest.FixtureRequest,
    taskcat_config: taskcat.Config,
) -> kubernetes.client.CoreV1Api:
    """Returns a Kubernetes client representing the EKS cluster."""
    # Run the taskcat test to provision the AWS resources.
    test: Optional[CFNTest] = None
    if not request.config.option.skip_bringup:
        test = CFNTest(
            config=taskcat_config,
            test_names=request.config.option.taskcat_test_name,
            regions=request.config.option.region,
            skip_upload=True,
            dont_wait_for_delete=False,
        )

        test.run()

    # Ensure the Kubernetes config is updated.
    subprocess.run(
        [
            "aws",
            "eks",
            "update-kubeconfig",
            "--region",
            request.config.option.region,
            "--name",
            taskcat_config.config.general.parameters["ClusterName"],
        ],
        check=True,
        capture_output=True,
    )

    kubernetes.config.load_kube_config()

    yield kubernetes.client.CoreV1Api()

    if test is not None and not request.config.option.skip_teardown:
        test.clean_up()


@pytest.fixture(scope="session")
def ensure_xrd_helm_repo_added() -> None:
    """Adds the XRd Helm repository."""
    subprocess.run(
        [
            "helm",
            "repo",
            "add",
            "--force-update",
            "xrd",
            "https://ios-xr.github.io/xrd-helm",
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def make_release(
    k8s: kubernetes.client.CoreV1Api,
) -> Callable[[str, dict, int], helm.Helm]:
    """Factory fixture to release a Helm chart.

    The Helm chart is installed as part of setup, and uninstalled as part of
    teardown.

    Note also that any existing Helm release in the default namespace is
    uninstalled as part of setup.

    The factory must only be used once per test case.

    """
    release: Optional[helm.Helm] = None
    xrd_pods: Optional[list[kubernetes.client.V1Pod]] = None

    def _make_release(
        chart_name: str, *, values: dict, num_expected_xrd_pods: int
    ) -> helm.Helm:
        # Assert this function is only called once per test case.
        nonlocal release, xrd_pods
        assert release is None and xrd_pods is None

        # Ensure any currently present Helm releases in the default namespace
        # are uninstalled.
        for existing_release in helm.list():
            existing_release.uninstall()

        # Install the chart.
        release = helm.install(chart_name, values=values)
        assert release.status == "deployed"

        # Wait for all expected XRd containers to start before yielding.
        xrd_pods = _common.get_running_xrd_pods(
            k8s, num_expected=num_expected_xrd_pods
        )

        return release

    yield _make_release

    # Uninstall, and wait for the XRd containers to terminate before
    # returning.
    if release is not None and xrd_pods is not None:
        release.uninstall()
        for xrd_pod in xrd_pods:
            _common.assert_pod_terminated(k8s, xrd_pod)
