from pydantic import HttpUrl

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServer, EphemeralMcpServerConfig


def test_model_default_values():
    # Test EphermalMcpServer
    mcp_server_config = EphemeralMcpServerConfig()
    assert mcp_server_config.port == 8080
    assert mcp_server_config.image == "mcp-ephemeral-proxy:latest"
    assert mcp_server_config.entrypoint == "mcp-proxy"
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
    assert mcp_server_config.job_name == "mcp-ephemeral-proxy-job"

    mcp_server = EphemeralMcpServer(config=mcp_server_config, pod_name="mcp-proxy-pod")
    assert mcp_server.url == HttpUrl(f"http://{mcp_server.pod_name}:{mcp_server.config.port}")
    assert mcp_server.sse_url == HttpUrl(f"{mcp_server.url}/sse")
