import asyncio
import logging
import time
from typing import Any, cast

from fastmcp import Client, FastMCP
from fastmcp.client.transports import SSETransport
from kubernetes import client
from kubernetes.client.exceptions import ApiException

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServerConfig
from mcp_ephemeral_k8s.api.exceptions import MCPJobError, MCPJobTimeoutError

logger = logging.getLogger(__name__)


def create_mcp_server_job(
    config: EphemeralMcpServerConfig, namespace: str, service_account_name: str | None = None
) -> client.V1Job:
    """
    Create a job that will run until explicitly terminated.

    Args:
        config: The configuration for the MCP server
        namespace: Kubernetes namespace
        service_account_name: Optional ServiceAccount name to use for the pod

    Returns:
        The MCP server instance
    """
    # Convert environment variables dictionary to list of V1EnvVar
    env_list = [client.V1EnvVar(name=key, value=value) for key, value in (config.env or {}).items()]

    # Configure the job
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=config.job_name, namespace=namespace),
        spec=client.V1JobSpec(
            backoff_limit=10,
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": config.job_name}),
                spec=client.V1PodSpec(
                    service_account_name=service_account_name,
                    containers=[
                        client.V1Container(
                            name=config.job_name,
                            image=config.image,
                            command=config.entrypoint,
                            image_pull_policy="IfNotPresent",
                            args=config.args,
                            resources=client.V1ResourceRequirements(
                                requests=config.resource_requests, limits=config.resource_limits
                            ),
                            ports=[client.V1ContainerPort(container_port=config.port)],
                            env=env_list,
                            readiness_probe=client.V1Probe(
                                tcp_socket=client.V1TCPSocketAction(port=config.port),
                                **config.probe_config.model_dump(),
                            ),
                        )
                    ],
                    restart_policy="Never",
                ),
            ),
        ),
    )

    return job


def delete_mcp_server_job(
    core_v1: client.CoreV1Api, batch_v1: client.BatchV1Api, job_name: str, namespace: str
) -> bool:
    """
    Delete a Kubernetes job and its associated pods.

    Args:
        core_v1: The Kubernetes core API client
        batch_v1: The Kubernetes batch API client
        job_name: The name of the pod to delete
        namespace: The namespace of the pod

    Returns:
        True if the job was deleted successfully, False otherwise
    """
    try:
        pods = core_v1.list_namespaced_pod(namespace=namespace, label_selector=f"app={job_name}")
        for pod in pods.items:
            if pod.metadata is None:
                continue
            pod_name_to_delete = pod.metadata.name
            if pod_name_to_delete is None:
                continue
            logger.info(f"Deleting pod {pod_name_to_delete}")
            core_v1.delete_namespaced_pod(
                name=pod_name_to_delete,
                namespace=namespace,
                body=client.V1DeleteOptions(grace_period_seconds=0, propagation_policy="Background"),
            )
    except ApiException:
        logger.exception("Error deleting pods")
        return False
    try:
        batch_v1.delete_namespaced_job(
            name=job_name, namespace=namespace, body=client.V1DeleteOptions(propagation_policy="Foreground")
        )
        logger.info(f"Job '{job_name}' deleted successfully")
    except ApiException:
        logger.exception("Error deleting job")
        return False
    else:
        return True


def get_mcp_server_job_status(batch_v1: client.BatchV1Api, job_name: str, namespace: str) -> None | client.V1Job:
    """
    Get the status of a Kubernetes job.

    Args:
        batch_v1: The Kubernetes batch API client
        job_name: The name of the pod to get the status of
        namespace: The namespace of the pod

    Returns:
        The status of the job
    """
    try:
        job = cast(client.V1Job, batch_v1.read_namespaced_job(name=job_name, namespace=namespace))

        # Get status
        if job.status is not None:
            active = job.status.active if job.status.active is not None else 0
            succeeded = job.status.succeeded if job.status.succeeded is not None else 0
            failed = job.status.failed if job.status.failed is not None else 0

            logger.info(f"Job '{job_name}' status:")
            logger.info(f"Active pods: {active}")
            logger.info(f"Succeeded pods: {succeeded}")
            logger.info(f"Failed pods: {failed}")

        # Get job creation time
        if job.metadata is not None and job.metadata.creation_timestamp is not None:
            creation_time = job.metadata.creation_timestamp
            logger.info(f"Creation time: {creation_time}")
    except ApiException as e:
        if e.status == 404:
            logger.info(f"Job '{job_name}' not found")
        else:
            logger.info(f"Error getting job status: {e}")
        return None
    else:
        return job


def _is_pod_ready(pod: client.V1Pod) -> bool:
    """Check if a pod is ready based on its conditions.

    Args:
        pod: The Kubernetes pod object

    Returns:
        True if pod is running and all probes are successful
    """
    if not pod.status or not pod.status.conditions:
        return False

    return any(condition.type == "Ready" and condition.status == "True" for condition in pod.status.conditions)


def _handle_failed_pod(core_v1: client.CoreV1Api, pod: client.V1Pod, namespace: str, job_name: str) -> None:
    """Handle a pod in failed or unknown state.

    Args:
        core_v1: The Kubernetes core API client
        pod: The failed pod
        namespace: Kubernetes namespace
        job_name: Name of the job

    Raises:
        MCPJobError: Always raises with pod failure details
    """
    phase = pod.status.phase if pod.status else "Unknown"
    if pod.metadata is not None and pod.metadata.name is not None:
        try:
            logs = core_v1.read_namespaced_pod_log(name=pod.metadata.name, namespace=namespace)
            logger.error(f"Pod {pod.metadata.name} in error state: {phase}")
            logger.error(f"Logs: {logs}")
            message = f"Pod is in error state: {phase}. Logs: {logs}"
        except Exception:
            logger.exception("Failed to retrieve pod logs")
            message = f"Pod is in error state: {phase}"
    else:
        message = f"Pod is in error state: {phase}"
    raise MCPJobError(namespace, job_name, message)


def check_pod_status(core_v1: client.CoreV1Api, job_name: str, namespace: str) -> bool:
    """
    Check the status of pods associated with a job.

    Args:
        core_v1: The Kubernetes core API client
        job_name: Name of the job/pod
        namespace: Kubernetes namespace

    Returns:
        True if a pod is running and ready (probes successful), False if waiting for pods

    Raises:
        MCPJobError: If a pod is in Failed or Unknown state
    """
    pods = core_v1.list_namespaced_pod(namespace=namespace, label_selector=f"job-name={job_name}")
    if not pods.items:
        logger.warning(f"No pods found for job '{job_name}', waiting...")
        return False

    for pod in pods.items:
        if not pod.status or not pod.status.phase:
            continue

        # Handle error states
        if pod.status.phase in ["Failed", "Unknown"]:
            _handle_failed_pod(core_v1, pod, namespace, job_name)

        # Handle running pods
        if pod.status.phase == "Running":
            if _is_pod_ready(pod):
                logger.info(f"Job '{job_name}' pod is running and ready (probes successful)")
                return True
            else:
                logger.info(f"Job '{job_name}' pod is running but not ready yet (waiting for probes)")

    return False


async def wait_for_job_ready(
    batch_v1: client.BatchV1Api,
    core_v1: client.CoreV1Api,
    job_name: str,
    namespace: str,
    sleep_time: float = 1,
    max_wait_time: float = 60,
) -> None:
    """
    Wait for a job's pod to be in the running state and ready (probes successful).

    Args:
        batch_v1: The Kubernetes batch API client
        core_v1: The Kubernetes core API client
        job_name: Name of the pod
        namespace: Kubernetes namespace
        sleep_time: Time to sleep between checks
        max_wait_time: Maximum time to wait before timing out

    Raises:
        MCPJobTimeoutError: If the job does not become ready within max_wait_time
    """
    start_time = time.time()
    while True:
        if time.time() - start_time > max_wait_time:
            raise MCPJobTimeoutError(namespace, job_name)

        job = get_mcp_server_job_status(batch_v1, job_name, namespace)
        if job is None:
            logger.warning(f"Job '{job_name}' not found, waiting for pod to become ready...")
            await asyncio.sleep(sleep_time)
            continue

        if job.status is None:
            logger.warning(f"Job '{job_name}' status is None, waiting for pod to become ready...")
            await asyncio.sleep(sleep_time)
            continue

        # Check if any pod is in running state and ready
        if check_pod_status(core_v1, job_name, namespace):
            break

        if job.status.active == 1:
            logger.info(f"Job '{job_name}' active")
        else:
            logger.warning(f"Job '{job_name}' in unknown state, waiting...")

        await asyncio.sleep(sleep_time)


async def wait_for_job_deletion(
    batch_v1: client.BatchV1Api, job_name: str, namespace: str, sleep_time: float = 1, max_wait_time: float = 60
) -> None:
    """
    Wait for a job to be deleted.

    Args:
        batch_v1: The Kubernetes batch API client
        job_name: Name of the pod
        namespace: Kubernetes namespace
        sleep_time: Time to sleep between checks
        max_wait_time: Maximum time to wait before timing out

    Raises:
        MCPJobTimeoutError: If the job is not deleted within max_wait_time
    """
    start_time = time.time()
    while True:
        if time.time() - start_time > max_wait_time:
            raise MCPJobTimeoutError(namespace, job_name)
        if get_mcp_server_job_status(batch_v1, job_name, namespace) is None:
            break
        await asyncio.sleep(sleep_time)


def expose_mcp_server_port(core_v1: client.CoreV1Api, job_name: str, namespace: str, port: int) -> None:
    """
    Expose the MCP server port to the outside world.

    Args:
        core_v1: The Kubernetes core API client
        job_name: Name of the pod (job name)
        namespace: Kubernetes namespace
        port: Port to expose
    """
    core_v1.create_namespaced_service(
        namespace=namespace,
        body=client.V1Service(
            metadata=client.V1ObjectMeta(name=job_name),
            spec=client.V1ServiceSpec(
                selector={"job-name": job_name},
                ports=[client.V1ServicePort(port=port)],
            ),
        ),
    )
    logger.info(f"Service '{job_name}' created successfully")


def remove_mcp_server_port(core_v1: client.CoreV1Api, job_name: str, namespace: str) -> None:
    """
    Remove the MCP server port from the outside world.

    Args:
        core_v1: The Kubernetes core API client
        job_name: Name of the pod
        namespace: Kubernetes namespace
    """
    core_v1.delete_namespaced_service(name=job_name, namespace=namespace)
    logger.info(f"Service '{job_name}' deleted successfully")


def create_proxy_server(url: str, **kwargs: Any) -> FastMCP:
    """Create a proxy server from a remote MCP server over SSE.

    Args:
        url: The SSE endpoint URL of the remote MCP server
        **kwargs: Additional keyword arguments for SSETransport configuration
            - sse_read_timeout: SSE read timeout (default: 300s)
            - headers: Optional HTTP headers dict
            - auth: Optional authentication
            - httpx_client_factory: Optional custom HTTPX client factory

    Returns:
        FastMCP proxy server instance

    Example:
        >>> server = create_proxy_server(
        ...     url="http://pod.default.svc.cluster.local:8080/sse",
        ...     sse_read_timeout=600.0
        ... )
    """
    # Only pass valid SSETransport parameters
    valid_params = {"sse_read_timeout", "headers", "auth", "httpx_client_factory"}
    transport_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}

    logger.debug(f"Creating proxy server for {url} with kwargs: {transport_kwargs}")

    remote_client = Client(SSETransport(url=url, **transport_kwargs))
    return FastMCP.as_proxy(remote_client)


__all__ = [
    "check_pod_status",
    "create_mcp_server_job",
    "create_proxy_server",
    "delete_mcp_server_job",
    "expose_mcp_server_port",
    "get_mcp_server_job_status",
    "remove_mcp_server_port",
    "wait_for_job_deletion",
    "wait_for_job_ready",
]
