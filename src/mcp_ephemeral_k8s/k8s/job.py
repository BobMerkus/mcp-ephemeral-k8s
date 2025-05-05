import logging
import time

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServerConfig
from mcp_ephemeral_k8s.api.exceptions import MCPJobError, MCPJobTimeoutError, MCPPortForwardError

logger = logging.getLogger(__name__)


def create_mcp_server_job(config: EphemeralMcpServerConfig, namespace: str) -> client.V1Job:
    """
    Create a job that will run until explicitly terminated.

    Args:
        config: The configuration for the MCP server
        namespace: Kubernetes namespace

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
                                initial_delay_seconds=5,
                                period_seconds=1,
                                timeout_seconds=2,
                                success_threshold=1,
                                failure_threshold=10,
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
    core_v1: client.CoreV1Api, batch_v1: client.BatchV1Api, pod_name: str, namespace: str
) -> bool:
    """
    Delete a Kubernetes job and its associated pods.

    Args:
        core_v1: The Kubernetes core API client
        batch_v1: The Kubernetes batch API client
        pod_name: The name of the pod to delete
        namespace: The namespace of the pod

    Returns:
        True if the job was deleted successfully, False otherwise
    """
    try:
        pods = core_v1.list_namespaced_pod(namespace=namespace, label_selector=f"app={pod_name}")
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
    except ApiException as e:
        logger.info(f"Error deleting pods: {e}")
        return False
    try:
        batch_v1.delete_namespaced_job(
            name=pod_name, namespace=namespace, body=client.V1DeleteOptions(propagation_policy="Foreground")
        )
        logger.info(f"Job '{pod_name}' deleted successfully")
    except ApiException as e:
        logger.info(f"Error deleting job: {e}")
        return False
    else:
        return True


def get_mcp_server_job_status(batch_v1: client.BatchV1Api, pod_name: str, namespace: str) -> None | client.V1Job:
    """
    Get the status of a Kubernetes job.

    Args:
        batch_v1: The Kubernetes batch API client
        pod_name: The name of the pod to get the status of
        namespace: The namespace of the pod

    Returns:
        The status of the job
    """
    try:
        job = batch_v1.read_namespaced_job(name=pod_name, namespace=namespace)

        # Get status
        if job.status is not None:
            active = job.status.active if job.status.active is not None else 0
            succeeded = job.status.succeeded if job.status.succeeded is not None else 0
            failed = job.status.failed if job.status.failed is not None else 0

            logger.info(f"Job '{pod_name}' status:")
            logger.info(f"Active pods: {active}")
            logger.info(f"Succeeded pods: {succeeded}")
            logger.info(f"Failed pods: {failed}")

        # Get job creation time
        if job.metadata is not None and job.metadata.creation_timestamp is not None:
            creation_time = job.metadata.creation_timestamp
            logger.info(f"Creation time: {creation_time}")
    except ApiException as e:
        if e.status == 404:
            logger.info(f"Job '{pod_name}' not found")
        else:
            logger.info(f"Error getting job status: {e}")
        return None
    else:
        return job


def check_pod_status(core_v1: client.CoreV1Api, pod_name: str, namespace: str) -> bool:
    """
    Check the status of pods associated with a job.

    Args:
        core_v1: The Kubernetes core API client
        pod_name: Name of the job/pod
        namespace: Kubernetes namespace

    Returns:
        True if a pod is running and ready (probes successful), False if waiting for pods

    Raises:
        MCPJobError: If a pod is in Failed or Unknown state
    """
    pods = core_v1.list_namespaced_pod(namespace=namespace, label_selector=f"job-name={pod_name}")

    if not pods.items:
        logger.warning(f"No pods found for job '{pod_name}', waiting...")
        return False

    for pod in pods.items:
        if pod.status and pod.status.phase:
            if pod.status.phase in ["Failed", "Unknown"]:
                raise MCPJobError(namespace, pod_name, f"Pod is in error state: {pod.status.phase}")
            elif pod.status.phase == "Running":
                # Check if the pod is also ready (probes successful)
                is_ready = False
                if pod.status.conditions:
                    for condition in pod.status.conditions:
                        if condition.type == "Ready" and condition.status == "True":
                            is_ready = True
                            break

                if is_ready:
                    logger.info(f"Job '{pod_name}' pod is running and ready (probes successful)")
                    return True
                else:
                    logger.info(f"Job '{pod_name}' pod is running but not ready yet (waiting for probes)")

    return False


def wait_for_job_ready(
    batch_v1: client.BatchV1Api,
    core_v1: client.CoreV1Api,
    pod_name: str,
    namespace: str,
    sleep_time: float = 1,
    max_wait_time: float = 60,
) -> None:
    """
    Wait for a job's pod to be in the running state and ready (probes successful).

    Args:
        batch_v1: The Kubernetes batch API client
        core_v1: The Kubernetes core API client
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        sleep_time: Time to sleep between checks
        max_wait_time: Maximum time to wait before timing out

    Raises:
        MCPJobTimeoutError: If the job does not become ready within max_wait_time
    """
    start_time = time.time()
    while True:
        if time.time() - start_time > max_wait_time:
            raise MCPJobTimeoutError(namespace, pod_name)

        job = get_mcp_server_job_status(batch_v1, pod_name, namespace)
        if job is None:
            logger.warning(f"Job '{pod_name}' not found, waiting for pod to become ready...")
            time.sleep(sleep_time)
            continue

        if job.status is None:
            logger.warning(f"Job '{pod_name}' status is None, waiting for pod to become ready...")
            time.sleep(sleep_time)
            continue

        # Check if any pod is in running state and ready
        if check_pod_status(core_v1, pod_name, namespace):
            break

        if job.status.active == 1:
            logger.info(f"Job '{pod_name}' active")
        else:
            logger.warning(f"Job '{pod_name}' in unknown state, waiting...")

        time.sleep(sleep_time)


def wait_for_job_deletion(
    batch_v1: client.BatchV1Api, pod_name: str, namespace: str, sleep_time: float = 1, max_wait_time: float = 60
) -> None:
    """
    Wait for a job to be deleted.

    Args:
        batch_v1: The Kubernetes batch API client
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        sleep_time: Time to sleep between checks
        max_wait_time: Maximum time to wait before timing out

    Raises:
        MCPJobTimeoutError: If the job is not deleted within max_wait_time
    """
    start_time = time.time()
    while True:
        if time.time() - start_time > max_wait_time:
            raise MCPJobTimeoutError(namespace, pod_name)
        if get_mcp_server_job_status(batch_v1, pod_name, namespace) is None:
            break
        time.sleep(sleep_time)


def expose_mcp_server_port(core_v1: client.CoreV1Api, pod_name: str, namespace: str, port: int) -> None:
    """
    Expose the MCP server port to the outside world.

    Args:
        core_v1: The Kubernetes core API client
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        port: Port to expose
    """
    core_v1.create_namespaced_service(
        namespace=namespace,
        body=client.V1Service(
            metadata=client.V1ObjectMeta(name=pod_name),
            spec=client.V1ServiceSpec(
                selector={"app": pod_name},
                ports=[client.V1ServicePort(port=port)],
            ),
        ),
    )
    logger.info(f"Service '{pod_name}' created successfully")


def remove_mcp_server_port(core_v1: client.CoreV1Api, pod_name: str, namespace: str) -> None:
    """
    Remove the MCP server port from the outside world.

    Args:
        core_v1: The Kubernetes core API client
        pod_name: Name of the pod
        namespace: Kubernetes namespace
    """
    core_v1.delete_namespaced_service(name=pod_name, namespace=namespace)
    logger.info(f"Service '{pod_name}' deleted successfully")


def create_port_forward(core_v1: client.CoreV1Api, pod_name: str, namespace: str, port: int) -> object:
    """
    Create a port forward to the MCP server.

    Args:
        core_v1: The Kubernetes core API client
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        port: Port to forward

    Returns:
        The portforward object that can be used to close the connection
    """
    from kubernetes.stream import portforward

    try:
        pf = portforward(
            core_v1.connect_get_namespaced_pod_portforward, pod_name, namespace, ports=str(port), async_req=True
        )
        logger.info(f"Port forward for pod '{pod_name}' created successfully")
    except Exception as e:
        logger.exception("Error creating port forward")
        raise MCPPortForwardError(pod_name, namespace, port) from e
    else:
        return pf


def delete_port_forward(core_v1: client.CoreV1Api, pod_name: str, namespace: str) -> None:
    """
    Delete the port forward to the MCP server.

    Args:
        core_v1: The Kubernetes core API client
        pod_name: Name of the pod
        namespace: Kubernetes namespace
    """
    try:
        # The port forward is deleted when the portforward object goes out of scope
        # This function is mainly for logging and future extensibility
        logger.info(f"Port forward for pod '{pod_name}' deleted")
    except Exception as e:
        logger.exception("Error deleting port forward")
        raise MCPPortForwardError(pod_name, namespace, 0) from e


__all__ = [
    "check_pod_status",
    "create_mcp_server_job",
    "create_port_forward",
    "delete_mcp_server_job",
    "delete_port_forward",
    "expose_mcp_server_port",
    "get_mcp_server_job_status",
    "remove_mcp_server_port",
    "wait_for_job_deletion",
    "wait_for_job_ready",
]
