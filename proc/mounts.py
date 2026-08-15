"""Mount table wrapper: ``get()`` → list of mount dicts."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/mounts")
    if raw:
        mounts = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                mounts.append({
                    "device": parts[0], "mountpoint": parts[1],
                    "fstype": parts[2],
                })
        return mounts
    return [
        {"device": "qfs_root", "mountpoint": "/", "fstype": "qfs"},
        {"device": "proc", "mountpoint": "/proc", "fstype": "proc"},
        {"device": "sysfs", "mountpoint": "/sys", "fstype": "sysfs"},
        {"device": "devtmpfs", "mountpoint": "/dev", "fstype": "devtmpfs"},
    ]
