import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_root(fastapi_client: TestClient):
    response = fastapi_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}


@pytest.mark.integration
def test_list_mcp_servers(fastapi_client: TestClient):
    response = fastapi_client.get("/list_mcp_servers")
    assert response.status_code == 200
    assert response.json() == {"servers": []}


@pytest.mark.integration
def test_create_mcp_server(fastapi_client: TestClient):
    response = fastapi_client.post(
        "/create_mcp_server",
        json={"runtime_exec": "uvx", "runtime_mcp": "mcp-server-fetch", "env": {"MCP_SERVER_PORT": "8080"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pod_name"].startswith("mcp-ephemeral-k8s-proxy")
    assert body["config"]["runtime_exec"] == "uvx"
    assert body["config"]["runtime_mcp"] == "mcp-server-fetch"
    assert body["config"]["env"] == {"MCP_SERVER_PORT": "8080"}


@pytest.mark.integration
def test_delete_mcp_server(fastapi_client: TestClient):
    create_response = fastapi_client.post(
        "/create_mcp_server",
        json={"runtime_exec": "uvx", "runtime_mcp": "mcp-server-fetch", "env": {"MCP_SERVER_PORT": "8080"}},
    )
    assert create_response.status_code == 200
    body = create_response.json()
    assert body["pod_name"].startswith("mcp-ephemeral-k8s-proxy")
    assert body["config"]["runtime_exec"] == "uvx"
    assert body["config"]["runtime_mcp"] == "mcp-server-fetch"
    assert body["config"]["env"] == {"MCP_SERVER_PORT": "8080"}

    delete_response = fastapi_client.post("/delete_mcp_server", json={"pod_name": body["pod_name"]})
    assert delete_response.status_code == 200
    # assert delete_response.json() == body


@pytest.mark.integration
def test_delete_mcp_server_not_found(fastapi_client: TestClient):
    response = fastapi_client.post("/delete_mcp_server", json={"pod_name": "mcp-ephemeral-k8s-proxy-job"})
    assert response.status_code == 404, "The server should not be found, as it was not created"
