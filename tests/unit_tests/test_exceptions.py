"""Unit tests for exception classes."""

from mcp_ephemeral_k8s.api.exceptions import (
    InvalidKubeConfigError,
    MCPInvalidRuntimeError,
    MCPJobError,
    MCPJobNotFoundError,
    MCPJobTimeoutError,
    MCPNamespaceNotFoundError,
    MCPPortForwardError,
    MCPServerCreationError,
)


def test_invalid_kube_config_error():
    """Test InvalidKubeConfigError exception."""
    error = InvalidKubeConfigError("test message")
    assert error.message == "Invalid kube config: test message"
    assert str(error) == "Invalid kube config: test message"


def test_mcp_port_forward_error():
    """Test MCPPortForwardError exception."""
    error = MCPPortForwardError("test-job", "test-namespace", 8080)
    expected = "Failed to create port forward: job_name='test-job' namespace='test-namespace' port=8080"
    assert error.message == expected
    assert str(error) == expected


def test_mcp_server_creation_error():
    """Test MCPServerCreationError exception."""
    error = MCPServerCreationError("test message")
    assert error.message == "Failed to create MCP server: test message"
    assert str(error) == "Failed to create MCP server: test message"


def test_mcp_job_not_found_error():
    """Test MCPJobNotFoundError exception."""
    error = MCPJobNotFoundError("test-namespace", "test-job")
    expected = "Failed to find MCP job: namespace='test-namespace' job_name='test-job'"
    assert error.message == expected
    assert str(error) == expected


def test_mcp_invalid_runtime_error():
    """Test MCPInvalidRuntimeError exception."""
    error = MCPInvalidRuntimeError("python", "uvx", "both cannot be set")
    expected = "Invalid runtime: runtime_exec='python' and runtime_mcp='uvx' both cannot be set"
    assert str(error) == expected


def test_mcp_invalid_runtime_error_with_none():
    """Test MCPInvalidRuntimeError with None values."""
    error = MCPInvalidRuntimeError(None, None, "at least one must be set")
    expected = "Invalid runtime: runtime_exec=None and runtime_mcp=None at least one must be set"
    assert str(error) == expected


def test_mcp_namespace_not_found_error():
    """Test MCPNamespaceNotFoundError exception."""
    error = MCPNamespaceNotFoundError("test-namespace")
    assert error.message == "Namespace not found: test-namespace"
    assert str(error) == "Namespace not found: test-namespace"


def test_mcp_job_timeout_error():
    """Test MCPJobTimeoutError exception."""
    error = MCPJobTimeoutError("test-namespace", "test-job")
    expected = "MCP job timed out: namespace='test-namespace' job_name='test-job'"
    assert error.message == expected
    assert str(error) == expected


def test_mcp_job_error():
    """Test MCPJobError exception."""
    error = MCPJobError("test-namespace", "test-job", "pod failed")
    expected = "MCP job error: namespace='test-namespace' job_name='test-job' - pod failed"
    assert error.message == expected
    assert str(error) == expected
