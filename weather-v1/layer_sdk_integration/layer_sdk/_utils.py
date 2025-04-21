import importlib.metadata
from typing import Optional

from packaging import version


def is_module_version_more_than(module_name: str, version_spec: str) -> Optional[bool]:
    """Check if the installed version of a module is less than the specified version.

    Parameters:
        module_name (str): The name of the module to check.
        version_spec (str): The version to compare against in the format
        'major.minor.patch'.

    Returns:
        bool: True if the installed version is less than the specified version,
        False otherwise.
    """
    installed_version = get_module_version(module_name)
    if not installed_version:
        return None

    return version.parse(installed_version) >= version.parse(version_spec)


def get_module_version(module_name: str) -> Optional[str]:
    """Get the installed version of a module.

    Parameters:
        module_name (str): The name of the module to check.

    Returns:
        str: The installed version of the module.
    """
    try:
        return importlib.metadata.version(module_name)
    except importlib.metadata.PackageNotFoundError:
        return None
