"""
This module contains the exceptions for the MCP ephemeral K8s library.
"""


class MCPServerCreationError(Exception):
    """Exception raised when the MCP server creation fails."""

    def __init__(self, message: str = "Failed to create MCP server"):
        self.message = message
        super().__init__(self.message)


class MCPJobNotFoundError(Exception):
    """Exception raised when the MCP job is not found."""

    def __init__(self, message: str = "Failed to find MCP job"):
        self.message = message
        super().__init__(self.message)
