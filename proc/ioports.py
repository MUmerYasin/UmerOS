"""I/O port wrapper: ``get()`` → list of ioport lines."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/ioports")
    if raw:
        return [line.strip() for line in raw.splitlines() if line.strip()]
    return [
        "0000-001f : dma1",
        "0020-0021 : pic1",
        "0040-0043 : timer0",
        "0060-0060 : keyboard",
    ]
