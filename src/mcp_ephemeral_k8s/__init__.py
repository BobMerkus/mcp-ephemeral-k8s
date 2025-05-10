import importlib.metadata

__version__ = importlib.metadata.version("mcp-ephemeral-k8s")

from .integrations import presets
from .session_manager import KubernetesRuntime, KubernetesSessionManager

__all__ = ["KubernetesRuntime", "KubernetesSessionManager", "presets"]
