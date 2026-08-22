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

"""
UmerOS Command Base Class
=========================
Base class for all bin/ commands.
"""

from __future__ import annotations

from typing import Any, List, Optional


class Command:
    """Base class for all UmerOS commands.

    Subclasses should define:
        name (str):            Command name as typed by the user.
        description (str):     One-line help text.
        category (str):        Category label (e.g. "file", "process").
        privileges (list):     Required privileges (e.g. ["user"], ["root"]).

    And override:
        execute(self, *args) -> Any
    """

    name: str = ""
    description: str = ""
    category: str = ""
    privileges: List[str] = []

    def execute(self, *args: Any) -> Any:
        """Run the command.  Override in subclasses."""
        raise NotImplementedError(f"{self.__class__.__name__}: execute() not implemented")
