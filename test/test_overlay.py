# test_overlay.py

"""End-to-end tests for the 'aws-overlay-example' Helm chart."""

import textwrap
from pathlib import Path
from typing import Callable, Tuple

import kubernetes.client
import pytest

from .helm import Helm
from ._types import Platform, Kubectl, Image
from . import _common, utils


pytestmark = pytest.mark.platform(Platform.XRD_VROUTER)


@pytest.mark.quickstart
def test_quickstart(image: Image, kubectl: Kubectl, helm: Helm) -> None:
    """XRd QuickStart should install the example Overlay application."""
    expected_release_name = "aws-overlay-example"

    releases = helm.list()

    assert len(releases) == 1
    release = releases[0]
    assert release.name == expected_release_name

    def ping(hostname: str, address: str) -> Callable[[], bool]:
        def predicate() -> bool:
            p = kubectl(
                "exec",
                f"{expected_release_name}-{hostname}-0",
                "--",
                "/pkg/bin/xrenv",
                "ping",
                address,
                check=False,
                log_output=True,
            )
            return p.returncode == 0 and "!!!!!" in p.stdout
        return predicate

    for address in ("10.0.2.12", "10.0.3.12"):
        if not utils.wait_until(ping("xrd1", address), interval=5, maximum=60):
            assert False, f"Could not ping {address} from 'xrd1'"
    
    for address in ("10.0.2.11", "10.0.3.11"):
        if not utils.wait_until(ping("xrd2", address), interval=5, maximum=60):
            assert False, f"Could not ping {address} from 'xrd2'"
