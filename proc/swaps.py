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
