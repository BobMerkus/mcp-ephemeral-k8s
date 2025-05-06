FROM ghcr.io/sparfenyuk/mcp-proxy:latest

# Add the local bin to the path
ENV PATH="/usr/local/bin:$PATH"

# Install npm
RUN apk add --no-cache npm

# Install the 'uv' package
RUN python3 -m ensurepip && pip install --no-cache-dir uv
ENV UV_PYTHON_PREFERENCE=only-system

# Preinstall the preset runtimes for uvx
RUN uv tool install mcp-server-fetch
RUN uv tool install mcp-server-time
RUN uv tool install mcp-server-git
RUN uv tool install awslabs.bedrock-kb-retrieval-mcp-server

# Install the preset runtimes for npx
RUN npm install @zereight/mcp-gitlab --global
RUN npm install @modelcontextprotocol/server-github --global

ENTRYPOINT [ "mcp-proxy" ]
