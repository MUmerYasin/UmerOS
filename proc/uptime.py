from .utils import _read_file

def get():
    """Return uptime information similar to /proc/uptime as raw string."""
    return _read_file("/proc/uptime")
