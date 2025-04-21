from importlib import metadata

try:
    __version__ = metadata.version("protectai-layer-sdk") or ""  # type: ignore
except metadata.PackageNotFoundError:
    __version__ = ""
