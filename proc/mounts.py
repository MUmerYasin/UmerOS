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

"""Mount table wrapper: ``get()`` → list of mount dicts."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/mounts")
    if raw:
        mounts = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                mounts.append({
                    "device": parts[0], "mountpoint": parts[1],
                    "fstype": parts[2],
                })
        return mounts
    return [
        {"device": "qfs_root", "mountpoint": "/", "fstype": "qfs"},
        {"device": "proc", "mountpoint": "/proc", "fstype": "proc"},
        {"device": "sysfs", "mountpoint": "/sys", "fstype": "sysfs"},
        {"device": "devtmpfs", "mountpoint": "/dev", "fstype": "devtmpfs"},
    ]
