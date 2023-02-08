# _types.py

__all__ = (
    "Image",
    "Kubectl",
    "KubernetesVersion",
    "Platform",
)

import dataclasses
import enum
import subprocess
from typing import Callable


class KubernetesVersion(str, enum.Enum):
    V1_22 = "1.22"
    V1_23 = "1.23"
    V1_24 = "1.24"

    def __str__(self):
        return self.value


class Platform(str, enum.Enum):
    XRD_CONTROL_PLANE = "xrd-control-plane"
    XRD_VROUTER = "xrd-vrouter"


@dataclasses.dataclass
class Image:
    platform: Platform
    repository: str
    tag: str


Kubectl = Callable[..., subprocess.CompletedProcess[str]]
