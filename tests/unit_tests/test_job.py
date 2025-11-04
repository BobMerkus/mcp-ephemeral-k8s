"""Unit tests for job functions."""

from unittest.mock import MagicMock, patch

import pytest
from kubernetes import client
from kubernetes.client.rest import ApiException

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServerConfig
from mcp_ephemeral_k8s.api.exceptions import MCPJobError, MCPJobTimeoutError
from mcp_ephemeral_k8s.k8s.job import (
    _handle_failed_pod,
    _is_pod_ready,
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


def test_delete_mcp_server_job_success():
    """Test deleting MCP server job successfully."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock pod list
    mock_pod = MagicMock()
    mock_pod.metadata.name = "test-pod"
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    # Mock successful deletion
    mock_core_v1.delete_namespaced_pod.return_value = None
    mock_batch_v1.delete_namespaced_job.return_value = None

    result = delete_mcp_server_job(mock_core_v1, mock_batch_v1, job_name, namespace)

    assert result is True
    mock_core_v1.list_namespaced_pod.assert_called_once()
    mock_core_v1.delete_namespaced_pod.assert_called_once()
    mock_batch_v1.delete_namespaced_job.assert_called_once()


def test_delete_mcp_server_job_pod_without_metadata():
    """Test deleting MCP server job when pod has no metadata."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock pod without metadata
    mock_pod = MagicMock()
    mock_pod.metadata = None
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    # Mock successful job deletion
    mock_batch_v1.delete_namespaced_job.return_value = None

    result = delete_mcp_server_job(mock_core_v1, mock_batch_v1, job_name, namespace)

    assert result is True
    # Pod deletion should be skipped
    mock_core_v1.delete_namespaced_pod.assert_not_called()


def test_delete_mcp_server_job_pod_without_name():
    """Test deleting MCP server job when pod metadata has no name."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock pod with metadata but no name
    mock_pod = MagicMock()
    mock_pod.metadata.name = None
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    # Mock successful job deletion
    mock_batch_v1.delete_namespaced_job.return_value = None

    result = delete_mcp_server_job(mock_core_v1, mock_batch_v1, job_name, namespace)

    assert result is True
    # Pod deletion should be skipped
    mock_core_v1.delete_namespaced_pod.assert_not_called()


def test_delete_mcp_server_job_pod_deletion_error():
    """Test deleting MCP server job when pod deletion fails."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock pod list
    mock_pod = MagicMock()
    mock_pod.metadata.name = "test-pod"
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    # Mock pod deletion error
    mock_core_v1.delete_namespaced_pod.side_effect = ApiException(status=500, reason="Error")

    result = delete_mcp_server_job(mock_core_v1, mock_batch_v1, job_name, namespace)

    assert result is False
    mock_core_v1.delete_namespaced_pod.assert_called_once()
    # Job deletion should not be attempted
    mock_batch_v1.delete_namespaced_job.assert_not_called()


def test_delete_mcp_server_job_job_deletion_error():
    """Test deleting MCP server job when job deletion fails."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock empty pod list
    mock_pod_list = MagicMock()
    mock_pod_list.items = []
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    # Mock job deletion error
    mock_batch_v1.delete_namespaced_job.side_effect = ApiException(status=500, reason="Error")

    result = delete_mcp_server_job(mock_core_v1, mock_batch_v1, job_name, namespace)

    assert result is False
    mock_batch_v1.delete_namespaced_job.assert_called_once()


def test_check_pod_status_no_pods():
    """Test checking pod status when no pods are found."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock empty pod list
    mock_pod_list = MagicMock()
    mock_pod_list.items = []
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    result = check_pod_status(mock_core_v1, job_name, namespace)

    assert result is False
    mock_core_v1.list_namespaced_pod.assert_called_once()


def test_check_pod_status_pod_without_status():
    """Test checking pod status when pod has no status."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock pod without status
    mock_pod = MagicMock()
    mock_pod.status = None
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    result = check_pod_status(mock_core_v1, job_name, namespace)

    assert result is False


def test_check_pod_status_pod_without_phase():
    """Test checking pod status when pod status has no phase."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock pod with status but no phase
    mock_pod = MagicMock()
    mock_pod.status.phase = None
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    result = check_pod_status(mock_core_v1, job_name, namespace)

    assert result is False


@pytest.mark.asyncio
async def test_wait_for_job_deletion_timeout():
    """Test wait_for_job_deletion raises timeout error."""
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock that job still exists
    mock_job = MagicMock()
    mock_batch_v1.read_namespaced_job.return_value = mock_job

    with pytest.raises(MCPJobTimeoutError):
        await wait_for_job_deletion(mock_batch_v1, job_name, namespace, sleep_time=0.01, max_wait_time=0.05)


@pytest.mark.asyncio
async def test_wait_for_job_deletion_success():
    """Test wait_for_job_deletion completes when job is deleted."""
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock that job doesn't exist (404)
    mock_batch_v1.read_namespaced_job.side_effect = ApiException(status=404, reason="Not Found")

    # Should complete without error
    await wait_for_job_deletion(mock_batch_v1, job_name, namespace, sleep_time=0.01, max_wait_time=1)


def test_create_mcp_server_job():
    """Test creating MCP server job."""
    config = EphemeralMcpServerConfig(
        runtime_exec="uvx",
        runtime_mcp="test-mcp-server",
        runtime_args="--arg1 value1",
        env={"ENV_VAR": "value"},
    )
    namespace = "test-namespace"
    service_account_name = "test-sa"

    job = create_mcp_server_job(config, namespace, service_account_name)

    assert isinstance(job, client.V1Job)
    assert job.metadata.name == config.job_name
    assert job.metadata.namespace == namespace
    assert job.spec.template.spec.service_account_name == service_account_name
    assert len(job.spec.template.spec.containers) == 1
    container = job.spec.template.spec.containers[0]
    assert container.image == config.image
    assert container.command == config.entrypoint
    assert len(container.env) == 1
    assert container.env[0].name == "ENV_VAR"
    assert container.env[0].value == "value"


def test_create_mcp_server_job_no_env():
    """Test creating MCP server job without environment variables."""
    config = EphemeralMcpServerConfig(
        runtime_exec="uvx",
        runtime_mcp="test-mcp-server",
    )
    namespace = "test-namespace"

    job = create_mcp_server_job(config, namespace)

    assert isinstance(job, client.V1Job)
    container = job.spec.template.spec.containers[0]
    assert container.env == []


def test_get_mcp_server_job_status_success():
    """Test getting MCP server job status successfully."""
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock job with full status
    mock_job = MagicMock(spec=client.V1Job)
    mock_job.status.active = 1
    mock_job.status.succeeded = 0
    mock_job.status.failed = 0
    mock_job.metadata.creation_timestamp = "2024-01-01T00:00:00Z"
    mock_batch_v1.read_namespaced_job.return_value = mock_job

    result = get_mcp_server_job_status(mock_batch_v1, job_name, namespace)

    assert result == mock_job
    mock_batch_v1.read_namespaced_job.assert_called_once_with(name=job_name, namespace=namespace)


def test_get_mcp_server_job_status_not_found():
    """Test getting MCP server job status when job not found."""
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock 404 error
    mock_batch_v1.read_namespaced_job.side_effect = ApiException(status=404, reason="Not Found")

    result = get_mcp_server_job_status(mock_batch_v1, job_name, namespace)

    assert result is None


def test_get_mcp_server_job_status_other_error():
    """Test getting MCP server job status with other API error."""
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock 500 error
    mock_batch_v1.read_namespaced_job.side_effect = ApiException(status=500, reason="Internal Server Error")

    result = get_mcp_server_job_status(mock_batch_v1, job_name, namespace)

    assert result is None


def test_get_mcp_server_job_status_none_values():
    """Test getting MCP server job status with None status values."""
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock job with None status values
    mock_job = MagicMock(spec=client.V1Job)
    mock_job.status.active = None
    mock_job.status.succeeded = None
    mock_job.status.failed = None
    mock_batch_v1.read_namespaced_job.return_value = mock_job

    result = get_mcp_server_job_status(mock_batch_v1, job_name, namespace)

    assert result == mock_job


def test_is_pod_ready_true():
    """Test _is_pod_ready returns True for ready pod."""
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_condition = MagicMock()
    mock_condition.type = "Ready"
    mock_condition.status = "True"
    mock_pod.status.conditions = [mock_condition]

    result = _is_pod_ready(mock_pod)

    assert result is True


def test_is_pod_ready_false_no_conditions():
    """Test _is_pod_ready returns False when no conditions."""
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.status.conditions = None

    result = _is_pod_ready(mock_pod)

    assert result is False


def test_is_pod_ready_false_no_status():
    """Test _is_pod_ready returns False when no status."""
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.status = None

    result = _is_pod_ready(mock_pod)

    assert result is False


def test_is_pod_ready_false_not_ready():
    """Test _is_pod_ready returns False when pod not ready."""
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_condition = MagicMock()
    mock_condition.type = "Ready"
    mock_condition.status = "False"
    mock_pod.status.conditions = [mock_condition]

    result = _is_pod_ready(mock_pod)

    assert result is False


def test_handle_failed_pod_with_logs():
    """Test _handle_failed_pod with pod logs available."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.metadata.name = "test-pod"
    mock_pod.status.phase = "Failed"
    namespace = "test-namespace"
    job_name = "test-job"

    # Mock logs
    mock_core_v1.read_namespaced_pod_log.return_value = "Error: something went wrong"

    with pytest.raises(MCPJobError) as exc_info:
        _handle_failed_pod(mock_core_v1, mock_pod, namespace, job_name)

    assert "Failed" in str(exc_info.value)
    assert "Error: something went wrong" in str(exc_info.value)
    mock_core_v1.read_namespaced_pod_log.assert_called_once()


def test_handle_failed_pod_without_logs():
    """Test _handle_failed_pod when logs cannot be retrieved."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.metadata.name = "test-pod"
    mock_pod.status.phase = "Failed"
    namespace = "test-namespace"
    job_name = "test-job"

    # Mock log retrieval failure
    mock_core_v1.read_namespaced_pod_log.side_effect = Exception("Cannot retrieve logs")

    with pytest.raises(MCPJobError) as exc_info:
        _handle_failed_pod(mock_core_v1, mock_pod, namespace, job_name)

    assert "Failed" in str(exc_info.value)


def test_handle_failed_pod_no_metadata():
    """Test _handle_failed_pod when pod has no metadata."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.metadata = None
    mock_pod.status.phase = "Failed"
    namespace = "test-namespace"
    job_name = "test-job"

    with pytest.raises(MCPJobError) as exc_info:
        _handle_failed_pod(mock_core_v1, mock_pod, namespace, job_name)

    assert "Failed" in str(exc_info.value)


def test_check_pod_status_running_and_ready():
    """Test check_pod_status with running and ready pod."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock running and ready pod
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.status.phase = "Running"
    mock_condition = MagicMock()
    mock_condition.type = "Ready"
    mock_condition.status = "True"
    mock_pod.status.conditions = [mock_condition]
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    result = check_pod_status(mock_core_v1, job_name, namespace)

    assert result is True


def test_check_pod_status_running_not_ready():
    """Test check_pod_status with running but not ready pod."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock running but not ready pod
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.status.phase = "Running"
    mock_condition = MagicMock()
    mock_condition.type = "Ready"
    mock_condition.status = "False"
    mock_pod.status.conditions = [mock_condition]
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    result = check_pod_status(mock_core_v1, job_name, namespace)

    assert result is False


def test_check_pod_status_failed():
    """Test check_pod_status with failed pod."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock failed pod
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.metadata.name = "test-pod"
    mock_pod.status.phase = "Failed"
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list
    mock_core_v1.read_namespaced_pod_log.return_value = "Error logs"

    with pytest.raises(MCPJobError):
        check_pod_status(mock_core_v1, job_name, namespace)


def test_expose_mcp_server_port():
    """Test exposing MCP server port."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"
    port = 8080

    expose_mcp_server_port(mock_core_v1, job_name, namespace, port)

    mock_core_v1.create_namespaced_service.assert_called_once()
    call_args = mock_core_v1.create_namespaced_service.call_args
    assert call_args[1]["namespace"] == namespace
    service = call_args[1]["body"]
    assert service.metadata.name == job_name
    assert service.spec.ports[0].port == port


def test_remove_mcp_server_port():
    """Test removing MCP server port."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    remove_mcp_server_port(mock_core_v1, job_name, namespace)

    mock_core_v1.delete_namespaced_service.assert_called_once_with(name=job_name, namespace=namespace)


@pytest.mark.asyncio
async def test_wait_for_job_ready_success():
    """Test wait_for_job_ready completes when job becomes ready."""
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock job status
    mock_job = MagicMock(spec=client.V1Job)
    mock_job.status.active = 1
    mock_batch_v1.read_namespaced_job.return_value = mock_job

    # Mock ready pod
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.status.phase = "Running"
    mock_condition = MagicMock()
    mock_condition.type = "Ready"
    mock_condition.status = "True"
    mock_pod.status.conditions = [mock_condition]
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    await wait_for_job_ready(mock_batch_v1, mock_core_v1, job_name, namespace, sleep_time=0.01, max_wait_time=1)


@pytest.mark.asyncio
async def test_wait_for_job_ready_timeout():
    """Test wait_for_job_ready raises timeout error."""
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock job that never becomes ready
    mock_job = MagicMock(spec=client.V1Job)
    mock_job.status.active = 1
    mock_batch_v1.read_namespaced_job.return_value = mock_job

    # Mock pod that's never ready
    mock_pod_list = MagicMock()
    mock_pod_list.items = []
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    with pytest.raises(MCPJobTimeoutError):
        await wait_for_job_ready(mock_batch_v1, mock_core_v1, job_name, namespace, sleep_time=0.01, max_wait_time=0.05)


@pytest.mark.asyncio
async def test_wait_for_job_ready_job_not_found():
    """Test wait_for_job_ready when job is not found initially."""
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call - job not found
            raise ApiException(status=404, reason="Not Found")
        else:
            # Second call - job exists and ready
            mock_job = MagicMock(spec=client.V1Job)
            mock_job.status.active = 1
            return mock_job

    mock_batch_v1.read_namespaced_job.side_effect = side_effect

    # Mock ready pod for second iteration
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.status.phase = "Running"
    mock_condition = MagicMock()
    mock_condition.type = "Ready"
    mock_condition.status = "True"
    mock_pod.status.conditions = [mock_condition]
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    await wait_for_job_ready(mock_batch_v1, mock_core_v1, job_name, namespace, sleep_time=0.01, max_wait_time=1)


@pytest.mark.asyncio
async def test_wait_for_job_ready_no_status():
    """Test wait_for_job_ready when job has no status."""
    mock_batch_v1 = MagicMock(spec=client.BatchV1Api)
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_job = MagicMock(spec=client.V1Job)
        if call_count == 1:
            # First call - no status
            mock_job.status = None
        else:
            # Second call - has status and ready
            mock_job.status.active = 1
        return mock_job

    mock_batch_v1.read_namespaced_job.side_effect = side_effect

    # Mock ready pod for second iteration
    mock_pod = MagicMock(spec=client.V1Pod)
    mock_pod.status.phase = "Running"
    mock_condition = MagicMock()
    mock_condition.type = "Ready"
    mock_condition.status = "True"
    mock_pod.status.conditions = [mock_condition]
    mock_pod_list = MagicMock()
    mock_pod_list.items = [mock_pod]
    mock_core_v1.list_namespaced_pod.return_value = mock_pod_list

    await wait_for_job_ready(mock_batch_v1, mock_core_v1, job_name, namespace, sleep_time=0.01, max_wait_time=1)


def test_create_proxy_server():
    """Test creating a proxy server."""
    url = "http://test.example.com:8080/sse"

    with (
        patch("mcp_ephemeral_k8s.k8s.job.Client") as mock_client_class,
        patch("mcp_ephemeral_k8s.k8s.job.SSETransport") as mock_transport_class,
        patch("mcp_ephemeral_k8s.k8s.job.FastMCP") as mock_fastmcp_class,
    ):
        mock_transport = MagicMock()
        mock_transport_class.return_value = mock_transport
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_proxy = MagicMock()
        mock_fastmcp_class.as_proxy.return_value = mock_proxy

        result = create_proxy_server(url, sse_read_timeout=600.0)

        mock_transport_class.assert_called_once_with(url=url, sse_read_timeout=600.0)
        mock_client_class.assert_called_once_with(mock_transport)
        mock_fastmcp_class.as_proxy.assert_called_once_with(mock_client)
        assert result == mock_proxy


def test_create_proxy_server_filters_invalid_kwargs():
    """Test that create_proxy_server filters out invalid kwargs."""
    url = "http://test.example.com:8080/sse"

    with (
        patch("mcp_ephemeral_k8s.k8s.job.Client") as _mock_client_class,
        patch("mcp_ephemeral_k8s.k8s.job.SSETransport") as mock_transport_class,
        patch("mcp_ephemeral_k8s.k8s.job.FastMCP") as _mock_fastmcp_class,
    ):
        mock_transport = MagicMock()
        mock_transport_class.return_value = mock_transport

        # Call with both valid and invalid kwargs
        create_proxy_server(url, sse_read_timeout=300, invalid_param="should_be_filtered")

        # Only valid params should be passed to SSETransport
        call_kwargs = mock_transport_class.call_args[1]
        assert "sse_read_timeout" in call_kwargs
        assert "invalid_param" not in call_kwargs
