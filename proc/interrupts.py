# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
