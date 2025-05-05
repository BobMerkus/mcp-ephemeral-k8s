import socket
import time
from contextlib import suppress
from http.client import HTTPConnection

import pytest
from kubernetes.client.exceptions import ApiException

from mcp_ephemeral_k8s.api.ephemeral_mcp_server import EphemeralMcpServerConfig
from mcp_ephemeral_k8s.session_manager import KubernetesSessionManager


def is_port_open(port, host="localhost", timeout=1.0):
    """Check if a port is open by attempting a socket connection"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0


@pytest.mark.integration
def test_port_forward_actual_connection():
    """
    Integration test for port forwarding to a real Kubernetes cluster.

    This test:
    1. Creates an MCP server in the Kubernetes cluster
    2. Sets up port forwarding
    3. Verifies the port is accessible locally
    4. Cleans up resources
    """
    config = EphemeralMcpServerConfig(
        runtime_exec="uvx",
        runtime_mcp="mcp-server-fetch",
    )

    port_forward_obj = None

    try:
        with KubernetesSessionManager() as session_manager:
            # Create MCP server
            mcp_server = session_manager.create_mcp_server(config, wait_for_ready=True)

            try:
                # Create port forward
                port_forward_obj = session_manager.create_port_forward(mcp_server)

                # Wait a moment for port forwarding to be established
                time.sleep(3)

                # Check if the port is accessible
                port = mcp_server.config.port
                assert is_port_open(port), f"Port {port} is not accessible"

                # Try to make a simple HTTP connection to verify connectivity
                # This might fail if the service doesn't respond to HTTP,
                # but it will verify the TCP connection
                try:
                    conn = HTTPConnection(f"localhost:{port}", timeout=5)
                    conn.request("GET", "/")
                    response = conn.getresponse()
                    print(f"Response status: {response.status}")
                    conn.close()
                except Exception as e:
                    print(f"HTTP connection attempt: {e}")

                # Verify port forwarding cleanup
                session_manager.delete_port_forward(mcp_server)

                # Allow time for port forwarding to close
                time.sleep(1)

                # Port should no longer be accessible
                assert not is_port_open(port), f"Port {port} is still accessible after deletion"

            finally:
                # Ensure cleanup happens
                if port_forward_obj:
                    with suppress(Exception):
                        port_forward_obj.close()
                session_manager.delete_mcp_server(mcp_server.pod_name, wait_for_deletion=True)
    except (ApiException, ConnectionError) as e:
        pytest.skip(f"Skipping integration test: Kubernetes cluster not available - {e!s}")
