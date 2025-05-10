"""Helper functions for managing RBAC resources for spawned MCP server pods."""

import logging
from enum import StrEnum
from typing import Any

from kubernetes import client
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RBACPreset(StrEnum):
    """Preset RBAC configurations for service accounts."""

    MINIMAL = "minimal"
    EXTENSIVE = "extensive"


class UnknownRBACPresetError(ValueError):
    """Exception raised when an unknown RBAC preset is encountered."""

    def __init__(self, preset: RBACPreset) -> None:
        self.preset = preset
        super().__init__(f"Unknown RBAC preset: {preset}")


class ServiceAccountConfig(BaseModel):
    """Configuration for ServiceAccount RBAC permissions."""

    preset: RBACPreset = Field(
        default=RBACPreset.MINIMAL,
        description="The RBAC preset to use for the service account",
    )
    cluster_wide: bool = Field(
        default=True,
        description="Whether to create ClusterRole/ClusterRoleBinding (True) or Role/RoleBinding (False)",
    )


def _get_minimal_rbac_rules() -> list[client.V1PolicyRule]:
    """Get minimal read-only RBAC rules for MCP server pods.

    Provides basic read access to:
    - Pod's own namespace information
    - ConfigMaps and Secrets (read-only)
    - Services (read-only)
    """
    return [
        # Read-only access to core resources in namespace
        client.V1PolicyRule(
            api_groups=[""],
            resources=["pods", "services", "configmaps", "secrets"],
            verbs=["get", "list", "watch"],
        ),
    ]


def _get_extensive_rbac_rules() -> list[client.V1PolicyRule]:
    """Get extensive RBAC rules with write permissions for MCP server pods.

    This preset includes permissions for:
    - Full CRUD operations on core resources
    - Helm chart management (requires access to various resource types)
    - Pod exec permissions
    - Service account and RBAC resource management
    - Network policies and storage management
    """
    return [
        # Core resources - full access
        client.V1PolicyRule(
            api_groups=[""],
            resources=[
                "pods",
                "services",
                "configmaps",
                "secrets",
                "persistentvolumeclaims",
                "namespaces",
                "nodes",
                "serviceaccounts",
            ],
            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
        ),
        # Pod exec and logs
        client.V1PolicyRule(
            api_groups=[""],
            resources=["pods/exec", "pods/log", "pods/status"],
            verbs=["get", "list", "create"],
        ),
        # Apps resources - full access
        client.V1PolicyRule(
            api_groups=["apps"],
            resources=["deployments", "statefulsets", "daemonsets", "replicasets"],
            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
        ),
        # Batch resources - full access
        client.V1PolicyRule(
            api_groups=["batch"],
            resources=["jobs", "cronjobs"],
            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
        ),
        # Networking resources
        client.V1PolicyRule(
            api_groups=["networking.k8s.io"],
            resources=["ingresses", "networkpolicies"],
            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
        ),
        # RBAC resources - required for Helm
        client.V1PolicyRule(
            api_groups=["rbac.authorization.k8s.io"],
            resources=["roles", "rolebindings", "clusterroles", "clusterrolebindings"],
            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
        ),
        # Storage resources
        client.V1PolicyRule(
            api_groups=["storage.k8s.io"],
            resources=["storageclasses"],
            verbs=["get", "list", "watch"],
        ),
        # Policy resources - required for PodDisruptionBudgets in Helm charts
        client.V1PolicyRule(
            api_groups=["policy"],
            resources=["poddisruptionbudgets"],
            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
        ),
        # Autoscaling resources
        client.V1PolicyRule(
            api_groups=["autoscaling"],
            resources=["horizontalpodautoscalers"],
            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
        ),
        # Events
        client.V1PolicyRule(
            api_groups=[""],
            resources=["events"],
            verbs=["get", "list", "watch", "create"],
        ),
        # API Services - for metrics-server and aggregation
        client.V1PolicyRule(
            api_groups=["apiregistration.k8s.io"],
            resources=["apiservices"],
            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
        ),
    ]


def _get_rbac_rules_by_preset(preset: RBACPreset) -> list[client.V1PolicyRule]:
    """Get RBAC rules based on the specified preset."""
    match preset:
        case RBACPreset.MINIMAL:
            return _get_minimal_rbac_rules()
        case RBACPreset.EXTENSIVE:
            return _get_extensive_rbac_rules()
        case _:
            raise UnknownRBACPresetError(preset)


def _create_service_account(
    core_v1: client.CoreV1Api,
    service_account_name: str,
    namespace: str,
    job_name: str,
) -> None:
    """Create a ServiceAccount for the job."""
    service_account = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name=service_account_name,
            namespace=namespace,
            labels={
                "app": job_name,
                "managed-by": "mcp-ephemeral-k8s",
            },
        ),
        automount_service_account_token=True,
    )

    try:
        core_v1.create_namespaced_service_account(namespace=namespace, body=service_account)
        logger.info(f"ServiceAccount '{service_account_name}' created successfully")
    except ApiException as e:
        if e.status == 409:  # Already exists
            logger.warning(f"ServiceAccount '{service_account_name}' already exists")
        else:
            raise


def _create_rbac_resource(
    create_func: Any, resource_type: str, resource_name: str, body: Any, namespace: str | None = None
) -> None:
    """Helper function to create RBAC resources with consistent error handling.

    Args:
        create_func: Function to call to create the resource
        resource_type: Type of resource (e.g., 'ClusterRole', 'Role')
        resource_name: Name of the resource
        body: Resource body to create
        namespace: Optional namespace for namespaced resources
    """
    try:
        if namespace:
            create_func(namespace=namespace, body=body)
        else:
            create_func(body=body)
        logger.info(f"{resource_type} '{resource_name}' created successfully")
    except ApiException as e:
        if e.status == 409:  # Already exists
            logger.warning(f"{resource_type} '{resource_name}' already exists")
        else:
            raise


def _create_cluster_role_and_binding(
    rbac_v1: client.RbacAuthorizationV1Api,
    job_name: str,
    namespace: str,
    service_account_name: str,
    rules: list[client.V1PolicyRule],
) -> None:
    """Create ClusterRole and ClusterRoleBinding for the job."""
    cluster_role_name = f"{job_name}-role"
    cluster_role = client.V1ClusterRole(
        metadata=client.V1ObjectMeta(
            name=cluster_role_name,
            labels={
                "app": job_name,
                "managed-by": "mcp-ephemeral-k8s",
            },
        ),
        rules=rules,
    )
    _create_rbac_resource(rbac_v1.create_cluster_role, "ClusterRole", cluster_role_name, cluster_role)

    # Create ClusterRoleBinding
    cluster_role_binding_name = f"{job_name}-rolebinding"
    cluster_role_binding = client.V1ClusterRoleBinding(
        metadata=client.V1ObjectMeta(
            name=cluster_role_binding_name,
            labels={
                "app": job_name,
                "managed-by": "mcp-ephemeral-k8s",
            },
        ),
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name=cluster_role_name,
        ),
        subjects=[
            client.RbacV1Subject(
                kind="ServiceAccount",
                name=service_account_name,
                namespace=namespace,
            )
        ],
    )
    _create_rbac_resource(
        rbac_v1.create_cluster_role_binding, "ClusterRoleBinding", cluster_role_binding_name, cluster_role_binding
    )


def _create_role_and_binding(
    rbac_v1: client.RbacAuthorizationV1Api,
    job_name: str,
    namespace: str,
    service_account_name: str,
    rules: list[client.V1PolicyRule],
) -> None:
    """Create Role and RoleBinding for the job."""
    role_name = f"{job_name}-role"
    role = client.V1Role(
        metadata=client.V1ObjectMeta(
            name=role_name,
            namespace=namespace,
            labels={
                "app": job_name,
                "managed-by": "mcp-ephemeral-k8s",
            },
        ),
        rules=rules,
    )
    _create_rbac_resource(rbac_v1.create_namespaced_role, "Role", role_name, role, namespace)

    # Create RoleBinding
    role_binding_name = f"{job_name}-rolebinding"
    role_binding = client.V1RoleBinding(
        metadata=client.V1ObjectMeta(
            name=role_binding_name,
            namespace=namespace,
            labels={
                "app": job_name,
                "managed-by": "mcp-ephemeral-k8s",
            },
        ),
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            kind="Role",
            name=role_name,
        ),
        subjects=[
            client.RbacV1Subject(
                kind="ServiceAccount",
                name=service_account_name,
                namespace=namespace,
            )
        ],
    )
    _create_rbac_resource(
        rbac_v1.create_namespaced_role_binding, "RoleBinding", role_binding_name, role_binding, namespace
    )


def create_service_account_for_job(
    core_v1: client.CoreV1Api,
    rbac_v1: client.RbacAuthorizationV1Api,
    job_name: str,
    namespace: str,
    cluster_wide: bool = True,
    sa_config: ServiceAccountConfig | None = None,
) -> str:
    """
    Create a ServiceAccount and RBAC resources for a spawned MCP server job.

    This creates:
    - A ServiceAccount
    - A Role/ClusterRole with permissions based on the ServiceAccountConfig
    - A RoleBinding/ClusterRoleBinding

    Args:
        core_v1: The Kubernetes core API client
        rbac_v1: The Kubernetes RBAC API client
        job_name: The name of the job (used for naming resources)
        namespace: Kubernetes namespace
        cluster_wide: Whether to create ClusterRole/ClusterRoleBinding (default: True)
                     Note: This parameter is deprecated when sa_config is provided
        sa_config: ServiceAccount configuration with RBAC preset (default: minimal preset)

    Returns:
        The name of the created ServiceAccount
    """
    service_account_name = f"{job_name}-sa"

    # Create ServiceAccount
    _create_service_account(core_v1, service_account_name, namespace, job_name)

    # Use ServiceAccountConfig if provided, otherwise use defaults
    if sa_config is None:
        sa_config = ServiceAccountConfig()

    rules = _get_rbac_rules_by_preset(sa_config.preset)

    # Create Role/ClusterRole and RoleBinding/ClusterRoleBinding
    if sa_config.cluster_wide:
        _create_cluster_role_and_binding(rbac_v1, job_name, namespace, service_account_name, rules)
    else:
        _create_role_and_binding(rbac_v1, job_name, namespace, service_account_name, rules)

    return service_account_name


def _delete_rbac_resource(
    delete_func: Any, resource_type: str, resource_name: str, namespace: str | None = None
) -> bool:
    """Helper function to delete RBAC resources with consistent error handling.

    Args:
        delete_func: Function to call to delete the resource
        resource_type: Type of resource (e.g., 'ClusterRole', 'Role')
        resource_name: Name of the resource
        namespace: Optional namespace for namespaced resources

    Returns:
        True if deletion succeeded or resource not found, False on error
    """
    try:
        if namespace:
            delete_func(
                name=resource_name,
                namespace=namespace,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
        else:
            delete_func(
                name=resource_name,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
    except ApiException as e:
        if e.status == 404:
            logger.warning(f"{resource_type} '{resource_name}' not found")
            return True
        else:
            logger.exception(f"Error deleting {resource_type}")
            return False
    else:
        logger.info(f"{resource_type} '{resource_name}' deleted successfully")
        return True


def _delete_cluster_role_and_binding(
    rbac_v1: client.RbacAuthorizationV1Api,
    job_name: str,
) -> bool:
    """Delete ClusterRole and ClusterRoleBinding for the job. Returns True if successful."""
    # Delete ClusterRoleBinding
    cluster_role_binding_name = f"{job_name}-rolebinding"
    binding_success = _delete_rbac_resource(
        rbac_v1.delete_cluster_role_binding, "ClusterRoleBinding", cluster_role_binding_name
    )

    # Delete ClusterRole
    cluster_role_name = f"{job_name}-role"
    role_success = _delete_rbac_resource(rbac_v1.delete_cluster_role, "ClusterRole", cluster_role_name)

    return binding_success and role_success


def _delete_role_and_binding(
    rbac_v1: client.RbacAuthorizationV1Api,
    job_name: str,
    namespace: str,
) -> bool:
    """Delete Role and RoleBinding for the job. Returns True if successful."""
    # Delete RoleBinding
    role_binding_name = f"{job_name}-rolebinding"
    binding_success = _delete_rbac_resource(
        rbac_v1.delete_namespaced_role_binding, "RoleBinding", role_binding_name, namespace
    )

    # Delete Role
    role_name = f"{job_name}-role"
    role_success = _delete_rbac_resource(rbac_v1.delete_namespaced_role, "Role", role_name, namespace)

    return binding_success and role_success


def _delete_service_account(
    core_v1: client.CoreV1Api,
    service_account_name: str,
    namespace: str,
) -> bool:
    """Delete the ServiceAccount. Returns True if successful."""
    try:
        core_v1.delete_namespaced_service_account(
            name=service_account_name,
            namespace=namespace,
            body=client.V1DeleteOptions(propagation_policy="Foreground"),
        )
    except ApiException as e:
        if e.status == 404:
            logger.warning(f"ServiceAccount '{service_account_name}' not found")
            return True
        else:
            logger.exception("Error deleting ServiceAccount")
            return False
    else:
        logger.info(f"ServiceAccount '{service_account_name}' deleted successfully")
        return True


def delete_service_account_for_job(
    core_v1: client.CoreV1Api,
    rbac_v1: client.RbacAuthorizationV1Api,
    job_name: str,
    namespace: str,
    cluster_wide: bool = True,
) -> bool:
    """
    Delete the ServiceAccount and RBAC resources for a spawned MCP server job.

    Args:
        core_v1: The Kubernetes core API client
        rbac_v1: The Kubernetes RBAC API client
        job_name: The name of the job
        namespace: Kubernetes namespace
        cluster_wide: Whether ClusterRole/ClusterRoleBinding were created (default: True)

    Returns:
        True if all resources were deleted successfully, False otherwise
    """
    service_account_name = f"{job_name}-sa"

    # Delete Role/ClusterRole and RoleBinding/ClusterRoleBinding
    if cluster_wide:
        rbac_success = _delete_cluster_role_and_binding(rbac_v1, job_name)
    else:
        rbac_success = _delete_role_and_binding(rbac_v1, job_name, namespace)

    # Delete ServiceAccount
    sa_success = _delete_service_account(core_v1, service_account_name, namespace)

    return rbac_success and sa_success


__all__ = [
    "RBACPreset",
    "ServiceAccountConfig",
    "create_service_account_for_job",
    "delete_service_account_for_job",
]
