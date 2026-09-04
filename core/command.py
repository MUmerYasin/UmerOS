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

from typing import List, Optional


class Command:
    """Base class for all UmerOS commands.

    [FIX H6 / H55] Canonical command contract (adopted convention):
        execute(self, args: Optional[List[str]] = None) -> int
    `args` is the argv list (excluding argv[0]); the return value is a POSIX-style
    exit code (0 == success). The base previously declared
    `execute(self, *args: Any) -> Any`, which contradicted the dominant `bin/`
    convention and let subclasses drift (see H35). We converge the base to the
    adopted contract so every `bin/*` subclass agrees on the signature.

    Subclasses should define:
        name (str):            Command name as typed by the user.
        description (str):     One-line help text.
        category (str):        Category label (e.g. "file", "process").
        privileges (list):     Required privileges (e.g. ["user"], ["root"]).
                              NOTE: `privileges` is declared but NOT yet enforced by
                              the base (see H56) — enforcement is a separate follow-up.

    And override:
        execute(self, args: Optional[List[str]] = None) -> int
    Optional `stdin`/`stdout` parameters are permitted as extensions for
    stream-oriented commands, but the minimal contract is the argv + int form.
    """

    name: str = ""
    description: str = ""
    category: str = ""
    privileges: List[str] = []

    def execute(self, args: Optional[List[str]] = None) -> int:
        """Run the command. Override in subclasses.

        [FIX H6 / H55] Adopted contract: `args` is the argument list (argv without
        argv[0]); returns a POSIX exit code (int). Subclasses must override this.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}: execute(args: Optional[List[str]] = None) -> int not implemented"
        )
