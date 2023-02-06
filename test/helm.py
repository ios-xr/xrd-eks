# -----------------------------------------------------------------------------
# helm.py - wrapper for Helm commands
#
# January 2023, Tom Johnes
#
# Copyright (c) 2023 by Cisco Systems, Inc.
# All rights reserved.
# -----------------------------------------------------------------------------

__all__ = (
    "Helm",
    "Release",
)

import dataclasses
import functools
import inspect
import json
from pathlib import Path
from typing import Optional, Union

from . import utils


@dataclasses.dataclass
class Release:
    """
    Represents a Helm release.

    .. attribute:: name
       Release name.

    .. attribute:: chart
       The associated Helm chart.

    """

    name: str
    chart: str


class Helm:
    """
    Encapsulates the Helm CLI.

    Example usage::

        >>> helm = Helm(kubeconfig=(Path.home() / ".kube" / "config"))
        >>> # equivalent to `helm install --kubeconfig=~/.kube/config ...`
        >>> release = helm.install(...)
        >>> helm.uninstall(release)

    .. attribute:: kubeconfig
        Path to a kubeconfig file to use.  This is passed as a global flag to
        all Helm subcommands.

    .. attribute:: namespace
        Kubernetes namespace.  This is passed as a global flag to all Helm
        subcommands.

    """

    def __init__(
        self,
        *,
        kubeconfig: Optional[Path] = None,
        namespace: Optional[str] = None,
    ) -> "Helm":
        self.kubeconfig = kubeconfig
        self.namespace = namespace

    def subcommand(*, name: Union[str, list[str]]):
        """
        Decorator to define a Helm subcommand.

        The wrapped function acts like a pytest fixture or a context manager -
        it must either return a list of arguments to pass to the subcommand; or
        return a generator which yields this list, in which case a
        `subprocess.CompletedProcess` is then sent to the generator for
        postprocessing.  For example::

            >>> @subcommand(name="foo")
            ... def foo(helm: Helm) -> str:
            ...     # `p` is the completed process `helm foo --bar baz`.
            ...     p = yield ["foo", "--bar", "baz"]
            ...     return p.stdout

        :param name:
            Name of the subcommand.  For nested subcommands, this is a list of
            strings, e.g. ``name=["foo", "bar"]`` corresponds to the subcommand
            ``helm foo bar``.

        """

        def decorator(func):
            @functools.wraps(func)
            def wrapper(parent: "Helm", *args, **kwargs):
                if not isinstance(name, list):
                    helm_args = [name]
                else:
                    helm_args = name

                if kubeconfig := kwargs.get("kubeconfig", parent.kubeconfig):
                    helm_args.extend(["--kubeconfig", str(kubeconfig)])

                if namespace := kwargs.get("namespace", parent.namespace):
                    helm_args.extend(["--namespace", namespace])

                is_generator_func = inspect.isgeneratorfunction(func)

                if is_generator_func:
                    generator = func(parent, *args, **kwargs)
                    helm_args.extend(next(generator))
                else:
                    helm_args.extend(func(parent, *args, **kwargs))

                p = utils.run_cmd(["helm", *helm_args], log_output=True)

                if is_generator_func:
                    try:
                        generator.send(p)
                    except StopIteration as exc:
                        return exc.value
                    else:
                        raise AssertionError(
                            "subcommand must yield exactly once"
                        )

            return wrapper

        return decorator

    @subcommand(name="install")
    def install(
        self,
        chart: str,
        *,
        name: Optional[str] = None,
        dependency_update: bool = False,
        devel: bool = False,
        dry_run: bool = False,
        values: Union[str, list[str], dict[str, str], None] = None,
        wait: bool = False,
        **kwargs,
    ) -> Release:
        """
        Install a Helm chart.

        :param values:
            Either i. one or more paths to ``--values`` files; or ii. a
            dictionary of values to set via ``--set``.

        Other parameters are per ``helm install``.

        :returns:
            A `Release` representing the installed chart.

        """
        if name is not None:
            args = [name, chart]
        else:
            args = [chart, "--generate-name"]

        if dependency_update:
            args.append("--dependency-update")

        if devel:
            args.append("--devel")

        if dry_run:
            args.append("--dry-run")

        if isinstance(values, dict):
            args.extend(
                [
                    "--set-json",
                    ",".join(
                        [f"{k}={json.dumps(v)}" for k, v in values.items()]
                    ),
                ]
            )
        elif values is not None:
            if not isinstance(values, list):
                values = [values]
            args.extend(["--values", *values])

        if wait:
            args.append("--wait")

        args.extend(["--output", "json"])

        p = yield args
        data = json.loads(p.stdout)

        return Release(data["name"], chart)

    @subcommand(name="upgrade")
    def upgrade(
        self,
        release: Release,
        *,
        dependency_update: bool = False,
        devel: bool = False,
        dry_run: bool = False,
        reset_values: bool = False,
        reuse_values: bool = False,
        values: Union[str, list[str], dict[str, str], None] = None,
        wait: bool = False,
        **kwargs,
    ) -> None:
        """
        Upgade a Helm release.

        :param release:
            Helm release.

        :param values:
            Either i. one or more paths to ``--values`` files; or ii. a
            dictionary of values to set via ``--set``.

        Other parameters are per ``helm upgrade``.

        """
        args = [release.name, release.chart]

        if dependency_update:
            args.append("--dependency-update")

        if devel:
            args.append("--devel")

        if dry_run:
            args.append("--dry-run")

        if reset_values:
            args.append("--reset-values")

        if reuse_values:
            args.append("--reuse-values")

        if isinstance(values, dict):
            args.extend(
                [
                    "--set-json",
                    ",".join(
                        [f"{k}={json.dumps(v)}" for k, v in values.items()]
                    ),
                ]
            )
        elif values is not None:
            if not isinstance(values, list):
                values = [values]
            args.extend(["--values", *values])

        if wait:
            args.append("--wait")

        return args

    @subcommand(name="uninstall")
    def uninstall(
        self,
        release: Union[str, Release],
        *,
        dry_run: bool = False,
        wait: bool = False,
        **kwargs,
    ) -> None:
        """Install a Helm chart.  Parameters are per ``helm uninstall``."""
        if isinstance(release, str):
            args = [release]
        else:
            args = [release.name]

        if dry_run:
            args.append("--dry-run")

        if wait:
            args.append("--wait")

        return args

    @subcommand(name="list")
    def list(
        self,
        *,
        filter: Optional[str] = None,
    ) -> list[Release]:
        args = ["--output", "json"]

        if filter is not None:
            args.append("--filter", filter)

        p = yield args
        data = json.loads(p.stdout)

        return [Release(d["name"], d["chart"]) for d in data]

    @subcommand(name=["repo", "add"])
    def repo_add(self, name: str, url: str, *, force_update: bool = False):
        args = [name, url]

        if force_update:
            args.append("--force-update")

        return args
