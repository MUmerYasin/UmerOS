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
from typing import List, Dict

def get() -> List[Dict[str, str]]:
    """Parse /proc/cpuinfo and return a list of dictionaries.
    Each dictionary corresponds to one logical processor.
    """
    raw = _read_file("/proc/cpuinfo")
    if not raw:
        return []
    processors: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            if current:
                processors.append(current)
                current = {}
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current[key.strip()] = value.strip()
    if current:
        processors.append(current)
    return processors
