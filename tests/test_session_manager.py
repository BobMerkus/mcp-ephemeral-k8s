import os

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServerConfig
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
    config = EphemeralMcpServerConfig(
        runtime_exec="uvx",
        runtime_mcp="mcp-server-fetch",
    )
    with KubernetesSessionManager() as session_manager:
        mcp_server = session_manager.create_mcp_server(config, wait_for_ready=True)
        assert mcp_server is not None
        assert mcp_server.pod_name is not None
        assert mcp_server.config.port is not None
        assert mcp_server.url is not None
        assert mcp_server.sse_url is not None
        # check that the job was created successfully
        result = session_manager._get_job_status(mcp_server.pod_name)
        assert result is not None
        assert result.status.active == 1
        assert result.status.succeeded is None
        assert result.status.failed is None
        # manually delete the job
        session_manager.delete_mcp_server(mcp_server.pod_name, wait_for_deletion=True)

    # after the context manager exits, the job should be deleted
    with KubernetesSessionManager() as session_manager:
        # check that the job was deleted
        result = session_manager._get_job_status(mcp_server.pod_name)
        assert result is None


def test_session_manager_start_mcp_server_invoke_runtime():
    """Test that the MCP server is started and the runtime is invokable."""
    config = EphemeralMcpServerConfig(
        runtime_exec="uvx",
        runtime_mcp="mcp-server-fetch",
    )
    with KubernetesSessionManager() as session_manager:
        mcp_server = session_manager.create_mcp_server(config)
        try:
            session_manager.expose_mcp_server_port(mcp_server)
        finally:
            session_manager.remove_mcp_server_port(mcp_server)
            session_manager.delete_mcp_server(mcp_server.pod_name)


def test_session_manager_start_mcp_server_github():
    """Test that the MCP server is started and the runtime is invokable."""
    config = EphemeralMcpServerConfig(
        runtime_exec="npx",
        runtime_mcp="@modelcontextprotocol/server-github",
        env={
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"),
            "GITHUB_DYNAMIC_TOOLSETS": "1",
        },
    )
    with KubernetesSessionManager() as session_manager:
        try:
            mcp_server = session_manager.create_mcp_server(config, wait_for_ready=True)
            assert mcp_server is not None
            # check that the job was created successfully
            status = session_manager._get_job_status(mcp_server.pod_name)
            assert status is not None
            assert status.status.active == 1
            assert status.status.succeeded is None
            assert status.status.failed is None
        finally:
            session_manager.delete_mcp_server(mcp_server.pod_name)
