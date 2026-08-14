from .utils import _read_file
from typing import List, Dict

def get() -> List[Dict[str, str]]:
    """Parse /proc/cpuinfo and return a list of dictionaries.
    Each dictionary corresponds to one logical processor.
    """
    raw = _read_file("/proc/cpuinfo")
    if not raw:
        return []
    processors: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            if current:
                processors.append(current)
                current = {}
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current[key.strip()] = value.strip()
    if current:
        processors.append(current)
    return processors
