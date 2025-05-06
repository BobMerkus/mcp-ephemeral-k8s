from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from mcp_ephemeral_k8s import KubernetesSessionManager
from mcp_ephemeral_k8s.app.fastapi import app


@pytest.fixture(scope="function")
def kubernetes_session_manager() -> Generator[KubernetesSessionManager]:
    """
    Shared KubernetesSessionManager fixture for all integration tests.

    This fixture creates a KubernetesSessionManager instance that's shared across
    all tests within a specific scope.

    Returns:
        Generator[KubernetesSessionManager, None, None]: A context manager for KubernetesSessionManager
    """
    with KubernetesSessionManager() as session_manager:
        yield session_manager


@pytest.fixture(scope="function")
def fastapi_client() -> Generator[TestClient]:
    """
    Shared FastAPI TestClient fixture for all integration tests.

    This fixture creates a TestClient instance that's shared across
    all tests within a specific scope.

    Returns:
        Generator[TestClient, None, None]: A TestClient for FastAPI app
    """
    with TestClient(app) as client:
        yield client
