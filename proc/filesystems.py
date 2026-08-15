"""Per-filesystem wrapper: ``get()`` → list of filesystem names."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/filesystems")
    if raw:
        return [line.split()[-1] for line in raw.splitlines() if line.strip()]
    return ["nodev/proc", "nodev/sysfs", "nodev/tmpfs", "qfs", "ext4"]
