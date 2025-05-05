"""MCP server application, meant to be used as an MCP server that can spawn other MCP servers."""

from mcp.server.fastmcp import FastMCP

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer, EphemeralMcpServerConfig
from mcp_ephemeral_k8s.session_manager import KubernetesSessionManager

mcp = FastMCP("mcp-ephemeral-k8s")
session_manager = KubernetesSessionManager(namespace="default", jobs={})


@mcp.tool("list_mcp_servers")
def list_mcp_servers() -> list[EphemeralMcpServer]:
    """List all running MCP servers."""
    return list(session_manager.jobs.values())


@mcp.tool("create_mcp_server")
def create_mcp_server(
    runtime_exec: str,
    runtime_mcp: str,
    env: dict[str, str] | None = None,
    wait_for_ready: bool = True,
) -> EphemeralMcpServer:
    """Create a new MCP server.

    Args:
        runtime_exec: The runtime to use for the MCP server (e.g. "uvx", "npx", "go run").
        runtime_mcp: The runtime to use for the MCP server (e.g. "mcp-server-fetch").
        env: The environment variables to set for the MCP server.
        wait_for_ready: Whether to wait for the MCP server to be ready before returning.
    """
    config = EphemeralMcpServerConfig(runtime_exec=runtime_exec, runtime_mcp=runtime_mcp, env=env)
    return session_manager.create_mcp_server(config, wait_for_ready=wait_for_ready)


@mcp.tool("delete_mcp_server")
def delete_mcp_server(name: str, wait_for_deletion: bool = True) -> EphemeralMcpServer:
    """Delete an MCP server.

    Args:
        name: The name of the MCP server to delete.
        wait_for_deletion: Whether to wait for the MCP server to be deleted before returning.
    """
    return session_manager.delete_mcp_server(name, wait_for_deletion=wait_for_deletion)


def main() -> None:
    with session_manager:
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
