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

"""/proc/uptime — system uptime wrapper.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

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
