"""MCP server application, meant to be used as an MCP server that can spawn other MCP servers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import Context, FastMCP
from kubernetes import client

from mcp_ephemeral_k8s import KubernetesSessionManager, __version__, presets
from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer, EphemeralMcpServerConfig


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[KubernetesSessionManager]:
    """
    Lifecycle hooks for the MCP ephemeral server.
    """
    with KubernetesSessionManager(namespace="default", jobs={}, sleep_time=1, max_wait_time=60) as session_manager:
        yield session_manager


mcp = FastMCP(name="mcp-ephemeral-k8s", lifespan=lifespan)


# Static resource
@mcp.resource("config://version")
def get_version() -> str:
    """Get the version of the MCP ephemeral server."""
    return __version__


# Preset configurations
@mcp.resource("config://presets")
def list_presets() -> list[EphemeralMcpServerConfig]:
    """List all preset configurations."""
    return [presets.FETCH, presets.GITHUB, presets.GITLAB, presets.GIT, presets.TIME, presets.BEDROCK_KB_RETRIEVAL]


@mcp.tool("list_mcp_servers")
def list_mcp_servers(ctx: Context) -> list[EphemeralMcpServer]:
    """List all running MCP servers."""
    session_manager: KubernetesSessionManager = ctx.request_context.lifespan_context
    return list(session_manager.jobs.values())


@mcp.tool("create_mcp_server")
def create_mcp_server(
    ctx: Context,
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
    session_manager: KubernetesSessionManager = ctx.request_context.lifespan_context
    return session_manager.create_mcp_server(config, wait_for_ready=wait_for_ready)


@mcp.tool("delete_mcp_server")
def delete_mcp_server(ctx: Context, pod_name: str, wait_for_deletion: bool = True) -> EphemeralMcpServer:
    """Delete an MCP server.

    Args:
        pod_name: The name of the MCP server to delete.
        wait_for_deletion: Whether to wait for the MCP server to be deleted before returning.
    """
    session_manager: KubernetesSessionManager = ctx.request_context.lifespan_context
    return session_manager.delete_mcp_server(pod_name, wait_for_deletion=wait_for_deletion)


@mcp.tool("get_mcp_server_status")
def get_mcp_server_status(ctx: Context, pod_name: str) -> client.V1Job | None:
    """Get the status of an MCP server.

    Args:
        pod_name: The name of the MCP server to get the status of.
    """
    session_manager: KubernetesSessionManager = ctx.request_context.lifespan_context
    return session_manager._get_job_status(pod_name)


def main() -> None:
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
