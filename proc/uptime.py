from .utils import _read_file, parse_key_value

def get() -> dict:
    """Parse /proc/uptime into a dict with 'total' and 'idle' seconds (float)."""
    raw = _read_file("/proc/uptime")
    if not raw:
        return {}
    parts = raw.strip().split()
    if len(parts) >= 2:
        return {"total": float(parts[0]), "idle": float(parts[1])}
    return {}
