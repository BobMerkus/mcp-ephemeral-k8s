from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mcp_ephemeral_k8s.session_manager import KubernetesSessionManager


@asynccontextmanager
async def lifecycle(app: FastAPI) -> AsyncIterator[None]:
    """
    Lifecycle hooks for the MCP ephemeral server.
    """
    with KubernetesSessionManager() as session_manager:
        app.state.session_manager = session_manager
        yield
    # the session manager will be deleted when the context manager is exited
    del app.state.session_manager


__all__ = ["lifecycle"]
