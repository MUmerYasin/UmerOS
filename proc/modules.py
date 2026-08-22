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
