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

"""Per-filesystem wrapper: ``get()`` → list of filesystem names."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/filesystems")
    if raw:
        return [line.split()[-1] for line in raw.splitlines() if line.strip()]
    return ["nodev/proc", "nodev/sysfs", "nodev/tmpfs", "qfs", "ext4"]
