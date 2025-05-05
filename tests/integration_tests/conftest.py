from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from mcp_ephemeral_k8s import KubernetesSessionManager
from mcp_ephemeral_k8s.app.fastapi import app


@pytest.fixture(scope="module")
def kubernetes_session_manager() -> Generator[KubernetesSessionManager]:
    """
    Shared KubernetesSessionManager fixture for all integration tests.

    This fixture creates a KubernetesSessionManager instance that's shared across
    all tests within a module, reducing overhead of connection setup.

    Returns:
        Generator[KubernetesSessionManager, None, None]: A context manager for KubernetesSessionManager
    """
    with KubernetesSessionManager() as session_manager:
        yield session_manager


@pytest.fixture(scope="module")
def fastapi_client() -> Generator[TestClient]:
    """
    Shared FastAPI TestClient fixture for all integration tests.

    This fixture creates a TestClient instance that's shared across
    all tests within a module, reducing overhead of client setup.

    Returns:
        AsyncGenerator[TestClient, None]: A TestClient for FastAPI app
    """
    with TestClient(app) as client:
        yield client
