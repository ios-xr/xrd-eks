# conftest.py - Pytest hooks and fixtures

"""Pytest hooks and fixtures."""

import subprocess
from pathlib import Path
from typing import Optional
import warnings

import pytest

from . import utils
from ._types import Image, Kubectl, Platform
from .helm import Helm

import taskcat
from taskcat.testing import CFNTest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--region",
        default="us-east-1",
        help="AWS region in which to run the tests [required]",
    )
    parser.addoption(
        "--control-plane-repository", help="xrd-control-plane image repository"
    )
    parser.addoption(
        "--control-plane-tags",
        nargs="+",
        default=[],
        help="Space-separated list of xrd-control-plane image tags",
    )
    parser.addoption(
        "--vrouter-repository", help="xrd-vrouter image repository"
    )
    parser.addoption(
        "--vrouter-tags",
        nargs="+",
        default=[],
        help="Space-separated list of xrd-vrouter image tags",
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
    # Generate the parametrized `image` fixture.
    if "image" in metafunc.fixturenames:
        images = []
        ids = []

        if mark := metafunc.definition.get_closest_marker("platform"):
            platforms = mark.args
        else:
            platforms = (Platform.XRD_CONTROL_PLANE, Platform.XRD_VROUTER)

        if Platform.XRD_CONTROL_PLANE in platforms:
            for tag in metafunc.config.option.control_plane_tags:
                images.append(
                    Image(
                        Platform.XRD_CONTROL_PLANE,
                        metafunc.config.option.control_plane_repository,
                        tag,
                    ),
                )
                ids.append(f"{Platform.XRD_CONTROL_PLANE}:{tag}")

        if Platform.XRD_VROUTER in platforms:
            for tag in metafunc.config.option.vrouter_tags:
                images.append(
                    Image(
                        Platform.XRD_VROUTER,
                        metafunc.config.option.vrouter_repository,
                        tag,
                    ),
                )
                ids.append(f"{Platform.XRD_VROUTER}:{tag}")

        metafunc.parametrize(
            "image",
            argvalues=images,
            ids=ids,
        )


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """
    Set the ``result`` attribute on a test item after it has completed the
    call phase.

    This may be used to implement run-on-failure actions in the test teardown
    phase.  For example:

    >>> @pytest.fixture
    ... def teardown(request):
    ...     yield
    ...     result = getattr(request.node, "result", None)
    ...     if result is not None and result.failed:
    ...         # Commands to run-on-failure.

    """
    outcome = yield
    result = outcome.get_result()
    if result.when == "call":
        setattr(item, "result", result)


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

    try:
        # Ensure the Kubernetes config is updated.
        utils.run_cmd(
            [
                "aws",
                "eks",
                "update-kubeconfig",
                "--region",
                request.config.option.region,
                "--name",
                taskcat_config.config.general.parameters["ClusterName"],
            ],
        )

        yield

    finally:
        if test is not None and not request.config.option.skip_teardown:
            test.clean_up()


@pytest.fixture(scope="session")
def kubectl(stack: None) -> Kubectl:
    def run_kubectl(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        return utils.run_cmd(["kubectl", *args], **kwargs)

    return run_kubectl


@pytest.fixture(scope="session")
def helm(stack: None) -> Helm:
    """"""
    helm = Helm()
    helm.repo_add(
        "xrd", "https://ios-xr.github.io/xrd-helm", force_update=True
    )
    return helm
