from pydantic import BaseModel, Field

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer


class ListMcpServersResponse(BaseModel):
    servers: list[EphemeralMcpServer] = Field(description="The list of MCP servers")


class CreateMcpServerRequest(BaseModel):
    runtime_exec: str = Field(
        default="uvx", description="The runtime to use for the MCP server", examples=["uvx", "npx", "go run"]
    )
    runtime_mcp: str = Field(
        default="mcp-server-fetch",
        description="The runtime to use for the MCP server",
        examples=["mcp-server-fetch", "mcp-server-aws"],
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set for the MCP server",
        examples=[{"MCP_SERVER_PORT": "8080"}],
    )


class DeleteMcpServerRequest(BaseModel):
    pod_name: str = Field(description="The pod name of the MCP server to delete")
