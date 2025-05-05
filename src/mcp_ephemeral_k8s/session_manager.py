"""
This module contains the session manager for the MCP ephemeral K8s library.
It is used to create and manage MCP servers in a Kubernetes cluster.
"""

import logging
import os
from typing import Any, Self

from kubernetes import client
from kubernetes.client.api.batch_v1_api import BatchV1Api
from kubernetes.client.api.core_v1_api import CoreV1Api
from kubernetes.client.api_client import ApiClient
from kubernetes.config.incluster_config import load_incluster_config
from kubernetes.config.kube_config import load_kube_config
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer, EphemeralMcpServerConfig, KubernetesRuntime
from mcp_ephemeral_k8s.api.exceptions import (
    InvalidKubeConfigError,
    MCPJobNotFoundError,
    MCPNamespaceNotFoundError,
    MCPServerCreationError,
)
from mcp_ephemeral_k8s.k8s.job import (
    check_pod_status,
    create_mcp_server_job,
    delete_mcp_server_job,
    expose_mcp_server_port,
    get_mcp_server_job_status,
    remove_mcp_server_port,
    wait_for_job_deletion,
    wait_for_job_ready,
)

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
    runtime: KubernetesRuntime = Field(
        default=KubernetesRuntime.KUBECONFIG, description="The runtime to use for the MCP server"
    )
    sleep_time: float = Field(default=1, description="The time to sleep between job status checks")
    max_wait_time: float = Field(default=60, description="The maximum time to wait for a job to complete")
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
        # check if the configured namespace exists
        namespaces = self._core_v1.list_namespace().items
        if self.namespace not in [namespace.metadata.name for namespace in namespaces if namespace.metadata]:
            raise MCPNamespaceNotFoundError(self.namespace)
        return self

    def _load_kube_config(self) -> None:
        """Load Kubernetes configuration from default location or from service account if running in cluster."""
        if self.runtime == KubernetesRuntime.KUBECONFIG:
            try:
                load_kube_config(
                    config_file=os.environ.get("KUBECONFIG"),
                    context=os.environ.get("KUBECONTEXT"),
                    client_configuration=None,
                    persist_config=False,
                )
                logger.info("Using local kubernetes configuration")
                return  # noqa: TRY300
            except Exception:
                logger.warning("Failed to load local kubernetes configuration, trying in-cluster configuration")
                self.runtime = KubernetesRuntime.INCLUSTER
        if self.runtime == KubernetesRuntime.INCLUSTER:
            load_incluster_config()
            logger.info("Using in-cluster kubernetes configuration")
            return
        raise InvalidKubeConfigError(self.runtime)

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

    def _get_job_status(self, pod_name: str) -> None | client.V1Job:
        """
        Get current status of a job.

        Args:
            pod_name: Name of the pod

        Returns:
            The job status
        """
        return get_mcp_server_job_status(self._batch_v1, pod_name, self.namespace)

    def _check_pod_status(self, pod_name: str) -> bool:
        """
        Check the status of pods associated with a job.

        Args:
            pod_name: Name of the job/pod

        Returns:
            True if a pod is running and ready (probes successful), False if waiting for pods

        Raises:
            MCPJobError: If a pod is in Failed or Unknown state
        """
        return check_pod_status(self._core_v1, pod_name, self.namespace)

    def _wait_for_job_ready(self, pod_name: str) -> None:
        """Wait for a job's pod to be in the running state and ready (probes successful)."""
        wait_for_job_ready(self._batch_v1, self._core_v1, pod_name, self.namespace, self.sleep_time, self.max_wait_time)

    def _wait_for_job_deletion(self, pod_name: str) -> None:
        """Wait for a job to be deleted."""
        wait_for_job_deletion(self._batch_v1, pod_name, self.namespace, self.sleep_time, self.max_wait_time)

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

    def create_mcp_server(self, config: EphemeralMcpServerConfig, wait_for_ready: bool = True) -> EphemeralMcpServer:
        """Start a new MCP server using the provided configuration."""
        mcp_server = self._create_job(config)
        self.jobs[mcp_server.pod_name] = mcp_server
        if wait_for_ready:
            self._wait_for_job_ready(mcp_server.pod_name)
        return mcp_server

    def delete_mcp_server(self, name: str, wait_for_deletion: bool = True) -> EphemeralMcpServer:
        """Delete the MCP server."""
        if name in self.jobs:
            job = self.jobs[name]
            self._delete_job(name)
            del self.jobs[name]
            if wait_for_deletion:
                self._wait_for_job_deletion(name)
            return job
        raise MCPJobNotFoundError(self.namespace, name)

    def expose_mcp_server_port(self, mcp_server: EphemeralMcpServer) -> None:
        """Expose the MCP server port to the outside world."""
        expose_mcp_server_port(self._core_v1, mcp_server.pod_name, self.namespace, mcp_server.config.port)

    def remove_mcp_server_port(self, mcp_server: EphemeralMcpServer) -> None:
        """Remove the MCP server port from the outside world."""
        remove_mcp_server_port(self._core_v1, mcp_server.pod_name, self.namespace)


__all__ = ["KubernetesSessionManager"]
