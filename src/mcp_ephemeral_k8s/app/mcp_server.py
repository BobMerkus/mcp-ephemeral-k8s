"""MCP server application, meant to be used as an MCP server that can spawn other MCP servers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.server.server import Transport
from kubernetes import client
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from mcp_ephemeral_k8s import KubernetesSessionManager, __version__, presets
from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer, EphemeralMcpServerConfig


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[KubernetesSessionManager]:
    """
    Lifecycle hooks for the MCP ephemeral server.
    """
    async with KubernetesSessionManager(
        namespace="default", jobs={}, sleep_time=1, max_wait_time=60
    ) as session_manager:
        yield session_manager


mcp = FastMCP(
    name="mcp-ephemeral-k8s",
    version=__version__,
    instructions=(
        "This MCP server provides tools for dynamically creating and managing ephemeral "
        "MCP (Model Context Protocol) servers in Kubernetes. It allows you to spawn "
        "isolated MCP server instances on-demand, manage their lifecycle, and clean them up "
        "when no longer needed. Each ephemeral server runs in its own Kubernetes Job and can "
        "be configured with custom runtime environments, executables, and MCP packages."
    ),
    lifespan=lifespan,
)


# Static resource
@mcp.resource("config://version")
def get_version() -> str:
    """Get the version of the MCP ephemeral server."""
    return __version__


# Preset configurations
@mcp.tool("list_presets")
def list_presets() -> list[EphemeralMcpServerConfig]:
    """
    List all available preset MCP server configurations.

    Returns a list of pre-configured MCP server templates that can be used as examples
    or starting points for creating new ephemeral MCP servers. Each preset includes
    the runtime executor (e.g., 'uvx', 'npx'), the MCP package to install, optional
    runtime arguments, and environment variables.

    Returns:
        A list of EphemeralMcpServerConfig objects containing preset configurations.
        Each config specifies how to run a specific MCP server package.

    Example usage:
        Use this to discover available MCP server configurations before creating one.
    """
    return presets.EXAMPLE_MCP_SERVER_CONFIGS


@mcp.tool("list_mcp_servers")
async def list_mcp_servers(ctx: Context) -> list[EphemeralMcpServer]:
    """
    List all currently running ephemeral MCP servers.

    Retrieves information about all MCP server instances that are currently managed
    by this controller. Each server entry includes its pod name, configuration details,
    current status, creation timestamp, and connection information if available.

    Returns:
        A list of EphemeralMcpServer objects representing all active MCP servers.
        Each object contains the server's configuration, runtime status, and metadata.

    Example usage:
        Call this tool to see what MCP servers are currently running before creating
        new ones or to check the status of existing servers.
    """
    session_manager: KubernetesSessionManager = ctx.request_context.lifespan_context
    return list(session_manager.jobs.values())


@mcp.tool("create_mcp_server")
async def create_mcp_server(
    ctx: Context,
    runtime_exec: str,
    runtime_mcp: str,
    runtime_args: str = "",
    env: dict[str, str] | None = None,
    wait_for_ready: bool = False,
) -> EphemeralMcpServer:
    """
    Create a new ephemeral MCP server in Kubernetes.

    Spawns a new MCP server instance as a Kubernetes Job with the specified configuration.
    The server runs in an isolated environment and can be customized with different
    runtime executors, packages, arguments, and environment variables.

    Args:
        runtime_exec: The executor to use for running the MCP server (e.g., 'uvx' for
            Python packages, 'npx' for Node.js packages, 'docker' for container images).
        runtime_mcp: The MCP package or image to run (e.g., 'mcp-server-sqlite' for a
            Python-based SQLite MCP server, or '@modelcontextprotocol/server-filesystem'
            for a Node.js filesystem server).
        runtime_args: Optional arguments to pass to the MCP server at runtime. These are
            appended to the command line when starting the server.
        env: Optional dictionary of environment variables to set in the server's container.
            Useful for configuration, authentication tokens, or feature flags.
        wait_for_ready: If True, this call will block until the Kubernetes Job is in a
            ready state. If False, returns immediately after submitting the Job.

    Returns:
        An EphemeralMcpServer object containing the created server's configuration,
        pod name, status, and connection details.

    Example usage:
        To create a filesystem MCP server: create_mcp_server(
            runtime_exec='npx',
            runtime_mcp='@modelcontextprotocol/server-filesystem',
            runtime_args='/tmp',
            wait_for_ready=True
        )
    """
    config = EphemeralMcpServerConfig(
        runtime_exec=runtime_exec,
        runtime_mcp=runtime_mcp,
        runtime_args=runtime_args,
        env=env,
    )
    session_manager: KubernetesSessionManager = ctx.request_context.lifespan_context
    return await session_manager.create_mcp_server(config, wait_for_ready=wait_for_ready, expose_port=True)


@mcp.tool("delete_mcp_server")
async def delete_mcp_server(ctx: Context, job_name: str, wait_for_deletion: bool = False) -> EphemeralMcpServer:
    """
    Delete an ephemeral MCP server and clean up its resources.

    Terminates a running MCP server instance and removes its associated Kubernetes
    resources including the Job, Pod, and any exposed Services. This is important
    for cleaning up resources when an MCP server is no longer needed.

    Args:
        job_name: The name of the pod/server to delete. This is returned when creating
            a server and can be retrieved using list_mcp_servers().
        wait_for_deletion: If True, this call will block until the Kubernetes resources
            are fully deleted and removed from the cluster. If False, initiates deletion
            and returns immediately.

    Returns:
        An EphemeralMcpServer object containing the deleted server's final state and
        metadata before removal.

    Example usage:
        After retrieving the list of servers, delete a specific one by its pod name:
        delete_mcp_server(job_name='mcp-server-xyz123', wait_for_deletion=True)
    """
    session_manager: KubernetesSessionManager = ctx.request_context.lifespan_context
    return await session_manager.delete_mcp_server(job_name, wait_for_deletion=wait_for_deletion)


@mcp.tool("get_mcp_server_status")
async def get_mcp_server_status(ctx: Context, job_name: str) -> client.V1Job | None:
    """
    Get the detailed Kubernetes status of an MCP server.

    Retrieves the underlying Kubernetes Job status for a specific MCP server instance.
    This provides low-level details about the Job's execution state, including
    conditions, start/completion times, and any failure information.

    Args:
        job_name: The name of the pod/server to check. This identifier is returned
            when creating a server and can be retrieved using list_mcp_servers().

    Returns:
        A Kubernetes V1Job object containing the Job's complete status information,
        or None if the Job is not found. The Job status includes fields such as:
        - active: number of active pods
        - succeeded: number of succeeded pods
        - failed: number of failed pods
        - conditions: detailed state information
        - start_time and completion_time

    Example usage:
        Use this to debug issues with a server or to check if a Job has completed
        successfully: get_mcp_server_status(job_name='mcp-server-xyz123')
    """
    session_manager: KubernetesSessionManager = ctx.request_context.lifespan_context
    return await session_manager._get_job_status(job_name)


@mcp.tool("mount_mcp_server")
async def mount_mcp_server(ctx: Context, job_name: str, name: str | None = None) -> EphemeralMcpServer:
    """Mount a remote MCP server over SSE.

    Args:
        job_name: The name of the pod that is running the remote MCP server.
        name: The name of the proxy server.
    """
    session_manager: KubernetesSessionManager = ctx.request_context.lifespan_context
    server, ephemeral_server = await session_manager.mount_mcp_server(job_name)
    mcp.mount(server=server, prefix=name, as_proxy=True)
    return ephemeral_server


@mcp.tool("remove_mcp_server_mount")
async def remove_mcp_server_mount(name: str | None = None) -> None:
    """Remove the mount of an MCP server.

    Args:
        name: The name of the server to remove. If None, all mounted servers with a prefix will be removed.
    """
    # Collect servers to remove first to avoid index shifting issues
    servers_to_remove = [
        mounted_server
        for mounted_server in mcp._mounted_servers
        if mounted_server.prefix == name or (name is None and mounted_server.prefix is not None)
    ]

    if not servers_to_remove:
        msg = f"No mounted server found with name {name}" if name is not None else "No mounted servers found"
        raise ValueError(msg)

    # Remove servers from the list
    for server in servers_to_remove:
        mcp._mounted_servers.remove(server)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check endpoint for the MCP server."""
    return PlainTextResponse("OK", status_code=200)


def main(
    transport: Transport = "sse",
    show_banner: bool = True,
    allow_origins: list[str] | None = None,
    **transport_kwargs: Any,
) -> None:
    """Run the FastMCP server."""
    # Configure CORS middleware for SSE transport to support browser-based clients
    if transport == "sse":
        cors_middleware = [
            (
                CORSMiddleware,
                (),
                {
                    "allow_origins": allow_origins or ["*"],
                    "allow_credentials": True,
                    "allow_methods": ["*"],
                    "allow_headers": ["*"],
                },
            )
        ]
        transport_kwargs.setdefault("middleware", cors_middleware)

    mcp.run(transport=transport, show_banner=show_banner, **transport_kwargs)


if __name__ == "__main__":
    main()
