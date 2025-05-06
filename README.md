# mcp-ephemeral-k8s

[![Release](https://img.shields.io/github/v/release/BobMerkus/mcp-ephemeral-k8s)](https://img.shields.io/github/v/release/BobMerkus/mcp-ephemeral-k8s)
[![Build status](https://img.shields.io/github/actions/workflow/status/BobMerkus/mcp-ephemeral-k8s/main.yml?branch=main)](https://github.com/BobMerkus/mcp-ephemeral-k8s/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/BobMerkus/mcp-ephemeral-k8s/branch/main/graph/badge.svg)](https://codecov.io/gh/BobMerkus/mcp-ephemeral-k8s)
[![Commit activity](https://img.shields.io/github/commit-activity/m/BobMerkus/mcp-ephemeral-k8s)](https://img.shields.io/github/commit-activity/m/BobMerkus/mcp-ephemeral-k8s)
[![License](https://img.shields.io/github/license/BobMerkus/mcp-ephemeral-k8s)](https://img.shields.io/github/license/BobMerkus/mcp-ephemeral-k8s)

A Python library for spawning ephemeral Model Context Protocol (MCP) servers on Kubernetes using Server-Sent Events (SSE).

- **Github**: <https://github.com/BobMerkus/mcp-ephemeral-k8s/>
- **Documentation**: <https://BobMerkus.github.io/mcp-ephemeral-k8s/>

## Features

- Supports multiple runtimes:
  - Node.js (via `npx`)
  - Python (via `uvx`)
- Works with [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) for `uvx` or `npx` runtimes
- Supports both local kubeconfig and in-cluster configuration
- Can be run as MCP server
- Can be run as FastAPI server

## Usage

### Running the MCP Server

```bash
uvx mcp-ephemeral-k8s
```

### Using the Library

```python
from mcp_ephemeral_k8s import KubernetesSessionManager, presets

with KubernetesSessionManager() as session_manager:
    mcp_server = session_manager.create_mcp_server(presets.GITHUB, wait_for_ready=True)
    print(mcp_server.sse_url)
```

## Installation

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Kind](https://kind.sigs.k8s.io/docs/user/quick-start/) or any Kubernetes cluster with valid `kubectl` configuration

### Option 1: Using `uvx` (Recommended)

```bash
uvx mcp-ephemeral-k8s
```

To connect to the MCP server, use the following config:
```json
{
   "mcp-ephemeral-k8s": {
      "url": "http://localhost:8000/sse",
      "transport": "sse"
   }
}
```

### Option 2: As a Python Package

```bash
pip install mcp-ephemeral-k8s
mcp-ephemeral-k8s
```

### Option 3: Using Helm Chart
To install the Helm chart, run:

```bash
helm repo add mcp-ephemeral-k8s https://BobMerkus.github.io/mcp-ephemeral-k8s/
helm repo update
helm install mcp-ephemeral-k8s mcp-ephemeral-k8s/mcp-ephemeral-k8s
```

To upgrade the Helm chart, run:
```bash
helm upgrade -i mcp-ephemeral-k8s mcp-ephemeral-k8s/mcp-ephemeral-k8s
```

To install a specific version, run:
```bash
helm install mcp-ephemeral-k8s mcp-ephemeral-k8s/mcp-ephemeral-k8s --version <replace-with-version>
```

To uninstall the Helm chart, run:
```bash
helm uninstall mcp-ephemeral-k8s
```

### Option 4: From Source

1. **Clone the repository**
   ```bash
   git clone https://github.com/BobMerkus/mcp-ephemeral-k8s.git
   cd mcp-ephemeral-k8s
   ```

2. **Set up development environment**
   ```bash
   make install
   ```

3. **Run pre-commit hooks**
   ```bash
   make check
   ```

4. **Run tests**
   ```bash
   make test
   ```

5. **Build Docker images**
   ```bash
   make docker-build-local
   make docker-build-local-proxy
   ```

6. **Load images to cluster**
   ```bash
   kind load docker-image ghcr.io/bobmerkus/mcp-ephemeral-k8s:latest
   kind load docker-image ghcr.io/bobmerkus/mcp-ephemeral-k8s-proxy:latest
   ```

7. **Install Helm chart**
   ```bash
   helm upgrade -i mcp-ephemeral-k8s charts/mcp-ephemeral-k8s --set image.tag=latest
   ```

8. **Port forward the FastAPI server**
   ```bash
   kubectl port-forward svc/mcp-ephemeral-k8s 8000:8000
   ```

9. **Visit the FastAPI server**
   ```bash
   open http://localhost:8000/docs
   ```
