# test_singleton.py

"""End-to-end tests for the Singleton application."""

import datetime
import subprocess
import textwrap

import pytest

from . import utils
from ._types import Image, Kubectl, Platform
from .helm import Helm


@pytest.fixture(autouse=True)
def uninstall_releases(helm: Helm) -> None:
    """Uninstall all Helm releases before and after each test case."""
    for release in helm.list():
        helm.uninstall(release, wait=True)

    yield

    for release in helm.list():
        helm.uninstall(release, wait=True)


def test_install(image: Image, kubectl: Kubectl, helm: Helm) -> None:
    release = helm.install(
        f"xrd/{image.platform}",
        name="xrd",
        values={
            "image": {
                "repository": image.repository,
                "tag": image.tag,
            },
        },
        wait=True,
    )


def test_upgrade(image: Image, kubectl: Kubectl, helm: Helm) -> None:
    release = helm.install(
        f"xrd/{image.platform}",
        name="xrd",
        values={
            "image": {
                "repository": image.repository,
                "tag": image.tag,
            },
        },
        wait=True,
    )

    # Upgrade the chart to configure a new hostname.
    helm.upgrade(
        release,
        reuse_values=True,
        values={
            "config": {
                "ascii": "hostname foo",
            },
        },
        wait=True,
    )

    # Check the hostname is correct in the new instance - it may take a while
    # for the new config to get applied, so use a predicate.
    def check_hostname(expected_hostname: str) -> bool:
        try:
            p = kubectl(
                "exec",
                f"xrd-{image.platform}-0",
                "--",
                "hostname",
                log_output=True,
            )
        except subprocess.CalledProcessError:
            return False

        return expected_hostname in p.stdout

    if not utils.wait_until(
        5,
        60,
        check_hostname,
        "foo",
    ):
        assert False, f"Hostname not updated"


def test_persistence(
    image: Image,
    kubectl: Kubectl,
    helm: Helm,
) -> None:
    """
    Check it is possible to write to a persistent volume used by the XRd Pod,
    and that the data written persists over Pod restart.

    """
    release = helm.install(
        f"xrd/{image.platform}",
        name="xrd",
        values={
            "image": {
                "repository": image.repository,
                "tag": image.tag,
            },
            "persistence": {
                "enabled": True,
            },
        },
        wait=True,
    )

    now = str(datetime.datetime.now())
    kubectl(
        "exec",
        f"xrd-{image.platform}-0",
        "--",
        "/bin/bash",
        "-c",
        f"echo {now} > /xr-storage/out.txt",
    )

    kubectl("delete", f"pod/xrd-{image.platform}-0", "--wait")
    kubectl("wait", "--for=condition=Ready", f"pod/xrd-{image.platform}-0")
    p = kubectl(
        "exec",
        f"xrd-{image.platform}-0",
        "--",
        "/bin/bash",
        "-c",
        "cat /xr-storage/out.txt",
    )
    assert now in p.stdout


@pytest.mark.platform(Platform.XRD_CONTROL_PLANE)
def test_default_cni(image: Image, kubectl: Kubectl, helm: Helm) -> None:
    """
    Check configuration of an XR interface backed by the default CNI interface.

    """
    address = "100.0.1.11"
    release = helm.install(
        f"xrd/{image.platform}",
        name="xrd",
        values={
            "image": {
                "repository": image.repository,
                "tag": image.tag,
            },
            "config": {
                "ascii": textwrap.dedent(
                    f"""
                    hostname xrd
                    interface Gi0/0/0/0
                     ipv4 address {address} 255.255.255.0
                    !

                    """
                ).strip(),
            },
            "interfaces": [
                {
                    "type": "defaultCni",
                    "xrName": "Gi0/0/0/0",
                },
            ],
        },
        wait=True,
    )

    if not utils.wait_until(
        5, 60, utils.check_ping, kubectl, f"xrd-{image.platform}-0", address
    ):
        assert False, f"Could not ping {address}"


@pytest.mark.platform(Platform.XRD_VROUTER)
def test_pci_last(image: Image, kubectl: Kubectl, helm: Helm):
    """
    Check configuration of XR interfaces backed by PCI interfaces using the
    ``last: n`` Helm chart value.

    """
    address = "100.0.1.11"
    release = helm.install(
        f"xrd/{image.platform}",
        name="xrd",
        values={
            "image": {
                "repository": image.repository,
                "tag": image.tag,
            },
            "config": {
                "ascii": textwrap.dedent(
                    f"""
                    hostname xrd
                    interface Hu0/0/0/0
                     ipv4 address {address} 255.255.255.0
                    !

                    """
                ).strip(),
            },
            "interfaces": [
                {
                    "type": "pci",
                    "config": {
                        "last": 1,
                    },
                },
            ],
        },
        wait=True,
    )

    if not utils.wait_until(
        5, 60, utils.check_ping, kubectl, f"xrd-{image.platform}-0", address
    ):
        assert False, f"Could not ping {address}"
