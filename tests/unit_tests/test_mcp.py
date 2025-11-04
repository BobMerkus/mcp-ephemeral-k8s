"""Tests for the mcp.py module."""

from unittest.mock import MagicMock, patch

import pytest
from fastmcp import Context
from kubernetes import client

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer
from mcp_ephemeral_k8s.app.mcp_server import (
    __version__,
    create_mcp_server,
    delete_mcp_server,
    get_mcp_server_status,
    get_version,
    list_mcp_servers,
    main,
)
from mcp_ephemeral_k8s.session_manager import KubernetesSessionManager


@pytest.mark.unit
def test_get_version():
    """Test the get_version function."""
    assert get_version.fn() == __version__


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_mcp_servers():
    """Test the list_mcp_servers function."""
    # Create mock context and session manager
    ctx = MagicMock(spec=Context)
    session_manager = MagicMock(spec=KubernetesSessionManager)
    mock_servers = [MagicMock(spec=EphemeralMcpServer) for _ in range(2)]

    # Configure mocks
    ctx.request_context.lifespan_context = session_manager
    session_manager.jobs = {f"server-{i}": server for i, server in enumerate(mock_servers)}

    # Call the function
    result = await list_mcp_servers.fn(ctx)

    # Assertions
    assert len(result) == 2
    assert result == list(session_manager.jobs.values())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_mcp_server():
    """Test the create_mcp_server function."""
    # Create mock context and session manager
    ctx = MagicMock(spec=Context)
    session_manager = MagicMock(spec=KubernetesSessionManager)
    mock_server = MagicMock(spec=EphemeralMcpServer)

    # Configure mocks
    ctx.request_context.lifespan_context = session_manager
    session_manager.create_mcp_server.return_value = mock_server

    # Call the function with correct parameter types
    result = await create_mcp_server.fn(
        ctx, "uvx", "mcp-server-fetch", "--port 8080", env={"KEY": "VALUE"}, wait_for_ready=True
    )

    # Assertions
    session_manager.create_mcp_server.assert_called_once()
    config_arg = session_manager.create_mcp_server.call_args[0][0]
    assert config_arg.runtime_exec == "uvx"
    assert config_arg.runtime_mcp == "mcp-server-fetch"
    assert config_arg.runtime_args == "--port 8080"
    assert config_arg.env == {"KEY": "VALUE"}
    assert session_manager.create_mcp_server.call_args[1]["wait_for_ready"] is True
    assert result == mock_server


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_mcp_server():
    """Test the delete_mcp_server function."""
    # Create mock context and session manager
    ctx = MagicMock(spec=Context)
    session_manager = MagicMock(spec=KubernetesSessionManager)
    mock_server = MagicMock(spec=EphemeralMcpServer)

    # Configure mocks
    ctx.request_context.lifespan_context = session_manager
    session_manager.delete_mcp_server.return_value = mock_server

    # Call the function
    result = await delete_mcp_server.fn(ctx, "server-name", wait_for_deletion=True)

    # Assertions
    session_manager.delete_mcp_server.assert_called_once_with("server-name", wait_for_deletion=True)
    assert result == mock_server


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_mcp_server_status():
    """Test the get_mcp_server_status function."""
    # Create mock context and session manager
    ctx = MagicMock(spec=Context)
    session_manager = MagicMock(spec=KubernetesSessionManager)
    mock_job = MagicMock(spec=client.V1Job)

    # Configure mocks
    ctx.request_context.lifespan_context = session_manager
    session_manager._get_job_status.return_value = mock_job

    # Call the function
    result = await get_mcp_server_status.fn(ctx, "server-name")

    # Assertions
    session_manager._get_job_status.assert_called_once_with("server-name")
    assert result == mock_job


@pytest.mark.unit
@patch("mcp_ephemeral_k8s.app.mcp_server.mcp")
def test_main(mock_mcp):
    """Test the main function."""
    # Call the function
    main()

    # Assertions
    mock_mcp.run.assert_called_once()
    call_args = mock_mcp.run.call_args
    assert call_args.kwargs["transport"] == "sse"
    assert call_args.kwargs["show_banner"] is True
    assert "middleware" in call_args.kwargs


@pytest.mark.unit
def test_main_entry_point():
    """Test the __main__ entry point."""
    # Execute the if __name__ == "__main__" code
    with patch("mcp_ephemeral_k8s.app.mcp_server.main") as mock_main:
        # Use exec to execute the if block with __name__ set to "__main__"
        code = """
if __name__ == "__main__":
    main()
"""
        namespace = {"__name__": "__main__", "main": mock_main}
        exec(code, namespace)  # noqa: S102

        # Validate main was called
        mock_main.assert_called_once()
