"""
This module contains the session manager for the MCP ephemeral K8s library.
It is used to create and manage MCP servers in a Kubernetes cluster.
"""

import logging
import os
from typing import Any, Self

from fastmcp import FastMCP
from kubernetes import client
from kubernetes.client.api import BatchV1Api, CoreV1Api, RbacAuthorizationV1Api
from kubernetes.client.api_client import ApiClient
from kubernetes.config.config_exception import ConfigException
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
    create_proxy_server,
    delete_mcp_server_job,
    expose_mcp_server_port,
    get_mcp_server_job_status,
    remove_mcp_server_port,
    wait_for_job_deletion,
    wait_for_job_ready,
)
from mcp_ephemeral_k8s.k8s.rbac import create_service_account_for_job, delete_service_account_for_job

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
    max_wait_time: float = Field(default=300, description="The maximum time to wait for a job to complete")
    _api_client: ApiClient = PrivateAttr()
    _batch_v1: BatchV1Api = PrivateAttr()
    _core_v1: CoreV1Api = PrivateAttr()
    _rbac_v1: RbacAuthorizationV1Api = PrivateAttr()

    def load_session_manager(self) -> Self:
        """Load Kubernetes configuration from default location or from service account if running in cluster."""
        self._load_kube_config()
        if not hasattr(self, "_api_client"):
            self._api_client = ApiClient()
        if not hasattr(self, "_batch_v1"):
            self._batch_v1 = BatchV1Api(self._api_client)
        if not hasattr(self, "_core_v1"):
            self._core_v1 = CoreV1Api(self._api_client)
        if not hasattr(self, "_rbac_v1"):
            self._rbac_v1 = RbacAuthorizationV1Api(self._api_client)
        # Check if the configured namespace exists using direct read (more efficient than listing all)
        try:
            self._core_v1.read_namespace(name=self.namespace)
        except Exception as e:
            raise MCPNamespaceNotFoundError(self.namespace) from e
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
            except (FileNotFoundError, OSError, ConfigException) as e:
                logger.warning(f"Failed to load local kubernetes configuration: {e}. Trying in-cluster configuration")
                self.runtime = KubernetesRuntime.INCLUSTER
            else:
                logger.info("Using local kubernetes configuration")
                return
        if self.runtime == KubernetesRuntime.INCLUSTER:
            try:
                load_incluster_config()
            except (FileNotFoundError, OSError) as e:
                msg = "Failed to load in-cluster configuration"
                raise InvalidKubeConfigError(msg) from e
            else:
                logger.info("Using in-cluster kubernetes configuration")
                return
        raise InvalidKubeConfigError(self.runtime)

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        self.load_session_manager()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the async context manager."""
        for job_name in self.jobs:
            await self._delete_job(job_name)

    async def _create_job(self, config: EphemeralMcpServerConfig) -> EphemeralMcpServer:
        """
        Create a job that will run until explicitly terminated.

        This also creates a dedicated ServiceAccount with RBAC permissions for the spawned pod.

        Args:
            config: The configuration for the MCP servers

        Returns:
            The MCP server instance
        """
        # Create ServiceAccount and RBAC resources for the job
        service_account_name = create_service_account_for_job(
            core_v1=self._core_v1,
            rbac_v1=self._rbac_v1,
            job_name=config.job_name,
            namespace=self.namespace,
            sa_config=config.sa_config,
        )

        # Create the job with the service account
        job = create_mcp_server_job(config=config, namespace=self.namespace, service_account_name=service_account_name)
        response = self._batch_v1.create_namespaced_job(namespace=self.namespace, body=job)
        logger.info(f"Job '{config.job_name}' created successfully")
        logger.debug(f"Job response: {response}")
        if not response.metadata or not response.metadata.name:
            raise MCPServerCreationError(str(response.metadata))
        return EphemeralMcpServer(config=config, job_name=response.metadata.name)

    async def _get_job_status(self, job_name: str) -> None | client.V1Job:
        """
        Get current status of a job.

        Args:
            job_name: Name of the pod

        Returns:
            The job status
        """
        return get_mcp_server_job_status(self._batch_v1, job_name, self.namespace)

    async def _check_pod_status(self, job_name: str) -> bool:
        """
        Check the status of pods associated with a job.

        Args:
            job_name: Name of the job/pod

        Returns:
            True if a pod is running and ready (probes successful), False if waiting for pods

        Raises:
            MCPJobError: If a pod is in Failed or Unknown state
        """
        return check_pod_status(self._core_v1, job_name, self.namespace)

    async def _wait_for_job_ready(self, job_name: str) -> None:
        """Wait for a job's pod to be in the running state and ready (probes successful).

        Args:
            job_name: Name of the job/pod
        """
        await wait_for_job_ready(
            self._batch_v1, self._core_v1, job_name, self.namespace, self.sleep_time, self.max_wait_time
        )

    async def _wait_for_job_deletion(self, job_name: str) -> None:
        """Wait for a job to be deleted.

        Args:
            job_name: Name of the job/pod
        """
        await wait_for_job_deletion(self._batch_v1, job_name, self.namespace, self.sleep_time, self.max_wait_time)

    async def _delete_job(self, job_name: str) -> bool:
        """
        Delete a Kubernetes job and its associated pods.

        This also deletes the dedicated ServiceAccount and RBAC resources.

        Args:
            job_name: Name of the job/pod

        Returns:
            True if the job was deleted successfully, False otherwise
        """
        # Remove service port if it exists
        if job_name in self.jobs:
            try:
                self.remove_mcp_server_port(self.jobs[job_name])
            except Exception as e:
                logger.warning(f"Failed to remove MCP server port for job {job_name}: {e}")
        else:
            logger.warning(f"Job {job_name} not found in session manager, skipping port removal")

        # Delete the job and pods
        job_deleted = delete_mcp_server_job(self._core_v1, self._batch_v1, job_name, self.namespace)

        # Delete ServiceAccount and RBAC resources
        if job_name in self.jobs:
            job_config = self.jobs[job_name].config
            cluster_wide = job_config.sa_config.cluster_wide if job_config.sa_config else True
        else:
            # Default to cluster_wide=True if job not found in tracking
            cluster_wide = True
            logger.warning(f"Job {job_name} config not found, using default cluster_wide=True for RBAC cleanup")

        rbac_deleted = delete_service_account_for_job(
            core_v1=self._core_v1,
            rbac_v1=self._rbac_v1,
            job_name=job_name,
            namespace=self.namespace,
            cluster_wide=cluster_wide,
        )

        return job_deleted and rbac_deleted

    async def create_mcp_server(
        self, config: EphemeralMcpServerConfig, wait_for_ready: bool = True, expose_port: bool = False
    ) -> EphemeralMcpServer:
        """Start a new MCP server using the provided configuration.

        Args:
            config: The configuration for the MCP servers
            wait_for_ready: Whether to wait for the job to be ready before returning a response to the client
            expose_port: Whether to expose the port through a Kubernetes service

        Returns:
            The MCP server instance
        """
        mcp_server = await self._create_job(config)
        self.jobs[mcp_server.job_name] = mcp_server
        if wait_for_ready:
            await self._wait_for_job_ready(mcp_server.job_name)
            logger.info(f"MCP server {mcp_server.job_name} ready")
        if expose_port:
            self.expose_mcp_server_port(mcp_server)
            logger.info(f"MCP server {mcp_server.job_name} port exposed with service '{mcp_server.job_name}'")
        return mcp_server

    async def delete_mcp_server(self, job_name: str, wait_for_deletion: bool = True) -> EphemeralMcpServer:
        """Delete the MCP server.

        Args:
            job_name: Name of the job/pod
            wait_for_deletion: Whether to wait for the job to be deleted

        Returns:
            The MCP server instance
        """
        if job_name in self.jobs:
            await self._delete_job(job_name)
            if wait_for_deletion:
                await self._wait_for_job_deletion(job_name)
            config = self.jobs[job_name].config
            result = EphemeralMcpServer(config=config, job_name=job_name)
            del self.jobs[job_name]
            return result
        raise MCPJobNotFoundError(self.namespace, job_name)

    def expose_mcp_server_port(self, mcp_server: EphemeralMcpServer) -> None:
        """Expose the MCP server port to the outside world through a Kubernetes service."""
        expose_mcp_server_port(self._core_v1, mcp_server.job_name, self.namespace, mcp_server.config.port)

    def remove_mcp_server_port(self, mcp_server: EphemeralMcpServer) -> None:
        """Remove the MCP server."""
        remove_mcp_server_port(self._core_v1, mcp_server.job_name, self.namespace)

    async def mount_mcp_server(self, job_name: str) -> tuple[FastMCP, EphemeralMcpServer]:
        """Mount an MCP server over SSE.

        Args:
            job_name: The name of the pod that is running the MCP server.
        """
        if job_name not in self.jobs:
            raise MCPJobNotFoundError(self.namespace, job_name)
        mcp_server = self.jobs[job_name]
        url = str(mcp_server.sse_url)
        if self.runtime == KubernetesRuntime.KUBECONFIG:
            # @TODO we need to port forward when running locally
            url = f"http://localhost:{mcp_server.config.port}/sse"
            logger.warning(
                f"The MCP server is running locally, port forwarding to localhost is required if you want to access {url=!r} for {job_name=!r}"
            )
        else:
            # we are running in a cluster
            url = str(mcp_server.sse_url)
        server = create_proxy_server(url=url)
        logger.info(f"Mounted MCP server {mcp_server.job_name} over SSE")
        return server, mcp_server


__all__ = ["KubernetesSessionManager"]
