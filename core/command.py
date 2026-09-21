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
import logging

from typing import Callable, List, Optional
log = logging.getLogger("UmerOS.Core.Command")
EXIT_PERMISSION_DENIED = 77  # sysexits.h EX_NOPERM
# [TODAY] UmerOS command base class - the live, canonical Command contract (H57 tier label).


class Command:
    """Base class for all UmerOS commands.

    Canonical command contract (adopted convention):
        execute(self, args: Optional[List[str]] = None) -> int
    `args` is the argv list (excluding argv[0]); the return value is a POSIX-style
    exit code (0 == success). The base previously declared
    `execute(self, *args: Any) -> Any`, which contradicted the dominant `bin/`
    convention and let subclasses drift. We converge the base to the
    adopted contract so every `bin/*` subclass agrees on the signature.

    Subclasses should define:
        name (str):            Command name as typed by the user.
        description (str):     One-line help text.
        category (str):        Category label (e.g. "file", "process").
        privileges (list):     Required privileges (e.g. ["user"], ["root"]).
                              `privileges` is enforced fail-closed by `run()` / `check_privileges()`
                               callers pass a `has_privilege` verifier (wired to
                              `CapabilityManager` / `Credentials`); unverifiable privileged
                              commands are denied by default and never run un-gated.

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

        Adopted contract: `args` is the argument list (argv without
        argv[0]); returns a POSIX exit code (int). Subclasses must override this.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}: execute(args: Optional[List[str]] = None) -> int not implemented"
        )

    def check_privileges(self, has_privilege: Optional[Callable[[str], bool]]) -> bool:
        """Fail-closed privilege gate for this command.

        Returns ``True`` only when the command may run for the
        current principal:
          * no ``privileges`` declared -> always allowed (unprivileged);
          * ``has_privilege`` is ``None``  -> DENY (no verifier wired);
          * otherwise -> every required privilege in ``self.privileges``
            must satisfy ``has_privilege(priv)`` (logical AND).

        ``has_privilege`` is a ``Callable[[str], bool]`` supplied by the
        caller (typically wired to ``CapabilityManager`` / ``Credentials``);
        the base stays decoupled from any specific privilege backend.
        """
        if not self.privileges:
            return True
        if has_privilege is None:
            return False
        return all(bool(has_privilege(p)) for p in self.privileges)

    def run(self, args: Optional[List[str]] = None,
            has_privilege: Optional[Callable[[str], bool]] = None) -> int:
        """Privilege-gated entry point.

        Refuses execution (returns ``EXIT_PERMISSION_DENIED`` /
        ``EX_NOPERM`` = 77) when :meth:`check_privileges` fails, otherwise
        delegates to :meth:`execute`. Callers that need enforcement should
        use ``run()`` and pass a ``has_privilege`` verifier; ``execute()``
        itself remains the capability-agnostic contract locked by H55/tests.
        """
        if not self.check_privileges(has_privilege):
            log.warning(
                "Command %s denied: caller lacks required privileges %s",
                self.name or self.__class__.__name__, self.privileges,
            )
            return EXIT_PERMISSION_DENIED
        return self.execute(args)