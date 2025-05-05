import pytest

from mcp_ephemeral_k8s.api.exceptions import MCPNamespaceNotFoundError
from mcp_ephemeral_k8s.integrations.presets import BEDROCK_KB_RETRIEVAL, FETCH, GIT, GITHUB, GITLAB, TIME
from mcp_ephemeral_k8s.session_manager import KubernetesSessionManager


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
def test_session_manager_start_mcp_server_time():
    with KubernetesSessionManager() as session_manager:
        mcp_server = session_manager.create_mcp_server(TIME, wait_for_ready=True)
        assert mcp_server is not None
        assert mcp_server.pod_name is not None


@pytest.mark.integration
def test_session_manager_start_mcp_server_default_values():
    with KubernetesSessionManager() as session_manager:
        mcp_server = session_manager.create_mcp_server(FETCH, wait_for_ready=True)
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
        session_manager.delete_mcp_server(
            mcp_server.pod_name, wait_for_deletion=True
        )  # explicitly wait for deletion, the context manager will not wait for deletion

    # after the context manager exits, the job should be deleted
    with KubernetesSessionManager() as session_manager:
        # check that the job was deleted
        result = session_manager._get_job_status(mcp_server.pod_name)
        assert result is None


@pytest.mark.integration
def test_session_manager_start_mcp_server_git():
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/modelcontextprotocol/servers/tree/main/src/git)
    """
    with KubernetesSessionManager() as session_manager:
        mcp_server = session_manager.create_mcp_server(GIT, wait_for_ready=True)
        assert mcp_server is not None
        # check that the job was created successfully
        status = session_manager._get_job_status(mcp_server.pod_name)
        assert status is not None
        assert status.status.active == 1
        assert status.status.succeeded is None
        assert status.status.failed is None


@pytest.mark.integration
def test_session_manager_start_mcp_server_fetch_expose_port():
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch)
    """
    with KubernetesSessionManager() as session_manager:
        mcp_server = session_manager.create_mcp_server(FETCH)
        try:
            session_manager.expose_mcp_server_port(mcp_server)
        finally:
            session_manager.remove_mcp_server_port(mcp_server)


@pytest.mark.integration
def test_session_manager_start_mcp_server_github():
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/github/github-mcp-server)
    """
    with KubernetesSessionManager() as session_manager:
        mcp_server = session_manager.create_mcp_server(GITHUB, wait_for_ready=True)
        assert mcp_server is not None
        # check that the job was created successfully
        status = session_manager._get_job_status(mcp_server.pod_name)
        assert status is not None
        assert status.status.active == 1
        assert status.status.succeeded is None
        assert status.status.failed is None


@pytest.mark.integration
def test_session_manager_start_mcp_server_gitlab():
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/zereight/mcp-gitlab)
    """
    with KubernetesSessionManager() as session_manager:
        mcp_server = session_manager.create_mcp_server(GITLAB, wait_for_ready=True)
        assert mcp_server is not None
        # check that the job was created successfully
        status = session_manager._get_job_status(mcp_server.pod_name)
        assert status is not None
        assert status.status.active == 1
        assert status.status.succeeded is None
        assert status.status.failed is None


@pytest.mark.integration
def test_session_manager_start_mcp_server_aws_kb_retrieval():
    """Test that the MCP server is started and the runtime is invokable.
    [MCP Source](https://github.com/awslabs/mcp/tree/main/src/bedrock-kb-retrieval-mcp-server)
    """
    with KubernetesSessionManager() as session_manager:
        mcp_server = session_manager.create_mcp_server(BEDROCK_KB_RETRIEVAL, wait_for_ready=True)
        assert mcp_server is not None
        # check that the job was created successfully
        status = session_manager._get_job_status(mcp_server.pod_name)
        assert status is not None
        assert status.status.active == 1
        assert status.status.succeeded is None
        assert status.status.failed is None
