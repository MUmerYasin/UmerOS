"""Kernel modules wrapper: ``get()`` → list of module dicts."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/modules")
    if raw:
        mods = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 6:
                mods.append({
                    "name": parts[0], "size": int(parts[1]),
                    "usage": int(parts[2]), "deps": parts[3],
                    "state": parts[4], "offset": parts[5],
                })
        return mods
    return [
        {"name": "umer_net", "size": 61440, "usage": 3,
         "deps": "-", "state": "Live", "offset": "0x0000000000000000"},
        {"name": "qcrypto", "size": 36864, "usage": 1,
         "deps": "-", "state": "Live", "offset": "0x0000000000000000"},
        {"name": "qfs", "size": 131072, "usage": 2,
         "deps": "qcrypto", "state": "Live", "offset": "0x0000000000000000"},
        {"name": "procfs", "size": 16384, "usage": 1,
         "deps": "-", "state": "Live", "offset": "0x0000000000000000"},
    ]
