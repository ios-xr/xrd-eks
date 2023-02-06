# test_control_plane.py

"""End-to-end tests for the 'xrd-control-plane' singleton chart in AWS."""

import textwrap
from typing import Callable

import pytest
import utils
from _types import Image, Kubectl
from helm import Helm


def ping(image: Image, address: str) -> Callable[[], bool]:
    def predicate() -> bool:
        p = kubectl(
            "exec",
            f"xrd-{image.platform}-0",
            "--",
            "/pkg/bin/xrenv",
            "ping",
            address,
        )
        return "!!!!!" in p.stdout

    return predicate


@pytest.fixture(autouse=True)
def teardown_topology(helm: Helm) -> None:
    for release in helm.list():
        helm.uninstall(release, wait=True)
    yield
    for release in helm.list():
        helm.uninstall(release, wait=True)


class TestQuickStart:
    pass


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
        pass

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
        kubectl(
            "exec",
            f"xrd-{image.platform}-0",
            "--",
            "/bin/bash",
            "-c",
            "echo hi > /xr-storage/out.txt",
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
        assert "hi" in p.stdout


class TestInterfaces:
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
                        interface GigabitEthernet0/0/0/0
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
            lambda: "!!!!!"
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
            interval=5,
            maximum=60,
        ):
            assert False, f"Could not ping {address}"
