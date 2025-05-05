"""
This module contains the models for the MCP ephemeral K8s library.
"""

from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, Field, HttpUrl, computed_field, model_validator

from mcp_ephemeral_k8s.api.exceptions import MCPInvalidRuntimeError
from mcp_ephemeral_k8s.k8s.uid import generate_unique_id


class KubernetesRuntime(str, Enum):
    """The runtime that is being used for Kubeconfig"""

    KUBECONFIG = "KUBECONFIG"
    INCLUSTER = "INCLUSTER"


class EphemeralMcpServerConfig(BaseModel):
    """Configuration for Kubernetes resources."""

    runtime_exec: str | None = Field(
        description="The runtime to use for the MCP container. When None, the image is assumed to be a MCP server instead of a proxy.",
        examples=["uvx", "npx"],
    )
    runtime_mcp: str | None = Field(
        description="The runtime to use for the MCP container. Can be any supported MCP server runtime loadable via the `runtime_exec`.",
        examples=["mcp-server-fetch", "@modelcontextprotocol/server-github"],
    )
    image: str = Field(
        default="ghcr.io/bobmerkus/mcp-ephemeral-k8s-proxy:latest",
        description="The image to use for the MCP server proxy",
    )
    entrypoint: list[str] | None = Field(
        default=["mcp-proxy"],
        description="The entrypoint for the MCP container. Normally not changed unless a custom image is used.",
    )
    host: str = Field(default="0.0.0.0", description="The host to expose the MCP server on")  # noqa: S104
    port: int = Field(default=8080, description="The port to expose the MCP server on")
    resource_requests: dict[str, str] = Field(
        default={"cpu": "100m", "memory": "100Mi"}, description="Resource requests for the container"
    )
    resource_limits: dict[str, str] = Field(
        default={"cpu": "200m", "memory": "200Mi"}, description="Resource limits for the container"
    )
    env: dict[str, str] | None = Field(
        default=None,
        description="Environment variables to set for the container",
        examples=[None, {"GITHUB_PERSONAL_ACCESS_TOKEN": "1234567890", "GITHUB_DYNAMIC_TOOLSETS": "1"}],
    )

    @model_validator(mode="after")
    def validate_runtime_exec(self) -> Self:
        if self.runtime_exec is not None and self.runtime_mcp is None:
            message = "Invalid runtime: runtime_exec is specified but runtime_mcp is not"
            raise MCPInvalidRuntimeError(runtime_exec=self.runtime_exec, runtime_mcp=self.runtime_mcp, message=message)
        if self.runtime_exec is None and self.runtime_mcp is not None:
            message = "Invalid runtime: runtime_mcp is specified but runtime_exec is not"
            raise MCPInvalidRuntimeError(runtime_exec=self.runtime_exec, runtime_mcp=self.runtime_mcp, message=message)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def args(self) -> list[str] | None:
        if self.runtime_exec is not None and self.runtime_mcp is not None:
            return [
                "--pass-environment",
                f"--sse-port={self.port}",
                f"--sse-host={self.host}",
                self.runtime_exec,
                self.runtime_mcp,
            ]
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def image_name(self) -> str:
        return self.image.split("/")[-1].split(":")[0]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def job_name(self) -> str:
        return generate_unique_id(prefix=self.image_name)

    @classmethod
    def from_docker_image(cls, image: str, entrypoint: list[str] | None = None, **kwargs: Any) -> Self:
        if image == "ghcr.io/bobmerkus/mcp-ephemeral-k8s-proxy:latest":
            message = "Invalid runtime: image is a proxy image, please use the `runtime_exec` and `runtime_mcp` fields to specify the MCP server to use."
            raise MCPInvalidRuntimeError(runtime_exec=None, runtime_mcp=None, message=message)
        return cls(image=image, entrypoint=entrypoint, runtime_exec=None, runtime_mcp=None, **kwargs)


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
