"""
This module contains the models for the MCP ephemeral K8s library.
"""

from pydantic import BaseModel, Field, computed_field


class ephemeralMcpServerConfig(BaseModel):
    """Configuration for Kubernetes resources."""

    image: str = Field(
        default="ghcr.io/sparfenyuk/mcp-proxy:latest",
        description="The image to use for the MCP server proxy",
    )
    entrypoint: str = Field(default="mcp-proxy", description="The entrypoint for the MCP container")
    args: list[str] = Field(
        default=[
            "--pass-environment",
            "--sse-port=8080",
            "--sse-host=0.0.0.0",
            "npx",
            "@modelcontextprotocol/server-gitlab",
        ],
        description="The arguments to pass to the MCP container",
    )
    namespace: str = Field(default="default", description="The namespace to create resources in")
    port: int = Field(default=8080, description="The port to expose the MCP server on")
    resource_requests: dict[str, str] = Field(
        default={"cpu": "100m", "memory": "100Mi"}, description="Resource requests for the container"
    )
    resource_limits: dict[str, str] = Field(
        default={"cpu": "200m", "memory": "200Mi"}, description="Resource limits for the container"
    )
    env: dict[str, str] | None = Field(default=None, description="Environment variables to set for the container")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def image_name(self) -> str:
        return self.image.split("/")[-1].split(":")[0]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def job_name(self) -> str:
        return f"{self.image_name}-job"


class ephemeralMcpServer(BaseModel):
    config: ephemeralMcpServerConfig = Field(description="The configuration that was used to create the MCP server")
    pod_name: str = Field(description="The name of the pod that is running the MCP server")
    protocol: str = Field(default="http", description="The protocol to use for the MCP server")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.pod_name}:{self.config.port}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sse_url(self) -> str:
        return f"{self.url}/sse"


__all__ = ["ephemeralMcpServer", "ephemeralMcpServerConfig"]
