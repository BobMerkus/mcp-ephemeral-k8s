import logging

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from mcp_ephemeral_k8s.api.model import EphemeralMcpServerConfig

logger = logging.getLogger(__name__)


def create_mcp_server_job(config: EphemeralMcpServerConfig, namespace: str) -> client.V1Job:
    """
    Create a job that will run until explicitly terminated.

    Args:
        job_name: Name of the job
        namespace: Kubernetes namespace
        image: Container image to use
        args: Arguments to pass to the container
        port: Port to expose the MCP server on
        env: Environment variables to set

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
        job_name: Name of the job to delete
        namespace: Kubernetes namespace

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


__all__ = ["create_mcp_server_job", "delete_mcp_server_job", "get_mcp_server_job_status"]
