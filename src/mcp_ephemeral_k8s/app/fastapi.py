"""FastAPI application for the MCP ephemeral server."""

from fastapi import FastAPI

from mcp_ephemeral_k8s.api.model import EphemeralMcpServer, EphemeralMcpServerConfig
from mcp_ephemeral_k8s.app.lifecycle import lifecycle
from mcp_ephemeral_k8s.session_manager import KubernetesSessionManager

app = FastAPI(lifespan=lifecycle)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.get("/list_mcp_servers")
async def list_mcp_servers() -> list[EphemeralMcpServer]:
    manager: KubernetesSessionManager = app.state.session_manager
    return list(manager.jobs.values())


@app.post("/create_mcp_server")
async def create_mcp_server(runtime_exec: str, runtime_mcp: str, env: dict[str, str]) -> EphemeralMcpServer:
    config = EphemeralMcpServerConfig(runtime_exec=runtime_exec, runtime_mcp=runtime_mcp, env=env)
    manager: KubernetesSessionManager = app.state.session_manager
    return manager.create_mcp_server(config)


@app.post("/delete_mcp_server")
async def delete_mcp_server(name: str) -> EphemeralMcpServer:
    manager: KubernetesSessionManager = app.state.session_manager
    return manager.delete_mcp_server(name)
