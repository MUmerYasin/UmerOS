from .utils import _read_file, parse_key_value_multi

def get() -> list[dict]:
    """Parse /proc/loadavg and return a dictionary with load averages.
    Returns keys: '1min', '5min', '15min', 'running', 'total', 'last_pid'.
    """
    raw = _read_file("/proc/loadavg")
    if not raw:
        return []
    parts = raw.strip().split()
    if len(parts) < 5:
        return []
    return [{
        "1min": float(parts[0]),
        "5min": float(parts[1]),
        "15min": float(parts[2]),
        "running": int(parts[3].split('/')[-2]),
        "total": int(parts[3].split('/')[-1]),
        "last_pid": int(parts[4])
    }]
