# helm.py - Helm wrapper

"""Helm wrapper."""

import dataclasses
import json
import subprocess
import tempfile
from typing import Optional

import yaml


__all__ = ("Helm", "install", "list")


@dataclasses.dataclass
class Helm:
    name: str
    chart: Optional[str] = None

    @property
    def status(self) -> str:
        output = self._run("status", self.name, "-o", "json").stdout
        return json.loads(output)["info"]["status"]

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        command = ["helm", *args]
        return subprocess.run(command, check=True, capture_output=True)

    def uninstall(self) -> None:
        """Uninstall the chart."""
        self._run("uninstall", self.name)

    def upgrade(self, values: dict[str, str]) -> None:
        """Upgrade the chart."""
        assert self.chart is not None
        with tempfile.NamedTemporaryFile(mode="w") as f:
            yaml.dump(values, f)
            self._run(
                "upgrade",
                self.name,
                self.chart,
                "-f",
                f.name,
                "--reuse-values",
                "--devel",
            )

    def rollback(self, *, revision: int = 1) -> None:
        """Rollback to a previous revision."""
        self._run("rollback", str(revision))


def install(
    chart: str,
    *,
    name: Optional[str] = None,
    values: Optional[dict[str, str]] = None,
) -> Helm:
    """Install a chart."""
    command = [
        "helm",
        "install",
        name or "--generate-name",
        chart,
        "-o",
        "json",
        "--dependency-update",
        "--devel",
    ]

    with tempfile.NamedTemporaryFile(mode="w") as f:
        if values is not None:
            yaml.dump(values, f)
            command.extend(["-f", f.name])
        output = subprocess.check_output(command)

    result = json.loads(output)
    return Helm(result["name"], chart=chart)


def list() -> list[Helm]:
    """List installed charts."""
    output = subprocess.check_output(["helm", "list", "-o", "json"])

    releases = []
    for info in json.loads(output):
        chart, version = info["chart"].rsplit("-", maxsplit=1)
        releases.append(Helm(info["name"]))

    return releases
