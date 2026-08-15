"""Per-partition wrapper: ``get()`` → list of partition dicts."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/partitions")
    if raw:
        parts = []
        for line in raw.splitlines()[2:]:
            if not line.strip():
                continue
            fields = line.split()
            if len(fields) == 4:
                parts.append({
                    "major": int(fields[0]), "minor": int(fields[1]),
                    "blocks": int(fields[2]), "name": fields[3],
                })
        return parts
    return [
        {"major": 254, "minor": 0, "blocks": 4194304, "name": "qfs_root"},
        {"major": 254, "minor": 16, "blocks": 2097152, "name": "qswap"},
    ]
