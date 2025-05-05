from unittest.mock import MagicMock, patch

import pytest
from kubernetes import client

from mcp_ephemeral_k8s.api.exceptions import MCPPortForwardError
from mcp_ephemeral_k8s.k8s.job import create_port_forward, delete_port_forward


@pytest.fixture
def mock_core_v1():
    """Create a mock CoreV1Api client"""
    return MagicMock(spec=client.CoreV1Api)


@pytest.fixture
def mock_portforward():
    """Create a mock portforward function"""
    with patch("kubernetes.stream.portforward") as mock:
        yield mock


@pytest.mark.unit
def test_create_port_forward(mock_core_v1, mock_portforward):
    """Test that create_port_forward calls the portforward function with the correct arguments"""
    # Setup
    pod_name = "test-pod"
    namespace = "default"
    port = 8080

    # Execute
    create_port_forward(mock_core_v1, pod_name, namespace, port)

    # Verify
    mock_portforward.assert_called_once_with(
        mock_core_v1.connect_get_namespaced_pod_portforward, pod_name, namespace, ports=str(port), async_req=True
    )


@pytest.mark.unit
def test_create_port_forward_exception(mock_core_v1, mock_portforward):
    """Test that create_port_forward handles exceptions"""
    # Setup
    pod_name = "test-pod"
    namespace = "default"
    port = 8080
    mock_portforward.side_effect = MCPPortForwardError(pod_name, namespace, port)

    # Execute and verify
    with pytest.raises(
        MCPPortForwardError, match="Failed to create port forward: pod_name='test-pod' namespace='default' port=8080"
    ):
        create_port_forward(mock_core_v1, pod_name, namespace, port)


@pytest.mark.unit
def test_delete_port_forward(mock_core_v1):
    """Test that delete_port_forward completes successfully"""
    # Setup
    pod_name = "test-pod"
    namespace = "default"

    # Execute
    delete_port_forward(mock_core_v1, pod_name, namespace)

    # No assertions needed - function should complete without errors


@pytest.mark.unit
def test_delete_port_forward_exception(mock_core_v1):
    """Test that delete_port_forward handles exceptions"""
    # Setup
    pod_name = "test-pod"
    namespace = "default"
    mock_core_v1.delete_namespaced_service.side_effect = Exception("Deletion error")

    # Execute - function should complete without raising an exception
    delete_port_forward(mock_core_v1, pod_name, namespace)

    # We don't expect an exception to be raised, as delete_port_forward catches it internally


@pytest.mark.unit
def test_session_manager_integration():
    """Test port forwarding in the session manager"""
    # Create a mock portforward object
    mock_pf = MagicMock()

    # We need to mock the actual portforward function from kubernetes.stream
    with patch("kubernetes.stream.portforward", return_value=mock_pf) as mock_portforward:
        # Create mock MCP server
        mock_server = MagicMock()
        mock_server.pod_name = "test-pod"
        mock_server.config = MagicMock()
        mock_server.config.port = 8080

        # Create a mock CoreV1Api
        mock_core_v1 = MagicMock()

        # Test the create_port_forward function directly
        result = create_port_forward(mock_core_v1, mock_server.pod_name, "default", mock_server.config.port)

        # Verify it returns our mock portforward object
        assert result is mock_pf

        # Verify that portforward was called with the correct arguments
        mock_portforward.assert_called_once_with(
            mock_core_v1.connect_get_namespaced_pod_portforward,
            mock_server.pod_name,
            "default",
            ports=str(mock_server.config.port),
            async_req=True,
        )

        # Test the delete_port_forward function directly without mocking it
        # This is already tested in test_delete_port_forward() above
        delete_port_forward(mock_core_v1, mock_server.pod_name, "default")
