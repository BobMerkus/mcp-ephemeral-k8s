from mcp_ephemeral_k8s.model import ephemeralMcpServer, ephemeralMcpServerConfig


def test_model_default_values():
    # Test EphermalMcpServer
    mcp_server_config = ephemeralMcpServerConfig()
    assert mcp_server_config.port == 8080
    assert mcp_server_config.namespace == "default"
    assert mcp_server_config.image == "ghcr.io/sparfenyuk/mcp-proxy:latest"
    assert mcp_server_config.entrypoint == "mcp-proxy"
    assert mcp_server_config.args == [
        "--pass-environment",
        "--sse-port=8080",
        "--sse-host=0.0.0.0",
        "npx",
        "@modelcontextprotocol/server-gitlab",
    ]
    assert mcp_server_config.resource_requests == {"cpu": "100m", "memory": "100Mi"}
    assert mcp_server_config.resource_limits == {"cpu": "200m", "memory": "200Mi"}
    assert mcp_server_config.env is None
    assert mcp_server_config.image_name == "mcp-proxy"
    assert mcp_server_config.job_name == "mcp-proxy-job"

    mcp_server = ephemeralMcpServer(config=mcp_server_config, pod_name="mcp-proxy-pod", protocol="http")
    assert mcp_server.url == f"http://{mcp_server.pod_name}:{mcp_server.config.port}"
    assert mcp_server.sse_url == f"{mcp_server.url}/sse"
