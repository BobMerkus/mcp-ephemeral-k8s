import pytest

from mcp_ephemeral_k8s import KubernetesRuntime, KubernetesSessionManager
from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServerConfig
from mcp_ephemeral_k8s.api.exceptions import MCPNamespaceNotFoundError
from mcp_ephemeral_k8s.integrations.presets import EXAMPLE_MCP_SERVER_CONFIGS


@pytest.fixture
async def session_manager():
    async with KubernetesSessionManager(
        namespace="default",
        runtime=KubernetesRuntime.KUBECONFIG,
        jobs={},
        sleep_time=1,
        max_wait_time=120,  # 2 minutes timeout for the job to be ready
    ) as manager:
        yield manager


@pytest.mark.integration
@pytest.mark.asyncio
async def test_creation_no_context_manager():
    session_manager = KubernetesSessionManager()
    assert session_manager is not None
    assert not hasattr(session_manager, "_api_client")
    assert not hasattr(session_manager, "_batch_v1")
    assert not hasattr(session_manager, "_core_v1")
    assert not hasattr(session_manager, "_rbac_v1")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_creation_with_valid_namespace():
    async with KubernetesSessionManager(namespace="default"):
        pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_namespace():
    with pytest.raises(MCPNamespaceNotFoundError):
        async with KubernetesSessionManager(namespace="invalid-namespace"):
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_attributes(session_manager: KubernetesSessionManager):
    """Test that the session manager has the expected attributes."""
    assert session_manager is not None
    assert hasattr(session_manager, "_api_client")
    assert hasattr(session_manager, "_batch_v1")
    assert hasattr(session_manager, "_core_v1")
    assert hasattr(session_manager, "_rbac_v1")


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("preset", EXAMPLE_MCP_SERVER_CONFIGS)
async def test_start_mcp_server(session_manager: KubernetesSessionManager, preset: EphemeralMcpServerConfig):
    """Test that the MCP server for time is started correctly."""
    mcp_server = await session_manager.create_mcp_server(preset, wait_for_ready=True)
    assert mcp_server is not None
    assert mcp_server.job_name is not None
    # Cleanup after test
    await session_manager.delete_mcp_server(mcp_server.job_name, wait_for_deletion=True)
