"""FastAPI application for the MCP ephemeral server."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from mcp_ephemeral_k8s.api.crud import CreateMcpServerRequest, DeleteMcpServerRequest, ListMcpServersResponse
from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer, EphemeralMcpServerConfig
from mcp_ephemeral_k8s.api.exceptions import MCPJobNotFoundError
from mcp_ephemeral_k8s.session_manager import KubernetesSessionManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Lifecycle hooks for the MCP ephemeral server.
    """
    with KubernetesSessionManager() as session_manager:
        app.state.session_manager = session_manager
        yield
    # the session manager will be deleted when the context manager is exited
    del app.state.session_manager


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello, World!"}


@app.get("/list_mcp_servers")
async def list_mcp_servers() -> ListMcpServersResponse:
    manager: KubernetesSessionManager = app.state.session_manager
    return ListMcpServersResponse(servers=list(manager.jobs.values()))


@app.post("/create_mcp_server")
async def create_mcp_server(request: CreateMcpServerRequest) -> EphemeralMcpServer:
    config = EphemeralMcpServerConfig(
        runtime_exec=request.runtime_exec, runtime_mcp=request.runtime_mcp, env=request.env
    )
    manager: KubernetesSessionManager = app.state.session_manager
    return manager.create_mcp_server(config=config, wait_for_ready=False)


@app.post("/delete_mcp_server")
async def delete_mcp_server(request: DeleteMcpServerRequest) -> EphemeralMcpServer:
    manager: KubernetesSessionManager = app.state.session_manager
    try:
        return manager.delete_mcp_server(request.pod_name, wait_for_deletion=False)
    except MCPJobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
