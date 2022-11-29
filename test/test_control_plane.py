# test_control_plane.py

"""End-to-end tests for the 'xrd-control-plane' singleton chart in AWS."""

import textwrap
from typing import Callable

import kubernetes.client
import pytest

import _common
import helm


pytestmark = pytest.mark.control_plane


def _get_pod(k8s: kubernetes.client.CoreV1Api) -> kubernetes.client.V1Pod:
    """Returns the single XRd pod defined by the Helm chart."""
    pods = _common.get_running_xrd_pods(k8s, num_expected=1)
    return pods[0]


@pytest.fixture
def release(
    ensure_xrd_helm_repo_added,
    make_release: Callable[[str, dict, int], helm.Helm],
    repository: str,
    tag: str,
) -> helm.Helm:
    """Helm chart installed and uninstalled in each test case.

    This is parametrized by ``--control-plane-repository`` and
    ``--control-plane-tags``.

    """
    return make_release(
        "xrd/xrd-control-plane",
        values={
            "image": {
                "repository": repository,
                "tag": tag,
            },
        },
        num_expected_xrd_pods=1,
    )


def test_chart(k8s: kubernetes.client.CoreV1Api, release: helm.Helm) -> None:
    """Install, upgrade, and uninstall the Helm chart."""
    # The chart is installed as part of setup.  Check that it is brought up
    # successfully.
    xrd = _get_pod(k8s)
    _common.assert_no_process_aborts(k8s, xrd)

    # Upgrade.  Add an interface and some configuration.
    release.upgrade(
        values={
            "config": {
                "ascii": textwrap.dedent(
                    """
                    hostname xrd
                    interface GigabitEthernet0/0/0/0
                     ipv4 address 100.0.1.11 255.255.255.0
                    !

                    """
                ),
            },
            "interfaces": [
                {
                    "type": "defaultCni",
                    "xrName": "Gi0/0/0/0",
                },
            ],
        },
    )

    _common.assert_pod_terminated(k8s, xrd)
    xrd = _get_pod(k8s)
    _common.assert_ping_success(k8s, xrd, "100.0.1.11")
    _common.assert_no_process_aborts(k8s, xrd)
