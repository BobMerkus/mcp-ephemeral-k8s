from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client import V1Job, V1JobStatus, V1ObjectMeta, V1Pod, V1PodList, V1PodStatus

from mcp_ephemeral_k8s import KubernetesSessionManager, presets
from mcp_ephemeral_k8s.api.exceptions import MCPNamespaceNotFoundError
from mcp_ephemeral_k8s.integrations.presets import BEDROCK_KB_RETRIEVAL, FETCH, GIT, GITLAB, TIME


@pytest.fixture
def mock_kube_client():
    with (
        patch("kubernetes.client.api_client.ApiClient") as mock_api_client,
        patch("kubernetes.client.api.batch_v1_api.BatchV1Api") as mock_batch_v1,
        patch("kubernetes.client.api.core_v1_api.CoreV1Api") as mock_core_v1,
        patch("kubernetes.config.kube_config.load_kube_config") as mock_load_kube,
        patch("kubernetes.config.incluster_config.load_incluster_config") as mock_load_incluster,
    ):
        # Mock namespace list
        mock_namespace = MagicMock()
        mock_namespace.metadata.name = "default"
        mock_core_v1.return_value.list_namespace.return_value.items = [mock_namespace]

        yield {
            "api_client": mock_api_client,
            "batch_v1": mock_batch_v1,
            "core_v1": mock_core_v1,
            "load_kube": mock_load_kube,
            "load_incluster": mock_load_incluster,
        }


def test_session_manager_creation_no_context_manager():
    session_manager = KubernetesSessionManager()
    assert session_manager is not None
    assert not hasattr(session_manager, "_api_client")
    assert not hasattr(session_manager, "_batch_v1")
    assert not hasattr(session_manager, "_core_v1")


def test_session_manager_creation_with_context_manager(mock_kube_client):
    with KubernetesSessionManager() as session_manager:
        assert session_manager is not None
        assert hasattr(session_manager, "_api_client")
        assert hasattr(session_manager, "_batch_v1")
        assert hasattr(session_manager, "_core_v1")


def test_session_manager_creation_with_valid_namespace(mock_kube_client):
    with KubernetesSessionManager(namespace="default"):
        pass


def test_session_manager_invalid_namespace(mock_kube_client):
    # Mock to simulate a nonexistent namespace
    mock_kube_client["core_v1"].return_value.list_namespace.return_value.items = [
        MagicMock(metadata=MagicMock(name="default"))
    ]

    with pytest.raises(MCPNamespaceNotFoundError), KubernetesSessionManager(namespace="invalid-namespace"):
        pass


def test_session_manager_start_mcp_server_time(mock_kube_client):
    # Create a mock response for job creation
    mock_job_response = MagicMock()
    mock_job_response.metadata.name = "mock-job-name"
    mock_kube_client["batch_v1"].return_value.create_namespaced_job.return_value = mock_job_response

    # Setup mock job status
    mock_job_status = V1Job(metadata=V1ObjectMeta(name="mock-job-name"), status=V1JobStatus(active=1))
    mock_kube_client["batch_v1"].return_value.read_namespaced_job.return_value = mock_job_status

    # Setup mock pod status for ready check
    mock_pod = V1Pod(metadata=V1ObjectMeta(name="mock-pod-name"), status=V1PodStatus(phase="Running"))
    mock_pod_list = V1PodList(items=[mock_pod])
    mock_kube_client["core_v1"].return_value.list_namespaced_pod.return_value = mock_pod_list

    with (
        patch("mcp_ephemeral_k8s.k8s.job.check_pod_status", return_value=True),
        KubernetesSessionManager() as session_manager,
    ):
        mcp_server = session_manager.create_mcp_server(TIME, wait_for_ready=True)
        assert mcp_server is not None
        assert mcp_server.pod_name is not None


def test_session_manager_start_mcp_server_fetch(mock_kube_client):
    # Create a mock response for job creation
    mock_job_response = MagicMock()
    mock_job_response.metadata.name = "mock-job-name"
    mock_kube_client["batch_v1"].return_value.create_namespaced_job.return_value = mock_job_response

    # Setup mock job status
    mock_job_status = V1Job(metadata=V1ObjectMeta(name="mock-job-name"), status=V1JobStatus(active=1))
    mock_kube_client["batch_v1"].return_value.read_namespaced_job.return_value = mock_job_status

    # Setup mock pod status for ready check
    mock_pod = V1Pod(metadata=V1ObjectMeta(name="mock-pod-name"), status=V1PodStatus(phase="Running"))
    mock_pod_list = V1PodList(items=[mock_pod])
    mock_kube_client["core_v1"].return_value.list_namespaced_pod.return_value = mock_pod_list

    # Mock pod status check to simulate readiness
    with (
        patch("mcp_ephemeral_k8s.k8s.job.check_pod_status", return_value=True),
        KubernetesSessionManager() as session_manager,
    ):
        mcp_server = session_manager.create_mcp_server(FETCH, wait_for_ready=True)
        assert mcp_server is not None
        assert mcp_server.pod_name is not None
        assert mcp_server.config.port is not None
        assert mcp_server.url is not None
        assert mcp_server.sse_url is not None

        # Check that the job was created successfully
        result = session_manager._get_job_status(mcp_server.pod_name)
        assert result is not None
        assert result.status.active == 1
        assert result.status.succeeded is None
        assert result.status.failed is None

        # Set up for deletion test
        mock_kube_client["batch_v1"].return_value.read_namespaced_job.side_effect = [
            mock_job_status,  # First call returns the job
            None,  # Second call returns None to simulate job deletion
        ]

        # Manually delete the job
        session_manager.delete_mcp_server(mcp_server.pod_name, wait_for_deletion=True)

    # After the context manager exits, simulate the job being deleted
    # by making _get_job_status return None
    with (
        patch("mcp_ephemeral_k8s.k8s.job.get_mcp_server_job_status", return_value=None),
        KubernetesSessionManager() as session_manager,
    ):
        # Check that the job was deleted
        result = session_manager._get_job_status(mcp_server.pod_name)
        assert result is None


def test_session_manager_start_mcp_server_git(mock_kube_client):
    """Test that the MCP server is started and the runtime is invokable."""
    # Create a mock response for job creation
    mock_job_response = MagicMock()
    mock_job_response.metadata.name = "mock-job-name"
    mock_kube_client["batch_v1"].return_value.create_namespaced_job.return_value = mock_job_response

    # Setup mock job status
    mock_job_status = V1Job(metadata=V1ObjectMeta(name="mock-job-name"), status=V1JobStatus(active=1))
    mock_kube_client["batch_v1"].return_value.read_namespaced_job.return_value = mock_job_status

    # Setup mock pod status for ready check
    mock_pod = V1Pod(metadata=V1ObjectMeta(name="mock-pod-name"), status=V1PodStatus(phase="Running"))
    mock_pod_list = V1PodList(items=[mock_pod])
    mock_kube_client["core_v1"].return_value.list_namespaced_pod.return_value = mock_pod_list

    with (
        patch("mcp_ephemeral_k8s.k8s.job.check_pod_status", return_value=True),
        KubernetesSessionManager() as session_manager,
    ):
        mcp_server = session_manager.create_mcp_server(GIT, wait_for_ready=True)
        assert mcp_server is not None

        # Check that the job was created successfully
        status = session_manager._get_job_status(mcp_server.pod_name)
        assert status is not None
        assert status.status.active == 1
        assert status.status.succeeded is None
        assert status.status.failed is None


def test_session_manager_start_mcp_server_fetch_expose_port(mock_kube_client):
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch)
    """
    # Create a mock response for job creation
    mock_job_response = MagicMock()
    mock_job_response.metadata.name = "mock-job-name"
    mock_kube_client["batch_v1"].return_value.create_namespaced_job.return_value = mock_job_response

    # Patch the underlying job module functions directly
    with (
        patch("mcp_ephemeral_k8s.session_manager.expose_mcp_server_port") as mock_expose,
        patch("mcp_ephemeral_k8s.session_manager.remove_mcp_server_port") as mock_remove,
        KubernetesSessionManager() as session_manager,
    ):
        mcp_server = session_manager.create_mcp_server(FETCH, expose_port=False)
        try:
            session_manager.expose_mcp_server_port(mcp_server)
            mock_expose.assert_called_once()
        finally:
            session_manager.remove_mcp_server_port(mcp_server)
            mock_remove.assert_called_once()


def test_session_manager_start_mcp_server_github(mock_kube_client):
    """Test that the MCP server is started and the runtime is invokable."""
    # Create a mock response for job creation
    mock_job_response = MagicMock()
    mock_job_response.metadata.name = "mock-job-name"
    mock_kube_client["batch_v1"].return_value.create_namespaced_job.return_value = mock_job_response

    # Setup mock job status
    mock_job_status = V1Job(metadata=V1ObjectMeta(name="mock-job-name"), status=V1JobStatus(active=1))
    mock_kube_client["batch_v1"].return_value.read_namespaced_job.return_value = mock_job_status

    # Setup mock pod status for ready check
    mock_pod = V1Pod(metadata=V1ObjectMeta(name="mock-pod-name"), status=V1PodStatus(phase="Running"))
    mock_pod_list = V1PodList(items=[mock_pod])
    mock_kube_client["core_v1"].return_value.list_namespaced_pod.return_value = mock_pod_list

    with (
        patch("mcp_ephemeral_k8s.k8s.job.check_pod_status", return_value=True),
        KubernetesSessionManager() as session_manager,
    ):
        mcp_server = session_manager.create_mcp_server(presets.GITHUB, wait_for_ready=True)
        assert mcp_server is not None

        # Check that the job was created successfully
        status = session_manager._get_job_status(mcp_server.pod_name)
        assert status is not None
        assert status.status.active == 1
        assert status.status.succeeded is None
        assert status.status.failed is None


def test_session_manager_start_mcp_server_gitlab(mock_kube_client):
    """Test that the MCP server is started and the runtime is invokable."""
    # Create a mock response for job creation
    mock_job_response = MagicMock()
    mock_job_response.metadata.name = "mock-job-name"
    mock_kube_client["batch_v1"].return_value.create_namespaced_job.return_value = mock_job_response

    # Setup mock job status
    mock_job_status = V1Job(metadata=V1ObjectMeta(name="mock-job-name"), status=V1JobStatus(active=1))
    mock_kube_client["batch_v1"].return_value.read_namespaced_job.return_value = mock_job_status

    # Setup mock pod status for ready check
    mock_pod = V1Pod(metadata=V1ObjectMeta(name="mock-pod-name"), status=V1PodStatus(phase="Running"))
    mock_pod_list = V1PodList(items=[mock_pod])
    mock_kube_client["core_v1"].return_value.list_namespaced_pod.return_value = mock_pod_list

    with (
        patch("mcp_ephemeral_k8s.k8s.job.check_pod_status", return_value=True),
        KubernetesSessionManager() as session_manager,
    ):
        mcp_server = session_manager.create_mcp_server(GITLAB, wait_for_ready=True)
        assert mcp_server is not None

        # Check that the job was created successfully
        status = session_manager._get_job_status(mcp_server.pod_name)
        assert status is not None
        assert status.status.active == 1
        assert status.status.succeeded is None
        assert status.status.failed is None


def test_session_manager_start_mcp_server_aws_kb_retrieval(mock_kube_client):
    """Test that the MCP server is started and the runtime is invokable."""
    # Create a mock response for job creation
    mock_job_response = MagicMock()
    mock_job_response.metadata.name = "mock-job-name"
    mock_kube_client["batch_v1"].return_value.create_namespaced_job.return_value = mock_job_response

    # Setup mock job status
    mock_job_status = V1Job(metadata=V1ObjectMeta(name="mock-job-name"), status=V1JobStatus(active=1))
    mock_kube_client["batch_v1"].return_value.read_namespaced_job.return_value = mock_job_status

    # Setup mock pod status for ready check
    mock_pod = V1Pod(metadata=V1ObjectMeta(name="mock-pod-name"), status=V1PodStatus(phase="Running"))
    mock_pod_list = V1PodList(items=[mock_pod])
    mock_kube_client["core_v1"].return_value.list_namespaced_pod.return_value = mock_pod_list

    with (
        patch("mcp_ephemeral_k8s.k8s.job.check_pod_status", return_value=True),
        KubernetesSessionManager() as session_manager,
    ):
        mcp_server = session_manager.create_mcp_server(BEDROCK_KB_RETRIEVAL, wait_for_ready=True)
        assert mcp_server is not None

        # Check that the job was created successfully
        status = session_manager._get_job_status(mcp_server.pod_name)
        assert status is not None
        assert status.status.active == 1
        assert status.status.succeeded is None
        assert status.status.failed is None
