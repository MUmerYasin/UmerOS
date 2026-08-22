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

from typing import Protocol, runtime_checkable, Dict, Any

# Global registry for character devices
CHAR_DEVICES: Dict[str, Any] = {}

@runtime_checkable
class FileOperations(Protocol):
    """Mimic file_operations for character devices."""
    def open(self, mode: str = "r") -> None: ...
    def read(self, size: int = -1) -> str: ...
    def write(self, data: str) -> int: ...
    def release(self) -> None: ...
