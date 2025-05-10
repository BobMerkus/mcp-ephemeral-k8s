from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServerConfig
from mcp_ephemeral_k8s.k8s.rbac import RBACPreset, ServiceAccountConfig

# https://github.com/modelcontextprotocol/servers/tree/main/src/fetch
FETCH = EphemeralMcpServerConfig(
    runtime_exec="uvx",
    runtime_mcp="mcp-server-fetch",
    env={
        "MCP_SERVER_PORT": "8080",
    },
)

# https://github.com/modelcontextprotocol/servers/tree/main/src/git
GIT = EphemeralMcpServerConfig(
    runtime_exec="uvx",
    runtime_mcp="mcp-server-git",
    env={
        "GIT_PYTHON_REFRESH": "quiet",
    },
)

# https://github.com/modelcontextprotocol/servers/tree/main/src/time
TIME = EphemeralMcpServerConfig(
    runtime_exec="uvx",
    runtime_mcp="mcp-server-time",
)

# https://github.com/containers/kubernetes-mcp-server
K8S_MCP_SERVER = EphemeralMcpServerConfig(
    runtime_exec="uvx",
    runtime_mcp="kubernetes-mcp-server",
    runtime_args="--port 8080",
    sa_config=ServiceAccountConfig(
        preset=RBACPreset.EXTENSIVE,
        cluster_wide=True,
    ),
)


# Collection of example MCP server configurations.
EXAMPLE_MCP_SERVER_CONFIGS: list[EphemeralMcpServerConfig] = [
    K8S_MCP_SERVER,
    FETCH,
    GIT,
    TIME,
]

__all__ = [
    "EXAMPLE_MCP_SERVER_CONFIGS",
    "FETCH",
    "GIT",
    "K8S_MCP_SERVER",
    "TIME",
]
