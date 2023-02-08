# test_overlay.py

"""End-to-end tests for the Overlay application."""


import pytest

from . import utils
from ._types import Image, Kubectl, Platform
from .helm import Helm


pytestmark = pytest.mark.platform(Platform.XRD_VROUTER)


def check_bgp_established(
    kubectl: Kubectl,
    pod_name: str,
    neighbor: str,
) -> bool:
    """
    Check whether a BGP session is established with the given neighbor.

    :param kubectl:
        Kubectl context.

    :param pod_name:
        Pod from which to check BGP connectivity.

    :param neighbor:
        IP address of the neighbor.

    :return:
        True if the connection is established.
        False otherwise.

    """
    try:
        p = kubectl(
            "exec",
            pod_name,
            "--",
            "xrenv",
            "bgp_show",
            "-V",
            "default",
            "-n",
            "-br",
            "-instance",
            "default",
        )
    except subprocess.CalledProcessError:
        return False

    # Example output:
    #
    # Neighbor        Spk    AS Description                          Up/Down  NBRState
    # 10.1.0.2          0     1                                      00:17:12 Established
    # 100.0.0.1         0     1                                      00:15:44 Established
    #
    # Grab the fifth column of the correct neighbour.
    for line in p.stdout.strip().splitlines():
        cols = line.split()
        if cols[0] == neighbor:
            if cols[4] == "Established":
                return True
            break

    return False


@pytest.mark.quickstart
def test_quickstart(image: Image, kubectl: Kubectl, helm: Helm) -> None:
    """XRd QuickStart should install the example Overlay application."""
    expected_release_name = "xrd-example"

    releases = helm.list()

    assert len(releases) == 1
    release = releases[0]
    assert release.name == expected_release_name

    if not utils.wait_until(
        5,
        60,
        check_bgp_established,
        kubectl,
        f"{expected_release_name}-xrd1-0",
        "1.0.0.12",
    ):
        assert False, f"BGP not established"

    if not utils.wait_until(
        5,
        60,
        check_bgp_established,
        kubectl,
        f"{expected_release_name}-xrd2-0",
        "1.0.0.11",
    ):
        assert False, f"BGP not established"

    for address in ("10.0.2.12", "10.0.3.12"):
        p = kubectl(
            "exec",
            f"{expected_release_name}-xrd1-0",
            "--",
            "xrenv",
            "ping",
            address,
            log_output=True,
        )
        assert "!!!!!" in p.stdout

    for address in ("10.0.2.11", "10.0.3.11"):
        p = kubectl(
            "exec",
            f"{expected_release_name}-xrd1-0",
            "--",
            "xrenv",
            "ping",
            address,
            log_output=True,
        )
        assert "!!!!!" in p.stdout
