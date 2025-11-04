import pytest
from pydantic import HttpUrl, ValidationError

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import (
    EphemeralMcpServer,
    EphemeralMcpServerConfig,
    MCPInvalidRuntimeError,
)


@pytest.mark.unit
def test_model_default_values() -> None:
    # Test EphermalMcpServer
    mcp_server_config = EphemeralMcpServerConfig(
        runtime_exec="uvx",
        runtime_mcp="mcp-server-fetch",
    )
    assert mcp_server_config.port == 8080
    assert mcp_server_config.image == "ghcr.io/bobmerkus/mcp-ephemeral-k8s-proxy:latest"
    assert mcp_server_config.entrypoint == ["mcp-proxy"]
    assert mcp_server_config.args == [
        "uvx",
        "mcp-server-fetch",
        "--pass-environment",
        "--port=8080",
        "--host=0.0.0.0",
        "--allow-origin",
        "*",
    ]
    assert mcp_server_config.resource_requests == {"cpu": "100m", "memory": "100Mi"}
    assert mcp_server_config.resource_limits == {"cpu": "200m", "memory": "200Mi"}
    assert mcp_server_config.env is None
    assert mcp_server_config.image_name == "mcp-ephemeral-k8s-proxy"
    assert mcp_server_config.job_name.startswith("mcp-ephemeral-k8s-proxy")

    mcp_server = EphemeralMcpServer(config=mcp_server_config, job_name="mcp-proxy-pod")
    assert mcp_server.url == HttpUrl(
        f"http://{mcp_server.job_name}.default.svc.cluster.local:{mcp_server.config.port}/"
    )
    assert mcp_server.sse_url == HttpUrl(f"{mcp_server.url}sse")


@pytest.mark.unit
def test_model_runtime_exec_none() -> None:
    mcp_server_config = EphemeralMcpServerConfig(
        runtime_exec="npx",
        runtime_mcp="@modelcontextprotocol/server-github",
    )
    assert mcp_server_config.args == [
        "npx",
        "@modelcontextprotocol/server-github",
        "--pass-environment",
        "--port=8080",
        "--host=0.0.0.0",
        "--allow-origin",
        "*",
    ]


@pytest.mark.unit
def test_model_docker_values() -> None:
    mcp_server_config = EphemeralMcpServerConfig(
        image="ghcr.io/github/github-mcp-server",
        entrypoint=["./github-mcp-server", "sse"],
        runtime_exec=None,
        runtime_mcp=None,
        host="0.0.0.0",  # noqa: S104
        port=8080,
        resource_requests={"cpu": "100m", "memory": "100Mi"},
        resource_limits={"cpu": "200m", "memory": "200Mi"},
        env=None,
    )
    assert mcp_server_config.args is None
    assert mcp_server_config.image_name == "github-mcp-server"
    assert mcp_server_config.job_name.startswith("github-mcp-server")

    mcp_server = EphemeralMcpServer(config=mcp_server_config, job_name="github-mcp-server-pod")
    assert mcp_server.url == HttpUrl(
        f"http://{mcp_server.job_name}.default.svc.cluster.local:{mcp_server.config.port}/"
    )
    assert mcp_server.sse_url == HttpUrl(f"{mcp_server.url}sse")


@pytest.mark.unit
def test_model_from_docker_image() -> None:
    mcp_server_config = EphemeralMcpServerConfig.from_docker_image(
        "docker.io/mcp/gitlab:latest", env={"GITLAB_PERSONAL_ACCESS_TOKEN": "1234567890"}
    )
    assert mcp_server_config.image == "docker.io/mcp/gitlab:latest"
    assert mcp_server_config.entrypoint is None
    assert mcp_server_config.args is None
    assert mcp_server_config.env == {"GITLAB_PERSONAL_ACCESS_TOKEN": "1234567890"}


@pytest.mark.unit
def test_model_with_runtime_args() -> None:
    mcp_server_config = EphemeralMcpServerConfig(
        runtime_exec="npx",
        runtime_mcp="@upstash/context7-mcp",
    )
    assert mcp_server_config.args == [
        "npx",
        "@upstash/context7-mcp",
        "--pass-environment",
        "--port=8080",
        "--host=0.0.0.0",
        "--allow-origin",
        "*",
    ]


@pytest.mark.unit
def test_model_invalid_runtime() -> None:
    with pytest.raises(ValidationError):
        EphemeralMcpServerConfig(runtime_exec=None, runtime_mcp="mcp-server-fetch")

    with pytest.raises(ValidationError):
        EphemeralMcpServerConfig(runtime_exec="uvx", runtime_mcp=None)

    with pytest.raises(MCPInvalidRuntimeError):
        EphemeralMcpServerConfig.from_docker_image("ghcr.io/bobmerkus/mcp-ephemeral-k8s-proxy:latest")
