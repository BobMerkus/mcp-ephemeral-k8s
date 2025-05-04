"""
This module contains the models for the MCP ephemeral K8s library.
"""

from pydantic import BaseModel, Field, HttpUrl, computed_field

from mcp_ephemeral_k8s.k8s.uid import generate_unique_id


class EphemeralMcpServerConfig(BaseModel):
    """Configuration for Kubernetes resources."""

    image: str = Field(
        default="mcp-ephemeral-proxy:latest",
        description="The image to use for the MCP server proxy",
    )
    entrypoint: str = Field(
        default="mcp-proxy", description="The entrypoint for the MCP container. Normally not changed."
    )
    runtime_exec: str = Field(
        default="uvx", description="The runtime to use for the MCP container. Can be either 'uvx', 'npx' or 'go run'"
    )
    runtime_mcp: str = Field(
        default="mcp-server-fetch",
        description="The runtime to use for the MCP container. Can be any supported MCP server runtime loadable via the `runtime_exec`.",
    )
    host: str = Field(default="0.0.0.0", description="The host to expose the MCP server on")  # noqa: S104
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
    def args(self) -> list[str]:
        return [
            "--pass-environment",
            f"--sse-port={self.port}",
            f"--sse-host={self.host}",
            self.runtime_exec,
            self.runtime_mcp,
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def image_name(self) -> str:
        return self.image.split("/")[-1].split(":")[0]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def job_name(self) -> str:
        return generate_unique_id(prefix=self.image_name)


class EphemeralMcpServer(BaseModel):
    """The MCP server that is running in a Kubernetes pod."""

    config: EphemeralMcpServerConfig = Field(description="The configuration that was used to create the MCP server")
    pod_name: str = Field(
        description="The name of the pod that is running the MCP server", examples=["mcp-ephemeral-proxy-test"]
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> HttpUrl:
        """The Uniform Resource Locator (URL) for the MCP server."""
        return HttpUrl(f"http://{self.pod_name}:{self.config.port}")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sse_url(self) -> HttpUrl:
        """The Server-Sent Events (SSE) URL for the MCP server."""
        return HttpUrl(f"{self.url}/sse")


__all__ = ["EphemeralMcpServer", "EphemeralMcpServerConfig"]
