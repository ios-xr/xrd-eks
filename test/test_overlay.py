# test_overlay.py

"""End-to-end tests for the 'aws-overlay-example' Helm chart."""

import textwrap
from pathlib import Path
from typing import Callable, Tuple

import kubernetes.client
import pytest

import _common
import helm


pytestmark = pytest.mark.vrouter


def _get_pods(
    k8s: kubernetes.client.CoreV1Api,
) -> Tuple[kubernetes.client.V1Pod, kubernetes.client.V1Pod]:
    """Returns the pair of XRd pods defined in the Helm chart."""
    pods = _common.get_running_xrd_pods(k8s, num_expected=2)
    return tuple(sorted(pods, key=lambda pod: pod.metadata.name))


@pytest.mark.quickstart
def test_quickstart(k8s: kubernetes.client.CoreV1Api):
    """Quick Start should install the Helm chart."""
    releases = helm.list()

    assert len(releases) == 1
    release = releases[0]
    assert release.name == "xrd-example"

    xrd1, xrd2 = _get_pods(k8s)

    _common.assert_ping_success(k8s, xrd1, "10.0.2.12")
    _common.assert_ping_success(k8s, xrd1, "10.0.3.12")

    _common.assert_ping_success(k8s, xrd2, "10.0.2.11")
    _common.assert_ping_success(k8s, xrd2, "10.0.3.11")

    _common.assert_no_process_aborts(k8s, xrd1)
    _common.assert_no_process_aborts(k8s, xrd2)


@pytest.fixture
def release(
    make_release: Callable[[str, dict, int], helm.Helm],
    repository: str,
    tag: str,
) -> helm.Helm:
    """Helm chart installed and uninstalled in each test case."""
    return make_release(
        Path(__file__).resolve().parent.parent
        / "charts"
        / "aws-overlay-example",
        values={
            "xrd1": {
                "image": {
                    "repository": repository,
                    "tag": tag,
                },
            },
            "xrd2": {
                "image": {
                    "repository": repository,
                    "tag": tag,
                },
            },
        },
        num_expected_xrd_pods=2,
    )


def test_chart(k8s: kubernetes.client.CoreV1Api, release: helm.Helm) -> None:
    """Install, upgrade, and uninstall the Helm chart."""
    # The chart is installed as part of setup.  Check that it is brought up
    # successfully.
    xrd1, xrd2 = _get_pods(k8s)

    _common.assert_ping_success(k8s, xrd1, "10.0.2.12")
    _common.assert_ping_success(k8s, xrd1, "10.0.3.12")

    _common.assert_ping_success(k8s, xrd2, "10.0.2.11")
    _common.assert_ping_success(k8s, xrd2, "10.0.3.11")

    _common.assert_no_process_aborts(k8s, xrd1)
    _common.assert_no_process_aborts(k8s, xrd2)

    # Upgrade.  Reduce the number of dataports on both XRd containers to two,
    # and replace the configuration.
    release.upgrade(
        values={
            "xrd1": {
                "config": {
                    "ascii": textwrap.dedent(
                        """
                        hostname xrd1
                        interface HundredGigE0/0/0/0
                         ipv4 address 100.0.1.11 255.255.255.0
                        !
                        interface HundredGigE0/0/0/1
                         ipv4 address 100.0.2.11 255.255.255.0
                        !

                        """
                    ),
                },
                "interfaces": [
                    {
                        "type": "pci",
                        "config": {
                            "last": 2,
                        },
                    },
                ],
            },
            "xrd2": {
                "config": {
                    "ascii": textwrap.dedent(
                        """
                        hostname xrd2
                        interface HundredGigE0/0/0/0
                         ipv4 address 100.0.1.12 255.255.255.0
                        !
                        interface HundredGigE0/0/0/1
                         ipv4 address 100.0.2.12 255.255.255.0
                        !

                        """
                    ),
                },
                "interfaces": [
                    {
                        "type": "pci",
                        "config": {
                            "last": 2,
                        },
                    },
                ],
            },
        },
    )

    _common.assert_pod_terminated(k8s, xrd1)
    _common.assert_pod_terminated(k8s, xrd2)

    xrd1, xrd2 = _get_pods(k8s)

    _common.assert_ping_success(k8s, xrd1, "100.0.1.11")
    _common.assert_ping_success(k8s, xrd1, "100.0.2.11")

    _common.assert_ping_success(k8s, xrd2, "100.0.1.12")
    _common.assert_ping_success(k8s, xrd2, "100.0.2.12")

    _common.assert_no_process_aborts(k8s, xrd1)
    _common.assert_no_process_aborts(k8s, xrd2)
