# test_control_plane.py

"""End-to-end tests for the 'xrd-control-plane' singleton chart in AWS."""

import datetime
import textwrap

import pytest

from . import utils
from ._types import Image, Kubectl, Platform
from .helm import Helm


@pytest.fixture(autouse=True)
def teardown_topology(helm: Helm) -> None:
    for release in helm.list():
        helm.uninstall(release, wait=True)
    yield
    for release in helm.list():
        helm.uninstall(release, wait=True)


class TestBasic:
    def test_install(self, image: Image, kubectl: Kubectl, helm: Helm) -> None:
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

    def test_upgrade(self, image: Image, kubectl: Kubectl, helm: Helm) -> None:
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

        if not utils.wait_until(
            lambda: (
                "foo"
                in kubectl(
                    "exec",
                    f"xrd-{image.platform}-0",
                    "--",
                    "/bin/hostname",
                    check=False,
                    log_output=True,
                ).stdout,
            ),
            interval=5,
            maximum=30,
        ):
            assert False, f"Hostname not updated"

    def test_persistence(
        self,
        image: Image,
        kubectl: Kubectl,
        helm: Helm,
    ) -> None:
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


class TestInterfaces:
    @pytest.mark.platform(Platform.XRD_CONTROL_PLANE)
    def test_default_cni(
        self, image: Image, kubectl: Kubectl, helm: Helm
    ) -> None:
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
            lambda: (
                "!!!!!"
                in kubectl(
                    "exec",
                    f"xrd-{image.platform}-0",
                    "--",
                    "/pkg/bin/xrenv",
                    "ping",
                    address,
                    check=False,
                    log_output=True,
                ).stdout,
            ),
            interval=5,
            maximum=60,
        ):
            assert False, f"Could not ping {address}"

    @pytest.mark.platform(Platform.XRD_VROUTER)
    def test_pci_last(self, image: Image, kubectl: Kubectl, helm: Helm):
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
            lambda: (
                "!!!!!"
                in kubectl(
                    "exec",
                    f"xrd-{image.platform}-0",
                    "--",
                    "/pkg/bin/xrenv",
                    "ping",
                    address,
                    check=False,
                    log_output=True,
                ).stdout,
            ),
            interval=5,
            maximum=60,
        ):
            assert False, f"Could not ping {address}"
