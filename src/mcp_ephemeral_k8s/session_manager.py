"""
This module contains the session manager for the MCP ephemeral K8s library.
It is used to create and manage MCP servers in a Kubernetes cluster.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any, Self, cast

from kubernetes import client, config
from kubernetes.client.api.batch_v1_api import BatchV1Api
from kubernetes.client.api.core_v1_api import CoreV1Api
from kubernetes.client.api_client import ApiClient
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from mcp_ephemeral_k8s.exceptions import MCPJobNotFoundError, MCPServerCreationError
from mcp_ephemeral_k8s.model import ephemeralMcpServer, ephemeralMcpServerConfig

logger = logging.getLogger(__name__)


class KubernetesSessionManager(BaseModel):
    """
    Kubernetes session manager for MCP.

    This manager creates and manages Kubernetes jobs for MCP sessions.
    It implements the async context manager protocol for easy resource management.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    jobs: dict[str, ephemeralMcpServer] = Field(default_factory=dict, description="The jobs that are currently running")
    _api_client: ApiClient | None = PrivateAttr(default=None)
    _batch_v1: BatchV1Api | None = PrivateAttr(default=None)
    _core_v1: CoreV1Api | None = PrivateAttr(default=None)

    def load_session_manager(self) -> Self:
        """Load Kubernetes configuration from default location or from service account if running in cluster."""
        self._load_kube_config()
        if self._api_client is None:
            self._api_client = client.ApiClient()
        if self._batch_v1 is None:
            self._batch_v1 = client.BatchV1Api(self._api_client)
        if self._core_v1 is None:
            self._core_v1 = client.CoreV1Api(self._api_client)
        return self

    def _load_kube_config(self) -> None:
        """Load Kubernetes configuration from default location or from service account if running in cluster."""
        try:
            # Try to load from default config file
            config.load_kube_config()
            logger.info("Using local kubernetes configuration")
        except Exception:
            # If that fails, we might be running in a pod, so try to use service account
            config.load_incluster_config()
            logger.info("Using in-cluster kubernetes configuration")

    def __enter__(self) -> Self:
        """Enter the context manager."""
        self.load_session_manager()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context manager."""
        for job_name in self.jobs:
            self._delete_job(job_name, self.jobs[job_name].config.namespace)

    async def __aenter__(self) -> AsyncGenerator["KubernetesSessionManager", None]:
        """
        Create and start the MCP server when entering the context.

        Returns:
            The MCP server instance
        """
        self.load_session_manager()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Clean up resources when exiting the context.

        This deletes the Kubernetes job and associated pods.
        """
        for job_name in self.jobs:
            self._delete_job(job_name, self.jobs[job_name].config.namespace)

    def _create_job(
        self,
        config: ephemeralMcpServerConfig,
    ) -> ephemeralMcpServer | None:
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
            metadata=client.V1ObjectMeta(name=config.job_name, namespace=config.namespace),
            spec=client.V1JobSpec(
                # Setting backoffLimit to a high number to prevent the job from being marked as failed
                backoff_limit=10,
                # We don't set completions or parallelism because we want the job to run indefinitely
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={"app": config.job_name}),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name=config.job_name,
                                image=config.image,
                                args=config.args,
                                # Adding resource requests/limits for better management
                                resources=client.V1ResourceRequirements(
                                    requests=config.resource_requests, limits=config.resource_limits
                                ),
                                ports=[client.V1ContainerPort(container_port=config.port)],
                                env=env_list,
                                # Add readiness probe to wait until the TCP endpoint is ready
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
                        restart_policy="Never",  # This is required for Jobs
                    ),
                ),
            ),
        )

        # Create the job
        try:
            response = self._batch_v1.create_namespaced_job(namespace=config.namespace, body=job)
            logger.info(f"Job '{config.job_name}' created successfully")
            logger.debug(f"Job response: {response}")
            pod_name = cast(str, response.metadata.name) if isinstance(response.metadata, client.V1ObjectMeta) else None
            return ephemeralMcpServer(config=config, pod_name=pod_name)
        except client.rest.ApiException as e:
            logger.exception(msg=f"Error creating job '{config.job_name}'", exc_info=e)
            return None

    def _delete_job(self, pod_name: str, namespace: str) -> bool:
        """
        Delete a Kubernetes job and its associated pods.

        Args:
            job_name: Name of the job to delete
            namespace: Kubernetes namespace

        Returns:
            True if the job was deleted successfully, False otherwise
        """
        # First get and delete pods with the job label
        try:
            pods = self._core_v1.list_namespaced_pod(namespace=namespace, label_selector=f"app={pod_name}")

            for pod in pods.items:
                logger.info(f"Deleting pod {pod.metadata.name}")
                self._core_v1.delete_namespaced_pod(
                    name=pod.metadata.name,
                    namespace=namespace,
                    body=client.V1DeleteOptions(grace_period_seconds=0, propagation_policy="Background"),
                )
        except client.rest.ApiException as e:
            logger.info(f"Error deleting pods: {e}")

        # Now delete the job itself
        try:
            self._batch_v1.delete_namespaced_job(
                name=pod_name, namespace=namespace, body=client.V1DeleteOptions(propagation_policy="Foreground")
            )
            logger.info(f"Job '{pod_name}' deleted successfully")
        except client.rest.ApiException as e:
            logger.info(f"Error deleting job: {e}")
            return False
        else:
            return True

    def get_job_status(self, pod_name: str, namespace: str | None = None) -> None | client.V1Job:
        """
        Get current status of a job.

        Args:
            pod_name: Name of the pod
            namespace: Kubernetes namespace (defaults to the configured namespace)

        Returns:
            The job status
        """
        if namespace is None and pod_name in self.jobs:
            namespace = self.jobs[pod_name].config.namespace
        elif namespace is None:
            raise MCPJobNotFoundError

        try:
            job = self._batch_v1.read_namespaced_job(name=pod_name, namespace=namespace)

            # Get status
            active = job.status.active if job.status.active else 0
            succeeded = job.status.succeeded if job.status.succeeded else 0
            failed = job.status.failed if job.status.failed else 0

            logger.info(f"Job '{pod_name}' status:")
            logger.info(f"Active pods: {active}")
            logger.info(f"Succeeded pods: {succeeded}")
            logger.info(f"Failed pods: {failed}")

            # Get job creation time
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

    async def start_mcp_server(self, config: ephemeralMcpServerConfig) -> ephemeralMcpServer:
        """Start a new MCP server using the provided configuration."""
        # Create the job
        mcp_server = self._create_job(config)
        if mcp_server is None:
            raise MCPServerCreationError
        self.jobs[mcp_server.pod_name] = mcp_server
        return mcp_server
