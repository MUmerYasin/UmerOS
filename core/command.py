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
