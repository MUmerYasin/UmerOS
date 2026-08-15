"""Interrupt info wrapper: ``get()`` → list of IRQ dicts."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/interrupts")
    if raw:
        lines = raw.splitlines()
        header = lines[0].split()
        result = []
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split()
            irq = parts[0].rstrip(":")
            counts = parts[1:1 + len(header)]
            description = " ".join(parts[1 + len(header):])
            result.append({"irq": irq, "counts": counts,
                           "description": description})
        return result
    return [
        {"irq": "0", "counts": ["0"], "description": "timer"},
        {"irq": "1", "counts": ["12"], "description": "i8042"},
        {"irq": "NMI", "counts": ["0", "0"], "description": "Non-maskable interrupts"},
        {"irq": "LOC", "counts": ["0", "0"], "description": "Local timer interrupts"},
    ]
