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

from .utils import _read_file, parse_key_value_multi

def get() -> list[dict]:
    """Parse /proc/loadavg and return a dictionary with load averages.
    Returns keys: '1min', '5min', '15min', 'running', 'total', 'last_pid'.
    """
    raw = _read_file("/proc/loadavg")
    if not raw:
        return []
    parts = raw.strip().split()
    if len(parts) < 5:
        return []
    return [{
        "1min": float(parts[0]),
        "5min": float(parts[1]),
        "15min": float(parts[2]),
        "running": int(parts[3].split('/')[-2]),
        "total": int(parts[3].split('/')[-1]),
        "last_pid": int(parts[4])
    }]
