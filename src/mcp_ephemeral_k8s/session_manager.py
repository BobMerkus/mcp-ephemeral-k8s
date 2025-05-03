"""
This module contains the session manager for the MCP ephemeral K8s library.
It is used to create and manage MCP servers in a Kubernetes cluster.
"""

import logging
from typing import Any, Self

from kubernetes import client
from kubernetes.client.api.batch_v1_api import BatchV1Api
from kubernetes.client.api.core_v1_api import CoreV1Api
from kubernetes.client.api_client import ApiClient
from kubernetes.config.incluster_config import load_incluster_config
from kubernetes.config.kube_config import load_kube_config
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from mcp_ephemeral_k8s.api.model import EphemeralMcpServer, EphemeralMcpServerConfig
from mcp_ephemeral_k8s.exceptions import MCPJobNotFoundError, MCPServerCreationError
from mcp_ephemeral_k8s.k8s.job import create_mcp_server_job, delete_mcp_server_job, get_mcp_server_job_status

logger = logging.getLogger(__name__)


class KubernetesSessionManager(BaseModel):
    """
    Kubernetes session manager for MCP.

    This manager creates and manages Kubernetes jobs for MCP sessions.
    It implements the async context manager protocol for easy resource management.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    namespace: str = Field(default="default", description="The namespace to create resources in")
    jobs: dict[str, EphemeralMcpServer] = Field(
        default_factory=dict,
        description="A dictionary mapping between pod names and MCP servers jobs that are running.",
    )
    _api_client: ApiClient = PrivateAttr()
    _batch_v1: BatchV1Api = PrivateAttr()
    _core_v1: CoreV1Api = PrivateAttr()

    def load_session_manager(self) -> Self:
        """Load Kubernetes configuration from default location or from service account if running in cluster."""
        self._load_kube_config()
        if not hasattr(self, "_api_client"):
            self._api_client = ApiClient()
        if not hasattr(self, "_batch_v1"):
            self._batch_v1 = BatchV1Api(self._api_client)
        if not hasattr(self, "_core_v1"):
            self._core_v1 = CoreV1Api(self._api_client)
        return self

    def _load_kube_config(self) -> None:
        """Load Kubernetes configuration from default location or from service account if running in cluster."""
        try:
            # Try to load from default config file
            load_kube_config()
            logger.info("Using local kubernetes configuration")
        except Exception:
            # If that fails, we might be running in a pod, so try to use service account
            load_incluster_config()
            logger.info("Using in-cluster kubernetes configuration")

    def __enter__(self) -> Self:
        """Enter the context manager."""
        self.load_session_manager()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context manager."""
        for job_name in self.jobs:
            self._delete_job(job_name)

    def _create_job(self, config: EphemeralMcpServerConfig) -> EphemeralMcpServer:
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
        job = create_mcp_server_job(config, self.namespace)
        response = self._batch_v1.create_namespaced_job(namespace=self.namespace, body=job)
        logger.info(f"Job '{config.job_name}' created successfully")
        logger.debug(f"Job response: {response}")
        if not response.metadata or not response.metadata.name:
            raise MCPServerCreationError(str(response.metadata))
        return EphemeralMcpServer(config=config, pod_name=response.metadata.name)

    def _delete_job(self, pod_name: str) -> bool:
        """
        Delete a Kubernetes job and its associated pods.

        Args:
            job_name: Name of the job to delete
            namespace: Kubernetes namespace

        Returns:
            True if the job was deleted successfully, False otherwise
        """
        return delete_mcp_server_job(self._core_v1, self._batch_v1, pod_name, self.namespace)

    def get_job_status(self, pod_name: str) -> None | client.V1Job:
        """
        Get current status of a job.

        Args:
            pod_name: Name of the pod
            namespace: Kubernetes namespace (defaults to the configured namespace)

        Returns:
            The job status
        """
        job = get_mcp_server_job_status(self._batch_v1, pod_name, self.namespace)
        if job is None:
            raise MCPJobNotFoundError(self.namespace, pod_name)
        return job

    def start_mcp_server(self, config: EphemeralMcpServerConfig) -> EphemeralMcpServer:
        """Start a new MCP server using the provided configuration."""
        mcp_server = self._create_job(config)
        self.jobs[mcp_server.pod_name] = mcp_server
        return mcp_server

    def delete_mcp_server(self, mcp_server: EphemeralMcpServer) -> None:
        """Delete the MCP server."""
        if mcp_server.pod_name in self.jobs:
            del self.jobs[mcp_server.pod_name]
            self._delete_job(mcp_server.pod_name)

    def expose_mcp_server_port(self, mcp_server: EphemeralMcpServer) -> None:
        """Expose the MCP server port to the outside world."""
        self._core_v1.create_namespaced_service(
            namespace=self.namespace,
            body=client.V1Service(
                metadata=client.V1ObjectMeta(name=mcp_server.pod_name),
                spec=client.V1ServiceSpec(
                    selector={"app": mcp_server.pod_name},
                    ports=[client.V1ServicePort(port=mcp_server.config.port)],
                ),
            ),
        )
        logger.info(f"Service '{mcp_server.pod_name}' created successfully")

    def remove_mcp_server_port(self, mcp_server: EphemeralMcpServer) -> None:
        """Remove the MCP server port from the outside world."""
        self._core_v1.delete_namespaced_service(name=mcp_server.pod_name, namespace=self.namespace)
        logger.info(f"Service '{mcp_server.pod_name}' deleted successfully")
