"""Swap device wrapper: ``get()`` → list of swap dicts."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/swaps")
    if raw:
        swaps = []
        for line in raw.splitlines()[1:]:
            if not line.strip():
                continue
            fields = line.split()
            if len(fields) >= 5:
                swaps.append({
                    "filename": fields[0], "type": fields[1],
                    "size": int(fields[2]), "used": int(fields[3]),
                    "priority": int(fields[4]),
                })
        return swaps
    return [{"filename": "/dev/qswap", "type": "partition",
             "size": 2097144, "used": 0, "priority": -2}]
