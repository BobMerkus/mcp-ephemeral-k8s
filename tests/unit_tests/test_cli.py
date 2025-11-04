"""Unit tests for CLI module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp_ephemeral_k8s.cli import Init, McpEphemeralK8s, Serve, cli


def test_init_default_path():
    """Test Init with default path."""
    init = Init()
    assert isinstance(init.path, Path)


def test_init_custom_path():
    """Test Init with custom path."""
    custom_path = Path("/custom/path")
    init = Init(path=custom_path)
    assert init.path == custom_path


def test_init_cli_cmd():
    """Test Init.cli_cmd logs the initialization message."""
    init = Init(path=Path("/test/path"))

    with patch("mcp_ephemeral_k8s.cli.logger") as mock_logger:
        init.cli_cmd()
        mock_logger.info.assert_called_once_with('Initializing MCP ephemeral K8s in path "/test/path"')


def test_serve_defaults():
    """Test Serve with default values."""
    serve = Serve()
    assert serve.transport == "sse"
    assert serve.namespace == "default"
    assert serve.allow_origins == ["*"]
    assert serve.show_banner is True
    assert serve.host == "127.0.0.1"
    assert serve.port == 8000


def test_serve_custom_values():
    """Test Serve with custom values."""
    serve = Serve(
        transport="stdio",
        namespace="custom-namespace",
        allow_origins=["http://localhost:3000"],
        show_banner=False,
        host="0.0.0.0",  # noqa: S104
        port=9000,
    )
    assert serve.transport == "stdio"
    assert serve.namespace == "custom-namespace"
    assert serve.allow_origins == ["http://localhost:3000"]
    assert serve.show_banner is False
    assert serve.host == "0.0.0.0"  # noqa: S104
    assert serve.port == 9000


def test_serve_cli_cmd():
    """Test Serve.cli_cmd calls main with correct arguments."""
    serve = Serve(
        transport="sse",
        namespace="test-namespace",
        allow_origins=["http://example.com"],
        show_banner=False,
        host="0.0.0.0",  # noqa: S104
        port=9000,
    )

    with patch("mcp_ephemeral_k8s.cli.main") as mock_main, patch("mcp_ephemeral_k8s.cli.logger") as mock_logger:
        serve.cli_cmd()

        mock_logger.info.assert_called_once_with(
            'Serving MCP ephemeral K8s in namespace "test-namespace" on 0.0.0.0:9000'
        )
        mock_main.assert_called_once_with(
            transport="sse",
            allow_origins=["http://example.com"],
            show_banner=False,
            host="0.0.0.0",  # noqa: S104
            port=9000,
        )


def test_mcp_ephemeral_k8s_cli_cmd():
    """Test McpEphemeralK8s.cli_cmd runs subcommand."""
    # Need to provide both init and serve as they are required fields
    mcp = McpEphemeralK8s(init=Init(), serve=Serve())

    with patch("mcp_ephemeral_k8s.cli.CliApp.run_subcommand") as mock_run_subcommand:
        mcp.cli_cmd()
        mock_run_subcommand.assert_called_once_with(mcp)


def test_cli_no_args():
    """Test cli() with no arguments defaults to 'serve'."""
    with (
        patch("sys.argv", ["mcp-ephemeral-k8s"]),
        patch("mcp_ephemeral_k8s.cli.CliApp.run") as mock_run,
        patch("mcp_ephemeral_k8s.cli.logger") as mock_logger,
    ):
        # Mock the return value
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"serve": {"transport": "sse"}}
        mock_run.return_value = mock_result

        cli()

        # Verify it logged the error about no subcommand
        mock_logger.error.assert_called_once_with("No subcommand provided, defaulting to 'serve'")

        # Verify it ran with 'serve' as the default
        mock_run.assert_called_once_with(McpEphemeralK8s, cli_args=["serve"])

        # Verify it logged the result
        mock_logger.info.assert_called_once()


def test_cli_with_serve_subcommand():
    """Test cli() with serve subcommand."""
    with (
        patch("sys.argv", ["mcp-ephemeral-k8s", "serve", "--namespace", "custom"]),
        patch("mcp_ephemeral_k8s.cli.CliApp.run") as mock_run,
        patch("mcp_ephemeral_k8s.cli.logger") as mock_logger,
    ):
        # Mock the return value
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"serve": {"namespace": "custom"}}
        mock_run.return_value = mock_result

        cli()

        # Verify it did not log error (no default fallback needed)
        mock_logger.error.assert_not_called()

        # Verify it ran with correct args
        mock_run.assert_called_once_with(McpEphemeralK8s, cli_args=["serve", "--namespace", "custom"])

        # Verify it logged the result
        mock_logger.info.assert_called_once()


def test_cli_with_init_subcommand():
    """Test cli() with init subcommand."""
    with (
        patch("sys.argv", ["mcp-ephemeral-k8s", "init", "/custom/path"]),
        patch("mcp_ephemeral_k8s.cli.CliApp.run") as mock_run,
        patch("mcp_ephemeral_k8s.cli.logger") as mock_logger,
    ):
        # Mock the return value
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"init": {"path": "/custom/path"}}
        mock_run.return_value = mock_result

        cli()

        # Verify it did not log error
        mock_logger.error.assert_not_called()

        # Verify it ran with correct args
        mock_run.assert_called_once_with(McpEphemeralK8s, cli_args=["init", "/custom/path"])

        # Verify it logged the result
        mock_logger.info.assert_called_once()
