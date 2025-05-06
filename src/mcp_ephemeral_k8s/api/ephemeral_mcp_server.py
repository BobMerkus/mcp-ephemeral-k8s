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


class KubernetesProbeConfig(BaseModel):
    """The configuration for the Kubernetes probe."""

    initial_delay_seconds: int = Field(default=10, description="The initial delay seconds for the probe")
    period_seconds: int = Field(default=1, description="The period seconds for the probe")
    timeout_seconds: int = Field(default=2, description="The timeout seconds for the probe")
    success_threshold: int = Field(default=1, description="The success threshold for the probe")
    failure_threshold: int = Field(default=300, description="The failure threshold for the probe")


class EphemeralMcpServerConfig(BaseModel):
    """Configuration for Kubernetes resources."""

    runtime_exec: str | None = Field(
        description="The runtime to use for the MCP container. When None, the image is assumed to be a MCP server instead of a proxy.",
        examples=["uvx", "npx"],
    )
    runtime_mcp: str | None = Field(
        description="The runtime to use for the MCP container. Can be any supported MCP server runtime loadable via the `runtime_exec`. See the [MCP Server Runtimes](https://github.com/modelcontextprotocol/servers/tree/main) for a list of supported runtimes.",
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
    cors_origins: list[str] | None = Field(
        default=["*"],
        description="The origins to allow CORS from",
        examples=["*"],
    )
    probe_config: KubernetesProbeConfig = Field(
        default_factory=KubernetesProbeConfig,
        description="The configuration for the Kubernetes probe",
    )

    @model_validator(mode="after")
    def validate_runtime_exec(self) -> Self:
        """Validate the runtime configuration.
        Both runtime_exec and runtime_mcp must be specified, or neither.
        """
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
        """The arguments to pass to the MCP server.
        [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy?tab=readme-ov-file#21-configuration)"""
        if self.runtime_exec is not None and self.runtime_mcp is not None:
            args = [
                "--pass-environment",
                f"--sse-port={self.port}",
                f"--sse-host={self.host}",
                self.runtime_exec,
                self.runtime_mcp,
            ]
            if self.cors_origins is not None:
                args.extend(["--allow-origin", *self.cors_origins])
            return args
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def image_name(self) -> str:
        """The name of the image to use for the MCP server."""
        return self.image.split("/")[-1].split(":")[0]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def job_name(self) -> str:
        """The name of the job to use for the MCP server."""
        return generate_unique_id(prefix=self.image_name)

    @classmethod
    def from_docker_image(cls, image: str, entrypoint: list[str] | None = None, **kwargs: Any) -> Self:
        """Create an EphemeralMcpServerConfig from a Docker image.
        The image must be a MCP server image, otherwise an error is raised.
        """
        if image.startswith("ghcr.io/bobmerkus/mcp-ephemeral-k8s-proxy") or image.startswith(
            "ghcr.io/sparfenyuk/mcp-proxy"
        ):
            message = "Invalid runtime: image is a proxy image, please use the `runtime_exec` and `runtime_mcp` fields to specify the MCP server to use."
            raise MCPInvalidRuntimeError(runtime_exec=None, runtime_mcp=None, message=message)
        return cls(image=image, entrypoint=entrypoint, runtime_exec=None, runtime_mcp=None, **kwargs)


class EphemeralMcpServer(BaseModel):
    """The MCP server that is running in a Kubernetes pod."""

    pod_name: str = Field(
        description="The name of the pod that is running the MCP server", examples=["mcp-ephemeral-k8s-proxy-test"]
    )
    config: EphemeralMcpServerConfig = Field(
        description="The configuration that was used to create the MCP server",
        examples=[
            EphemeralMcpServerConfig(
                runtime_exec="uvx",
                runtime_mcp="mcp-server-fetch",
                port=8000,
                cors_origins=["*"],
            )
        ],
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> HttpUrl:
        """The Uniform Resource Locator (URL) for the MCP server."""
        return HttpUrl(f"http://{self.pod_name}.default.svc.cluster.local:{self.config.port}/")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sse_url(self) -> HttpUrl:
        """The Server-Sent Events (SSE) URL for the MCP server."""
        return HttpUrl(f"{self.url}sse")


__all__ = ["EphemeralMcpServer", "EphemeralMcpServerConfig"]
