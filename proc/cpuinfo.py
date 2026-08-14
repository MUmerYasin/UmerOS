from .utils import _read_file

def get():
    """Return CPU info similar to /proc/cpuinfo as raw string."""
    return _read_file("/proc/cpuinfo")
