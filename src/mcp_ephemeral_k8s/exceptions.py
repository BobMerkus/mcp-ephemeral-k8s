"""
This module contains the exceptions for the MCP ephemeral K8s library.
"""


class MCPServerCreationError(Exception):
    """Exception raised when the MCP server creation fails."""

    def __init__(self, message: str):
        self.message = f"Failed to create MCP server: {message}"
        super().__init__(self.message)


class MCPJobNotFoundError(Exception):
    """Exception raised when the MCP job is not found."""

    def __init__(self, namespace: str, pod_name: str):
        self.message = f"Failed to find MCP job: {namespace=} {pod_name=}"
        super().__init__(self.message)


__all__ = ["MCPJobNotFoundError", "MCPServerCreationError"]
