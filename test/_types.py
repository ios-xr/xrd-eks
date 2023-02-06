import dataclasses
import enum
import subprocess
from typing import Callable


class Platform(str, enum.Enum):
    XRD_CONTROL_PLANE = "xrd-control-plane"
    XRD_VROUTER = "xrd-vrouter"


@dataclasses.dataclass
class Image:
    platform: Platform
    repository: str
    tag: str


Kubectl = Callable[..., subprocess.CompletedProcess[str]]
