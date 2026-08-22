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

from .utils import _read_file
from typing import Dict

def get() -> Dict[str, str]:
    """Parse /proc/meminfo into a dict of key/value pairs.
    Values retain the original units (e.g., 'kB').
    """
    raw = _read_file("/proc/meminfo")
    info: Dict[str, str] = {}
    if not raw:
        return info
    for line in raw.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        info[key.strip()] = value.strip()
    return info
