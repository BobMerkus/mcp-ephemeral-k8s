from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServerConfig

FETCH = EphemeralMcpServerConfig(
    runtime_exec="uvx",
    runtime_mcp="mcp-server-fetch",
    env={
        "MCP_SERVER_PORT": "8080",
    },
    resource_requests={"cpu": "100m", "memory": "100Mi"},
    resource_limits={"cpu": "200m", "memory": "200Mi"},
)

GIT = EphemeralMcpServerConfig(
    runtime_exec="uvx",
    runtime_mcp="mcp-server-git",
    env={
        "GIT_PYTHON_REFRESH": "quiet",
    },
    resource_requests={"cpu": "100m", "memory": "100Mi"},
    resource_limits={"cpu": "200m", "memory": "200Mi"},
)

GITHUB = EphemeralMcpServerConfig(
    runtime_exec="npx",
    runtime_mcp="@modelcontextprotocol/server-github",
    env={
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_1234567890",
        "GITHUB_DYNAMIC_TOOLSETS": "1",
    },
    resource_requests={"cpu": "100m", "memory": "100Mi"},
    resource_limits={"cpu": "200m", "memory": "200Mi"},
)

GITLAB = EphemeralMcpServerConfig(
    runtime_exec="npx",
    runtime_mcp="@zereight/mcp-gitlab",
    env={
        "GITLAB_PERSONAL_ACCESS_TOKEN": "glpat_1234567890",
        "GITLAB_API_URL": "https://gitlab.com/api/v4",
        "GITLAB_READ_ONLY_MODE": "false",
        "USE_GITLAB_WIKI": "true",
    },
    resource_requests={"cpu": "100m", "memory": "100Mi"},
    resource_limits={"cpu": "200m", "memory": "200Mi"},
)

BEDROCK_KB_RETRIEVAL = EphemeralMcpServerConfig(
    runtime_exec="uvx",
    runtime_mcp="awslabs.bedrock-kb-retrieval-mcp-server",
    env={
        "AWS_ACCESS_KEY_ID": "ASIAIOSFODNN7EXAMPLE",
        "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "AWS_SESSION_TOKEN": "AQoEXAMPLEH4aoAH0gNCAPy...truncated...zrkuWJOgQs8IZZaIv2BXIa2R4Olgk",
        "FASTMCP_LOG_LEVEL": "ERROR",
    },
    resource_requests={"cpu": "100m", "memory": "100Mi"},
    resource_limits={"cpu": "200m", "memory": "200Mi"},
)

TIME = EphemeralMcpServerConfig(
    runtime_exec="uvx",
    runtime_mcp="mcp-server-time",
)

__all__ = ["BEDROCK_KB_RETRIEVAL", "FETCH", "GIT", "GITHUB", "GITLAB", "TIME"]
