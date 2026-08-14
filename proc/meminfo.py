from .utils import _read_file
from typing import Dict

def get() -> Dict[str, str]:
    """Parse /proc/meminfo into a dict of key/value pairs.
    Values retain the original units (e.g., 'kB').
    """
    raw = _read_file("/proc/meminfo")
    info: Dict[str, str] = {}
    if not raw:
        return info
    for line in raw.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        info[key.strip()] = value.strip()
    return info
