FROM ghcr.io/sparfenyuk/mcp-proxy:v0.11.0

# Add the local bin to the path
ENV PATH="/usr/local/bin:$PATH"

# Install npm
RUN apk add --no-cache npm

# Install the 'uv' package
RUN python3 -m ensurepip && pip install --no-cache-dir uv
ENV UV_PYTHON_PREFERENCE=only-system
ENV UV_LINK_MODE=copy

# Preinstall the preset runtimes for uvx
RUN uv tool install mcp-server-fetch
RUN uv tool install mcp-server-time
RUN uv tool install mcp-server-git

ENTRYPOINT [ "mcp-proxy" ]
