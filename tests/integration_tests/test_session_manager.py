import pytest

from mcp_ephemeral_k8s import KubernetesSessionManager, presets
from mcp_ephemeral_k8s.api.exceptions import MCPNamespaceNotFoundError


@pytest.mark.integration
def test_session_manager_attributes(kubernetes_session_manager: KubernetesSessionManager):
    """Test that the session manager has the expected attributes."""
    assert kubernetes_session_manager is not None
    assert hasattr(kubernetes_session_manager, "_api_client")
    assert hasattr(kubernetes_session_manager, "_batch_v1")
    assert hasattr(kubernetes_session_manager, "_core_v1")


@pytest.mark.integration
def test_session_manager_start_mcp_server_time(kubernetes_session_manager: KubernetesSessionManager):
    """Test that the MCP server for time is started correctly."""
    mcp_server = kubernetes_session_manager.create_mcp_server(presets.TIME, wait_for_ready=True)
    assert mcp_server is not None
    assert mcp_server.pod_name is not None
    # Cleanup after test
    kubernetes_session_manager.delete_mcp_server(mcp_server.pod_name, wait_for_deletion=True)


@pytest.mark.integration
def test_session_manager_start_mcp_server_fetch(kubernetes_session_manager: KubernetesSessionManager):
    """Test that the MCP server for fetch is started correctly."""
    mcp_server = kubernetes_session_manager.create_mcp_server(presets.FETCH, wait_for_ready=True)
    assert mcp_server is not None
    assert mcp_server.pod_name is not None
    assert mcp_server.config.port is not None
    assert mcp_server.url is not None
    assert mcp_server.sse_url is not None

    # check that the job was created successfully
    result = kubernetes_session_manager._get_job_status(mcp_server.pod_name)
    assert result is not None
    assert result.status.active == 1
    assert result.status.succeeded is None
    assert result.status.failed is None

    # Cleanup after test
    kubernetes_session_manager.delete_mcp_server(mcp_server.pod_name, wait_for_deletion=True)


@pytest.mark.integration
def test_session_manager_creation_no_context_manager():
    session_manager = KubernetesSessionManager()
    assert session_manager is not None
    assert not hasattr(session_manager, "_api_client")
    assert not hasattr(session_manager, "_batch_v1")
    assert not hasattr(session_manager, "_core_v1")


@pytest.mark.integration
def test_session_manager_creation_with_context_manager():
    with KubernetesSessionManager() as session_manager:
        assert session_manager is not None
        assert hasattr(session_manager, "_api_client")
        assert hasattr(session_manager, "_batch_v1")
        assert hasattr(session_manager, "_core_v1")


@pytest.mark.integration
def test_session_manager_creation_with_valid_namespace():
    with KubernetesSessionManager(namespace="default"):
        pass


@pytest.mark.integration
def test_session_manager_invalid_namespace():
    with pytest.raises(MCPNamespaceNotFoundError), KubernetesSessionManager(namespace="invalid-namespace"):
        pass


@pytest.mark.integration
def test_session_manager_start_mcp_server_git(kubernetes_session_manager: KubernetesSessionManager):
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/modelcontextprotocol/servers/tree/main/src/git)
    """
    mcp_server = kubernetes_session_manager.create_mcp_server(presets.GIT, wait_for_ready=True)
    assert mcp_server is not None
    # check that the job was created successfully
    status = kubernetes_session_manager._get_job_status(mcp_server.pod_name)
    assert status is not None
    assert status.status.active == 1
    assert status.status.succeeded is None
    assert status.status.failed is None


@pytest.mark.integration
def test_session_manager_start_mcp_server_fetch_expose_port(kubernetes_session_manager: KubernetesSessionManager):
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch)
    """
    mcp_server = kubernetes_session_manager.create_mcp_server(presets.FETCH, expose_port=False)
    try:
        kubernetes_session_manager.expose_mcp_server_port(mcp_server)
    finally:
        kubernetes_session_manager.remove_mcp_server_port(mcp_server)


@pytest.mark.integration
def test_session_manager_start_mcp_server_github(kubernetes_session_manager: KubernetesSessionManager):
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/github/github-mcp-server)
    """
    mcp_server = kubernetes_session_manager.create_mcp_server(presets.GITHUB, wait_for_ready=True, expose_port=False)
    assert mcp_server is not None
    # check that the job was created successfully
    status = kubernetes_session_manager._get_job_status(mcp_server.pod_name)
    assert status is not None
    assert status.status.active == 1
    assert status.status.succeeded is None
    assert status.status.failed is None


@pytest.mark.integration
def test_session_manager_start_mcp_server_gitlab(kubernetes_session_manager: KubernetesSessionManager):
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/zereight/mcp-gitlab)
    """
    mcp_server = kubernetes_session_manager.create_mcp_server(presets.GITLAB, wait_for_ready=True)
    assert mcp_server is not None
    # check that the job was created successfully
    status = kubernetes_session_manager._get_job_status(mcp_server.pod_name)
    assert status is not None
    assert status.status.active == 1
    assert status.status.succeeded is None
    assert status.status.failed is None


@pytest.mark.integration
def test_session_manager_start_mcp_server_aws_kb_retrieval(kubernetes_session_manager: KubernetesSessionManager):
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/awslabs/mcp/tree/main/src/bedrock-kb-retrieval-mcp-server)
    """
    mcp_server = kubernetes_session_manager.create_mcp_server(presets.BEDROCK_KB_RETRIEVAL, wait_for_ready=True)
    assert mcp_server is not None
    # check that the job was created successfully
    status = kubernetes_session_manager._get_job_status(mcp_server.pod_name)
    assert status is not None
    assert status.status.active == 1
    assert status.status.succeeded is None
    assert status.status.failed is None
