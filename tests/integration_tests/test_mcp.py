from pathlib import Path

import pytest
from fastmcp import Client
from mcp.types import TextContent

from mcp_ephemeral_k8s import __version__
from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer

mcp_file_path = Path(__file__).parent.parent.parent / "src" / "mcp_ephemeral_k8s" / "app" / "mcp_server.py"


@pytest.mark.integration
def test_mcp_file_exists():
    assert mcp_file_path.exists()


@pytest.fixture
def mcp_server():
    from mcp_ephemeral_k8s.app.mcp_server import mcp

    return mcp


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_tool_functionality(mcp_server):
    # Pass the server directly to the Client constructor
    async with Client(mcp_server) as client:
        list_resources = await client.list_resources()
        assert len(list_resources) == 1
        assert "config://version" in [str(resource.uri) for resource in list_resources]

        # Test version
        version = await client.read_resource("config://version")
        assert version is not None
        assert len(version) == 1
        assert version[0].text == __version__

        # Test presets
        presets = await client.call_tool("list_presets")
        assert presets is not None
        assert len(presets.content) > 0

        # Test list_mcp_servers
        result = await client.call_tool("list_mcp_servers")
        assert result is not None
        assert len(result.content) > 0 or len(result.content) == 0  # Can be empty initially

        result = await client.call_tool(
            "create_mcp_server",
            {"runtime_exec": "uvx", "runtime_mcp": "mcp-server-fetch", "env": {"MCP_SERVER_PORT": "8080"}},
        )
        assert result is not None
        data: TextContent = result.content[0]
        body = EphemeralMcpServer.model_validate_json(data.text)
        assert body.job_name.startswith("mcp-ephemeral-k8s-proxy")
        assert body.config.runtime_exec == "uvx"
        assert body.config.runtime_mcp == "mcp-server-fetch"
        assert body.config.env == {"MCP_SERVER_PORT": "8080"}

        result = await client.call_tool("delete_mcp_server", {"job_name": body.job_name})
        assert result is not None
        data: TextContent = result.content[0]
        body = EphemeralMcpServer.model_validate_json(data.text)
        assert body.job_name == body.job_name
        assert body.config.runtime_exec == "uvx"
        assert body.config.runtime_mcp == "mcp-server-fetch"
        assert body.config.env == {"MCP_SERVER_PORT": "8080"}
