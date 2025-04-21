import os
import platform
from typing import Dict, Union, Literal, Optional
from functools import lru_cache


class OtherPlatform:
    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return f"Other:{self.name}"


Platform = Union[
    OtherPlatform,
    Literal[
        "MacOS",
        "Linux",
        "Windows",
        "iOS",
        "Android",
        "Unknown",
    ],
]


def get_platform() -> Platform:
    try:
        system = platform.system().lower()
        platform_name = platform.platform().lower()
    except Exception:
        return "Unknown"

    if "iphone" in platform_name or "ipad" in platform_name:
        # Tested using Python3IDE on an iPhone 11 and Pythonista on an iPad 7
        # system is Darwin and platform_name is a string like:
        # - Darwin-21.6.0-iPhone12,1-64bit
        # - Darwin-21.6.0-iPad7,11-64bit
        return "iOS"

    if system == "darwin":
        return "MacOS"

    if system == "windows":
        return "Windows"

    if "android" in platform_name:
        # Tested using Pydroid 3
        return "Android"

    if system == "linux":
        return "Linux"

    if platform_name:
        return OtherPlatform(platform_name)

    return "Unknown"


@lru_cache(maxsize=None)
def platform_session_attributes(version: str, *, platform: Optional[Platform]) -> Dict[str, str]:
    """Return a dictionary with the session attributes.

    They provide information about the platform and the SDK version.

    Args:
        version: The version of the SDK.
        platform: The platform where the SDK is running. If not provided, it will be detected.

    Returns:
        A dictionary with the session attributes.
    """
    default_attributes = {
        "source": f"layer-python-sdk/{version}",
        "os": str(platform or get_platform()),
        "python.runtime": _get_python_runtime(),
        "python.runtime.version": _get_python_version(),
    }

    return {**default_attributes, **kubernetes_session_attributes()}


def kubernetes_session_attributes() -> Dict[str, str]:
    if not os.environ.get('KUBERNETES_SERVICE_HOST'):
        return {}

    kubernetes_info = {
        "kubernetes_pod_name": os.environ.get(
            'POD_NAME',
            os.environ.get('HOSTNAME')
        ),  # POD_NAME or fallback to HOSTNAME
        "kubernetes_pod_namespace": os.environ.get('POD_NAMESPACE'),
        "kubernetes_node_name": os.environ.get('NODE_NAME'),
    }

    return {k: v for k, v in kubernetes_info.items() if v}  # Filter out None values



def _get_python_runtime() -> str:
    try:
        return platform.python_implementation()
    except Exception:
        return "unknown"


def _get_python_version() -> str:
    try:
        return platform.python_version()
    except Exception:
        return "unknown"
