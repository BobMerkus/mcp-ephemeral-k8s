import time

import pytest

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServerConfig
from mcp_ephemeral_k8s.api.exceptions import MCPJobNotFoundError
from mcp_ephemeral_k8s.session_manager import KubernetesSessionManager


def test_session_manager_creation_no_context_manager():
    session_manager = KubernetesSessionManager()
    assert session_manager is not None
    assert not hasattr(session_manager, "_api_client")
    assert not hasattr(session_manager, "_batch_v1")
    assert not hasattr(session_manager, "_core_v1")


def test_session_manager_creation_with_context_manager():
    with KubernetesSessionManager() as session_manager:
        assert session_manager is not None
        assert hasattr(session_manager, "_api_client")
        assert hasattr(session_manager, "_batch_v1")
        assert hasattr(session_manager, "_core_v1")


def test_session_manager_start_mcp_server_default_values():
    with KubernetesSessionManager() as session_manager:
        config = EphemeralMcpServerConfig()
        mcp_server = session_manager.create_mcp_server(config)
        assert mcp_server is not None
        assert mcp_server.pod_name is not None
        assert mcp_server.config.port is not None
        assert mcp_server.url is not None
        assert mcp_server.sse_url is not None

        # check that the job was created (we are not waiting for the job to be ready)
        result = session_manager.get_job_status(mcp_server.pod_name)
        assert result is not None
        assert result.status.active is None or result.status.active == 1
        assert result.status.succeeded is None or result.status.succeeded == 1
        assert result.status.failed is None or result.status.failed == 1

    # wait for the jobs to be deleted from the cluster
    time.sleep(1)

    # after the context manager exits, the job should be deleted
    with KubernetesSessionManager() as session_manager, pytest.raises(MCPJobNotFoundError):
        # check that the job was deleted
        result = session_manager.get_job_status(mcp_server.pod_name)
        assert result is None


def test_session_manager_start_mcp_server_invoke_runtime():
    """Test that the MCP server is started and the runtime is invokable."""
    with KubernetesSessionManager() as session_manager:
        config = EphemeralMcpServerConfig()
        mcp_server = session_manager.create_mcp_server(config)
        try:
            session_manager.expose_mcp_server_port(mcp_server)
        finally:
            session_manager.remove_mcp_server_port(mcp_server)
            session_manager.delete_mcp_server(mcp_server.pod_name)
