"""Unit tests for RBAC functions."""

from unittest.mock import MagicMock

import pytest
from kubernetes import client
from kubernetes.client.rest import ApiException

from mcp_ephemeral_k8s.k8s.rbac import (
    RBACPreset,
    ServiceAccountConfig,
    UnknownRBACPresetError,
    _create_cluster_role_and_binding,
    _create_rbac_resource,
    _create_role_and_binding,
    _create_service_account,
    _delete_cluster_role_and_binding,
    _delete_rbac_resource,
    _delete_role_and_binding,
    _delete_service_account,
    _get_extensive_rbac_rules,
    _get_minimal_rbac_rules,
    _get_rbac_rules_by_preset,
    create_service_account_for_job,
    delete_service_account_for_job,
)


def test_create_role_and_binding():
    """Test creating namespaced role and rolebinding."""
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"
    namespace = "test-namespace"
    service_account_name = "test-sa"
    rules = [
        client.V1PolicyRule(
            api_groups=[""],
            resources=["pods"],
            verbs=["get", "list"],
        )
    ]

    # Mock the create methods to return success
    mock_rbac_v1.create_namespaced_role.return_value = None
    mock_rbac_v1.create_namespaced_role_binding.return_value = None

    # Call the function
    _create_role_and_binding(mock_rbac_v1, job_name, namespace, service_account_name, rules)

    # Verify role was created
    mock_rbac_v1.create_namespaced_role.assert_called_once()
    role_call_args = mock_rbac_v1.create_namespaced_role.call_args
    assert role_call_args[1]["namespace"] == namespace
    role = role_call_args[1]["body"]
    assert role.metadata.name == f"{job_name}-role"
    assert role.rules == rules

    # Verify rolebinding was created
    mock_rbac_v1.create_namespaced_role_binding.assert_called_once()
    binding_call_args = mock_rbac_v1.create_namespaced_role_binding.call_args
    assert binding_call_args[1]["namespace"] == namespace
    binding = binding_call_args[1]["body"]
    assert binding.metadata.name == f"{job_name}-rolebinding"
    assert binding.role_ref.name == f"{job_name}-role"
    assert len(binding.subjects) == 1
    assert binding.subjects[0].name == service_account_name


def test_delete_role_and_binding_success():
    """Test deleting namespaced role and rolebinding successfully."""
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock successful deletion
    mock_rbac_v1.delete_namespaced_role_binding.return_value = None
    mock_rbac_v1.delete_namespaced_role.return_value = None

    result = _delete_role_and_binding(mock_rbac_v1, job_name, namespace)

    assert result is True
    mock_rbac_v1.delete_namespaced_role_binding.assert_called_once()
    mock_rbac_v1.delete_namespaced_role.assert_called_once()


def test_delete_role_and_binding_not_found():
    """Test deleting namespaced role and rolebinding when resources don't exist."""
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock 404 errors (resources not found)
    not_found_exception = ApiException(status=404, reason="Not Found")
    mock_rbac_v1.delete_namespaced_role_binding.side_effect = not_found_exception
    mock_rbac_v1.delete_namespaced_role.side_effect = not_found_exception

    result = _delete_role_and_binding(mock_rbac_v1, job_name, namespace)

    assert result is True  # Should still return True for 404s
    mock_rbac_v1.delete_namespaced_role_binding.assert_called_once()
    mock_rbac_v1.delete_namespaced_role.assert_called_once()


def test_delete_role_and_binding_error():
    """Test deleting namespaced role and rolebinding with error."""
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    # Mock a non-404 error
    error_exception = ApiException(status=500, reason="Internal Server Error")
    mock_rbac_v1.delete_namespaced_role_binding.side_effect = error_exception

    result = _delete_role_and_binding(mock_rbac_v1, job_name, namespace)

    assert result is False
    mock_rbac_v1.delete_namespaced_role_binding.assert_called_once()


def test_delete_service_account_success():
    """Test deleting service account successfully."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    service_account_name = "test-sa"
    namespace = "test-namespace"

    # Mock successful deletion
    mock_core_v1.delete_namespaced_service_account.return_value = None

    result = _delete_service_account(mock_core_v1, service_account_name, namespace)

    assert result is True
    mock_core_v1.delete_namespaced_service_account.assert_called_once_with(
        name=service_account_name,
        namespace=namespace,
        body=client.V1DeleteOptions(propagation_policy="Foreground"),
    )


def test_delete_service_account_not_found():
    """Test deleting service account when it doesn't exist."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    service_account_name = "test-sa"
    namespace = "test-namespace"

    # Mock 404 error (resource not found)
    not_found_exception = ApiException(status=404, reason="Not Found")
    mock_core_v1.delete_namespaced_service_account.side_effect = not_found_exception

    result = _delete_service_account(mock_core_v1, service_account_name, namespace)

    assert result is True  # Should return True for 404s
    mock_core_v1.delete_namespaced_service_account.assert_called_once()


def test_delete_service_account_error():
    """Test deleting service account with error."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    service_account_name = "test-sa"
    namespace = "test-namespace"

    # Mock a non-404 error
    error_exception = ApiException(status=500, reason="Internal Server Error")
    mock_core_v1.delete_namespaced_service_account.side_effect = error_exception

    result = _delete_service_account(mock_core_v1, service_account_name, namespace)

    assert result is False
    mock_core_v1.delete_namespaced_service_account.assert_called_once()


def test_get_minimal_rbac_rules():
    """Test getting minimal RBAC rules."""
    rules = _get_minimal_rbac_rules()

    assert len(rules) == 1
    assert rules[0].api_groups == [""]
    assert "pods" in rules[0].resources
    assert "get" in rules[0].verbs
    assert "list" in rules[0].verbs


def test_get_extensive_rbac_rules():
    """Test getting extensive RBAC rules."""
    rules = _get_extensive_rbac_rules()

    # Should have many rules for various resources
    assert len(rules) > 5
    # Check for some key resources
    resource_types = []
    for rule in rules:
        resource_types.extend(rule.resources)
    assert "pods" in resource_types
    assert "services" in resource_types
    assert "deployments" in resource_types


def test_get_rbac_rules_by_preset_minimal():
    """Test getting RBAC rules by preset - minimal."""
    rules = _get_rbac_rules_by_preset(RBACPreset.MINIMAL)

    assert len(rules) == 1
    assert "pods" in rules[0].resources


def test_get_rbac_rules_by_preset_extensive():
    """Test getting RBAC rules by preset - extensive."""
    rules = _get_rbac_rules_by_preset(RBACPreset.EXTENSIVE)

    assert len(rules) > 5


def test_get_rbac_rules_by_preset_unknown():
    """Test getting RBAC rules by unknown preset raises error."""
    with pytest.raises(UnknownRBACPresetError) as exc_info:
        _get_rbac_rules_by_preset("invalid_preset")

    assert "invalid_preset" in str(exc_info.value)


def test_unknown_rbac_preset_error():
    """Test UnknownRBACPresetError exception."""
    preset = "invalid"
    error = UnknownRBACPresetError(preset)

    assert error.preset == preset
    assert "invalid" in str(error)


def test_create_service_account():
    """Test creating service account."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    service_account_name = "test-sa"
    namespace = "test-namespace"
    job_name = "test-job"

    _create_service_account(mock_core_v1, service_account_name, namespace, job_name)

    mock_core_v1.create_namespaced_service_account.assert_called_once()
    call_args = mock_core_v1.create_namespaced_service_account.call_args
    assert call_args[1]["namespace"] == namespace
    sa = call_args[1]["body"]
    assert sa.metadata.name == service_account_name
    assert sa.metadata.labels["app"] == job_name
    assert sa.automount_service_account_token is True


def test_create_service_account_already_exists():
    """Test creating service account when it already exists."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    service_account_name = "test-sa"
    namespace = "test-namespace"
    job_name = "test-job"

    # Mock 409 conflict error
    mock_core_v1.create_namespaced_service_account.side_effect = ApiException(status=409, reason="Conflict")

    # Should not raise, just log warning
    _create_service_account(mock_core_v1, service_account_name, namespace, job_name)


def test_create_service_account_other_error():
    """Test creating service account with other error."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    service_account_name = "test-sa"
    namespace = "test-namespace"
    job_name = "test-job"

    # Mock 500 error
    mock_core_v1.create_namespaced_service_account.side_effect = ApiException(
        status=500, reason="Internal Server Error"
    )

    with pytest.raises(ApiException):
        _create_service_account(mock_core_v1, service_account_name, namespace, job_name)


def test_create_rbac_resource_success():
    """Test creating RBAC resource successfully."""
    mock_create_func = MagicMock()
    resource_type = "Role"
    resource_name = "test-role"
    body = MagicMock()
    namespace = "test-namespace"

    _create_rbac_resource(mock_create_func, resource_type, resource_name, body, namespace)

    mock_create_func.assert_called_once_with(namespace=namespace, body=body)


def test_create_rbac_resource_cluster_wide():
    """Test creating cluster-wide RBAC resource."""
    mock_create_func = MagicMock()
    resource_type = "ClusterRole"
    resource_name = "test-cluster-role"
    body = MagicMock()

    _create_rbac_resource(mock_create_func, resource_type, resource_name, body)

    mock_create_func.assert_called_once_with(body=body)


def test_create_rbac_resource_already_exists():
    """Test creating RBAC resource when it already exists."""
    mock_create_func = MagicMock()
    mock_create_func.side_effect = ApiException(status=409, reason="Conflict")
    resource_type = "Role"
    resource_name = "test-role"
    body = MagicMock()
    namespace = "test-namespace"

    # Should not raise, just log warning
    _create_rbac_resource(mock_create_func, resource_type, resource_name, body, namespace)


def test_create_rbac_resource_other_error():
    """Test creating RBAC resource with other error."""
    mock_create_func = MagicMock()
    mock_create_func.side_effect = ApiException(status=500, reason="Internal Server Error")
    resource_type = "Role"
    resource_name = "test-role"
    body = MagicMock()
    namespace = "test-namespace"

    with pytest.raises(ApiException):
        _create_rbac_resource(mock_create_func, resource_type, resource_name, body, namespace)


def test_create_cluster_role_and_binding():
    """Test creating cluster role and binding."""
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"
    namespace = "test-namespace"
    service_account_name = "test-sa"
    rules = [client.V1PolicyRule(api_groups=[""], resources=["pods"], verbs=["get"])]

    _create_cluster_role_and_binding(mock_rbac_v1, job_name, namespace, service_account_name, rules)

    mock_rbac_v1.create_cluster_role.assert_called_once()
    mock_rbac_v1.create_cluster_role_binding.assert_called_once()


def test_delete_rbac_resource_success():
    """Test deleting RBAC resource successfully."""
    mock_delete_func = MagicMock()
    resource_type = "Role"
    resource_name = "test-role"
    namespace = "test-namespace"

    result = _delete_rbac_resource(mock_delete_func, resource_type, resource_name, namespace)

    assert result is True
    mock_delete_func.assert_called_once()


def test_delete_rbac_resource_not_found():
    """Test deleting RBAC resource when not found."""
    mock_delete_func = MagicMock()
    mock_delete_func.side_effect = ApiException(status=404, reason="Not Found")
    resource_type = "Role"
    resource_name = "test-role"
    namespace = "test-namespace"

    result = _delete_rbac_resource(mock_delete_func, resource_type, resource_name, namespace)

    assert result is True


def test_delete_rbac_resource_error():
    """Test deleting RBAC resource with error."""
    mock_delete_func = MagicMock()
    mock_delete_func.side_effect = ApiException(status=500, reason="Internal Server Error")
    resource_type = "Role"
    resource_name = "test-role"
    namespace = "test-namespace"

    result = _delete_rbac_resource(mock_delete_func, resource_type, resource_name, namespace)

    assert result is False


def test_delete_cluster_role_and_binding_success():
    """Test deleting cluster role and binding successfully."""
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"

    result = _delete_cluster_role_and_binding(mock_rbac_v1, job_name)

    assert result is True
    mock_rbac_v1.delete_cluster_role_binding.assert_called_once()
    mock_rbac_v1.delete_cluster_role.assert_called_once()


def test_delete_cluster_role_and_binding_partial_failure():
    """Test deleting cluster role and binding with partial failure."""
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"

    # Binding succeeds, role fails
    mock_rbac_v1.delete_cluster_role.side_effect = ApiException(status=500, reason="Internal Server Error")

    result = _delete_cluster_role_and_binding(mock_rbac_v1, job_name)

    assert result is False


def test_create_service_account_for_job_minimal():
    """Test creating service account for job with minimal preset."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    sa_name = create_service_account_for_job(mock_core_v1, mock_rbac_v1, job_name, namespace, cluster_wide=True)

    assert sa_name == f"{job_name}-sa"
    mock_core_v1.create_namespaced_service_account.assert_called_once()
    mock_rbac_v1.create_cluster_role.assert_called_once()
    mock_rbac_v1.create_cluster_role_binding.assert_called_once()


def test_create_service_account_for_job_extensive():
    """Test creating service account for job with extensive preset."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"
    namespace = "test-namespace"
    sa_config = ServiceAccountConfig(preset=RBACPreset.EXTENSIVE, cluster_wide=True)

    sa_name = create_service_account_for_job(mock_core_v1, mock_rbac_v1, job_name, namespace, sa_config=sa_config)

    assert sa_name == f"{job_name}-sa"
    mock_core_v1.create_namespaced_service_account.assert_called_once()
    mock_rbac_v1.create_cluster_role.assert_called_once()


def test_create_service_account_for_job_namespaced():
    """Test creating service account for job with namespaced role."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"
    namespace = "test-namespace"
    sa_config = ServiceAccountConfig(preset=RBACPreset.MINIMAL, cluster_wide=False)

    sa_name = create_service_account_for_job(
        mock_core_v1, mock_rbac_v1, job_name, namespace, cluster_wide=False, sa_config=sa_config
    )

    assert sa_name == f"{job_name}-sa"
    mock_core_v1.create_namespaced_service_account.assert_called_once()
    mock_rbac_v1.create_namespaced_role.assert_called_once()
    mock_rbac_v1.create_namespaced_role_binding.assert_called_once()


def test_delete_service_account_for_job_cluster_wide():
    """Test deleting service account for job with cluster-wide resources."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    result = delete_service_account_for_job(mock_core_v1, mock_rbac_v1, job_name, namespace, cluster_wide=True)

    assert result is True
    mock_rbac_v1.delete_cluster_role_binding.assert_called_once()
    mock_rbac_v1.delete_cluster_role.assert_called_once()
    mock_core_v1.delete_namespaced_service_account.assert_called_once()


def test_delete_service_account_for_job_namespaced():
    """Test deleting service account for job with namespaced resources."""
    mock_core_v1 = MagicMock(spec=client.CoreV1Api)
    mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)
    job_name = "test-job"
    namespace = "test-namespace"

    result = delete_service_account_for_job(mock_core_v1, mock_rbac_v1, job_name, namespace, cluster_wide=False)

    assert result is True
    mock_rbac_v1.delete_namespaced_role_binding.assert_called_once()
    mock_rbac_v1.delete_namespaced_role.assert_called_once()
    mock_core_v1.delete_namespaced_service_account.assert_called_once()


def test_service_account_config_defaults():
    """Test ServiceAccountConfig default values."""
    config = ServiceAccountConfig()

    assert config.preset == RBACPreset.MINIMAL
    assert config.cluster_wide is True


def test_rbac_preset_values():
    """Test RBAC preset enum values."""
    assert RBACPreset.MINIMAL == "minimal"
    assert RBACPreset.EXTENSIVE == "extensive"
