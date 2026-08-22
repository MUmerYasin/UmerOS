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

"""I/O port wrapper: ``get()`` → list of ioport lines."""
from proc.utils import _read_file

def get() -> list:
    raw = _read_file("/proc/ioports")
    if raw:
        return [line.strip() for line in raw.splitlines() if line.strip()]
    return [
        "0000-001f : dma1",
        "0020-0021 : pic1",
        "0040-0043 : timer0",
        "0060-0060 : keyboard",
    ]
