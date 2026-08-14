from .utils import _read_file

def get():
    """Return memory info similar to /proc/meminfo as raw string."""
    return _read_file("/proc/meminfo")
