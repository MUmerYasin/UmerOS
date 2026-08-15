"""DMA channel wrapper: ``get()`` → list of DMA lines."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/dma")
    if raw:
        return [line.strip() for line in raw.splitlines() if line.strip()]
    return ["4: cascade"]
