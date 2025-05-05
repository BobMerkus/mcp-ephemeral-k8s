import pytest
from pydantic import HttpUrl, ValidationError

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer, EphemeralMcpServerConfig


def test_model_default_values():
    # Test EphermalMcpServer
    mcp_server_config = EphemeralMcpServerConfig(
        runtime_exec="uvx",
        runtime_mcp="mcp-server-fetch",
    )
    assert mcp_server_config.port == 8080
    assert mcp_server_config.image == "mcp-ephemeral-proxy:latest"
    assert mcp_server_config.entrypoint == ["mcp-proxy"]
    assert mcp_server_config.args == [
        "--pass-environment",
        "--sse-port=8080",
        "--sse-host=0.0.0.0",
        "uvx",
        "mcp-server-fetch",
    ]
    assert mcp_server_config.resource_requests == {"cpu": "100m", "memory": "100Mi"}
    assert mcp_server_config.resource_limits == {"cpu": "200m", "memory": "200Mi"}
    assert mcp_server_config.env is None
    assert mcp_server_config.image_name == "mcp-ephemeral-proxy"
    assert mcp_server_config.job_name.startswith("mcp-ephemeral-proxy")

    mcp_server = EphemeralMcpServer(config=mcp_server_config, pod_name="mcp-proxy-pod")
    assert mcp_server.url == HttpUrl(f"http://{mcp_server.pod_name}:{mcp_server.config.port}")
    assert mcp_server.sse_url == HttpUrl(f"{mcp_server.url}/sse")


def test_model_runtime_exec_none():
    mcp_server_config = EphemeralMcpServerConfig(
        runtime_exec="npx",
        runtime_mcp="@modelcontextprotocol/server-github",
    )
    assert mcp_server_config.args == [
        "--pass-environment",
        "--sse-port=8080",
        "--sse-host=0.0.0.0",
        "npx",
        "@modelcontextprotocol/server-github",
    ]


def test_model_docker_values():
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

    mcp_server = EphemeralMcpServer(config=mcp_server_config, pod_name="github-mcp-server-pod")
    assert mcp_server.url == HttpUrl(f"http://{mcp_server.pod_name}:{mcp_server.config.port}")
    assert mcp_server.sse_url == HttpUrl(f"{mcp_server.url}/sse")


def test_model_invalid_runtime():
    with pytest.raises(ValidationError):
        EphemeralMcpServerConfig(runtime_exec=None, runtime_mcp="mcp-server-fetch")

    with pytest.raises(ValidationError):
        EphemeralMcpServerConfig(runtime_exec="uvx", runtime_mcp=None)
