"""
This module contains the exceptions for the MCP ephemeral K8s library.
"""


class InvalidKubeConfigError(Exception):
    """Exception raised when the kube config is invalid."""

    def __init__(self, message: str):
        self.message = f"Invalid kube config: {message}"
        super().__init__(self.message)


class MCPPortForwardError(Exception):
    """Exception raised when the MCP port forward fails."""

    def __init__(self, job_name: str, namespace: str, port: int):
        self.message = f"Failed to create port forward: {job_name=} {namespace=} {port=}"
        super().__init__(self.message)


class MCPServerCreationError(Exception):
    """Exception raised when the MCP server creation fails."""

    def __init__(self, message: str):
        self.message = f"Failed to create MCP server: {message}"
        super().__init__(self.message)


class MCPJobNotFoundError(Exception):
    """Exception raised when the MCP job is not found."""

    def __init__(self, namespace: str, job_name: str):
        self.message = f"Failed to find MCP job: {namespace=} {job_name=}"
        super().__init__(self.message)


class MCPInvalidRuntimeError(ValueError):
    """An error that occurs when the runtime is invalid."""

    def __init__(self, runtime_exec: str | None, runtime_mcp: str | None, message: str) -> None:
        super().__init__(f"Invalid runtime: {runtime_exec=} and {runtime_mcp=} {message}")


class MCPNamespaceNotFoundError(ValueError):
    """An error that occurs when the namespace is not found."""

    def __init__(self, namespace: str):
        self.message = f"Namespace not found: {namespace}"
        super().__init__(self.message)


class MCPJobTimeoutError(Exception):
    """Exception raised when the MCP job times out."""

    def __init__(self, namespace: str, job_name: str):
        self.message = f"MCP job timed out: {namespace=} {job_name=}"
        super().__init__(self.message)


class MCPJobError(Exception):
    """Exception raised when the MCP job is in an error state."""

    def __init__(self, namespace: str, job_name: str, message: str):
        self.message = f"MCP job error: {namespace=} {job_name=} - {message}"
        super().__init__(self.message)


__all__ = [
    "MCPInvalidRuntimeError",
    "MCPJobError",
    "MCPJobNotFoundError",
    "MCPJobTimeoutError",
    "MCPServerCreationError",
]
