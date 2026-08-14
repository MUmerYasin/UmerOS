from .utils import _read_file, parse_key_value

def get() -> str:
    """Return the raw contents of /proc/version as a string."""
    return _read_file("/proc/version")
