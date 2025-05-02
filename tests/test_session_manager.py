import pytest

from mcp_ephemeral_k8s.exceptions import MCPJobNotFoundError
from mcp_ephemeral_k8s.model import ephemeralMcpServerConfig
from mcp_ephemeral_k8s.session_manager import KubernetesSessionManager


def test_session_manager_creation_no_context_manager():
    session_manager = KubernetesSessionManager()
    assert session_manager is not None
    assert session_manager._api_client is None
    assert session_manager._batch_v1 is None
    assert session_manager._core_v1 is None


def test_session_manager_creation_with_context_manager():
    with KubernetesSessionManager() as session_manager:
        assert session_manager is not None
        assert session_manager._api_client is not None
        assert session_manager._batch_v1 is not None
        assert session_manager._core_v1 is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_session_manager_creation_with_context_manager_async():
    async with KubernetesSessionManager() as session_manager:
        assert session_manager is not None
        assert session_manager._api_client is not None
        assert session_manager._batch_v1 is not None
        assert session_manager._core_v1 is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_session_manager_start_mcp_server_default_values():
    with KubernetesSessionManager() as session_manager:
        config = ephemeralMcpServerConfig()
        mcp_server = await session_manager.start_mcp_server(config)
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

    # after the context manager exits, the job should be deleted
    with KubernetesSessionManager() as session_manager, pytest.raises(MCPJobNotFoundError):
        # check that the job was deleted
        result = session_manager.get_job_status(mcp_server.pod_name)
        assert result is None
