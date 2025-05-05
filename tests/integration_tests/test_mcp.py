from pathlib import Path

import pytest
from fastmcp import Client
from mcp.types import TextContent

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer

mcp_file_path = Path(__file__).parent.parent.parent / "src" / "mcp_ephemeral_k8s" / "app" / "mcp.py"


@pytest.mark.integration
def test_mcp_file_exists():
    assert mcp_file_path.exists()


@pytest.fixture
def mcp_server():
    from mcp_ephemeral_k8s.app.mcp import mcp

    return mcp


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_tool_functionality(mcp_server):
    # Pass the server directly to the Client constructor
    async with Client(mcp_server) as client:
        result = await client.call_tool("list_mcp_servers")
        assert result is not None
        assert len(result) == 0

        result = await client.call_tool(
            "create_mcp_server",
            {"runtime_exec": "uvx", "runtime_mcp": "mcp-server-fetch", "env": {"MCP_SERVER_PORT": "8080"}},
        )
        assert result is not None
        data: TextContent = result[0]
        body = EphemeralMcpServer.model_validate_json(data.text)
        assert body.pod_name.startswith("mcp-ephemeral-k8s-proxy")
        assert body.config.runtime_exec == "uvx"
        assert body.config.runtime_mcp == "mcp-server-fetch"
        assert body.config.env == {"MCP_SERVER_PORT": "8080"}

        result = await client.call_tool("delete_mcp_server", {"name": body.pod_name})
        assert result is not None
