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

"""Per-partition wrapper: ``get()`` → list of partition dicts."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/partitions")
    if raw:
        parts = []
        for line in raw.splitlines()[2:]:
            if not line.strip():
                continue
            fields = line.split()
            if len(fields) == 4:
                parts.append({
                    "major": int(fields[0]), "minor": int(fields[1]),
                    "blocks": int(fields[2]), "name": fields[3],
                })
        return parts
    return [
        {"major": 254, "minor": 0, "blocks": 4194304, "name": "qfs_root"},
        {"major": 254, "minor": 16, "blocks": 2097152, "name": "qswap"},
    ]
