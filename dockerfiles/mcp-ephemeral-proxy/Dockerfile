FROM ghcr.io/sparfenyuk/mcp-proxy:latest

# Add the local bin to the path
ENV PATH="/usr/local/bin:$PATH"

# Install npm
RUN apk add --no-cache npm

# Install the 'uv' package
RUN python3 -m ensurepip && pip install --no-cache-dir uv
ENV UV_PYTHON_PREFERENCE=only-system

ENTRYPOINT [ "mcp-proxy" ]
