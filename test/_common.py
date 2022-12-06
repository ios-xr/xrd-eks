# common.py - Common test utilities

"""Common test utilities."""

from typing import Optional

import kubernetes.client
import kubernetes.stream
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)


@retry(
    wait=wait_fixed(5),
    stop=stop_after_delay(120),
    retry=retry_if_exception_type(AssertionError),
)
def get_running_xrd_pods(
    k8s: kubernetes.client.CoreV1Api,
    *,
    num_expected: Optional[int] = None,
) -> list[kubernetes.client.V1Pod]:
    """Returns a list of running XRd pods.

    These pods have 'xrd' in the name label, consist of exactly one container,
    and the one container is in running state.

    If ``num_expected`` is provided, this function additionally asserts that
    the number of such XRd pods is as expected.

    """
    pods = []
    for pod in k8s.list_namespaced_pod("default").items:
        try:
            if (
                pod.metadata.labels.get("app.kubernetes.io/name").startswith(
                    "xrd"
                )
                and pod.status.container_statuses.__len__() == 1
                and pod.status.container_statuses[0].state.running is not None
            ):
                pods.append(pod)
        except AttributeError:
            pass

    if num_expected is not None:
        assert len(pods) == num_expected

    return pods


def container_exec(
    k8s: kubernetes.client.CoreV1Api,
    pod: kubernetes.client.V1Pod,
    command: str,
) -> str:
    """Execute a command in a container.

    This assumes there is exactly one container in ``pod``.  Returns stdout.

    """
    return kubernetes.stream.stream(
        k8s.connect_post_namespaced_pod_exec,
        pod.metadata.name,
        pod.metadata.namespace or "default",
        command=command,
        stdout=True,
    )


@retry(
    wait=wait_fixed(5),
    stop=stop_after_delay(120),
    retry=retry_if_exception_type(AssertionError),
)
def assert_pod_terminated(
    k8s: kubernetes.client.CoreV1Api, pod: kubernetes.client.V1Pod
) -> None:
    """Assert a pod has terminated."""
    current_pods = k8s.list_namespaced_pod(
        pod.metadata.namespace or "default"
    ).items
    for current_pod in current_pods:
        assert current_pod.metadata.uid != pod.metadata.uid


@retry(
    wait=wait_fixed(5),
    stop=stop_after_delay(120),
    retry=retry_if_exception_type(AssertionError),
)
def assert_ping_success(
    k8s: kubernetes.client.CoreV1Api, pod: kubernetes.client.V1Pod, dest: str
) -> None:
    """Assert it is possible to ping an IPv4 address from an XRd container."""
    output = container_exec(k8s, pod, ["/pkg/bin/xrenv", "ping", dest])
    assert (
        "!!!!!" in output
    ), f"Ping destination address {dest} did not succeed: {output}"


@retry(
    wait=wait_fixed(5),
    stop=stop_after_delay(120),
    retry=retry_if_exception_type(AssertionError),
)
def assert_no_process_aborts(
    k8s: kubernetes.client.CoreV1Api, pod: kubernetes.client.V1Pod
) -> None:
    """Assert ``show processes aborts`` is empty."""
    output = container_exec(
        k8s, pod, ["/pkg/bin/xrenv", "sysmgr_show", "-o", "-l", "aborts"]
    )
    assert (
        "No process aborts found" in output
    ), f"Some process(es) aborted: {output}"
