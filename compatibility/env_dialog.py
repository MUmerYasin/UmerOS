"""
Umer OS /compatibility/env_dialog — the "Environment Variables" dialog
======================================================================

Windows exposes environment variables through a dialog reached from
*System Properties -> Advanced -> Environment Variables*.  It has two
sections:

* **User variables** -- apply to the signed-in profile only.
  Persisted in ``HKCU\\Environment``.
* **System variables** -- apply to every user on the machine.
  Persisted in ``HKLM\\...\\Session Manager\\Environment``.

The dialog lets you *add* a variable, *edit* an existing one or *remove*
it.  The ``Path`` variable is edited differently: it is shown as a
**list of directories** with *New*, *Edit*, *Delete*, *Move Up* and
*Move Down*, rather than as one long string.

This module models that dialog in pure Python so an installer (or a
headless provisioning tool) can make exactly the same changes the GUI
would make, with the same validation and the same side effects.

Reference behaviour encoded here
--------------------------------

* ``Path`` is stored as ``REG_EXPAND_SZ`` so ``%SystemRoot%`` entries
  keep working.
* The dialog displays at most **4095** characters of a value.  A longer
  value is **truncated permanently** when *OK* is pressed.
* A ``Path`` longer than **2048** characters is a known hazard: the
  ``Shell32.dll`` handler for ``WM_SETTINGCHANGE`` assumes the old
  2048-character limit and rebuilds a partially initialised
  environment block, which shows up as ``%windir% not found``.
* *Cancel* discards every pending change; *OK* writes them to the
  registry and notifies running applications.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/shell/environment-variables
* https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-settingchange
* https://support.microsoft.com/en-us/servicing/os/windows/2017/01/error-messages-after-you-change-the-2047-character-limit-in-an-environment-variable-on-a-computer-th
* https://learn.microsoft.com/en-us/windows/win32/sysinfo/registry-value-types

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.EnvDialog")

#: The largest value the dialog will display.  Anything longer is
#: truncated when the user presses *OK*.
MAX_DIALOG_VALUE_LENGTH = 4095

#: The pre-hotfix limit.  Still the limit on unpatched systems.
LEGACY_MAX_VALUE_LENGTH = 2047

#: The length beyond which ``Shell32.dll`` fails to rebuild the
#: environment block after a ``WM_SETTINGCHANGE`` broadcast.
SHELL_SAFE_PATH_LENGTH = 2048


class DialogScope(Enum):
    """The two sections of the Environment Variables dialog."""

    USER = "user"
    SYSTEM = "system"

    @property
    def registry_key(self) -> str:
        """The registry key that persists this section."""
        if self is DialogScope.USER:
            return r"HKCU\Environment"
        return (r"HKLM\SYSTEM\CurrentControlSet\Control"
                r"\Session Manager\Environment")

    @property
    def title(self) -> str:
        """The label the dialog uses for this section."""
        return "User variables" if self is DialogScope.USER \
            else "System variables"


# ---------------------------------------------------------------------------
# The PATH list
# ---------------------------------------------------------------------------

@dataclass
class PathEditor:
    """The list-of-directories model the dialog uses for ``Path``.

    Windows stores ``Path`` as one ``;``-separated string, but the
    dialog shows it as a list of directories.  This class keeps the
    entry list as the source of truth and converts to and from the
    string form.
    """

    entries: List[str] = field(default_factory=list)

    # -- conversion ----------------------------------------------------

    @classmethod
    def from_value(cls, value: str) -> "PathEditor":
        """Split a ``;``-separated ``Path`` into its entries.

        Blank entries are preserved: the dialog shows them and a
        round-trip must not silently drop them.
        """
        if not value:
            return cls([])
        return cls(value.split(";"))

    def to_value(self) -> str:
        """Render the entries back into the ``;``-separated form."""
        return ";".join(self.entries)

    # -- editing -------------------------------------------------------

    def add(self, entry: str, index: Optional[int] = None) -> bool:
        """Insert a directory.  Returns ``False`` if it is already there."""
        entry = entry.strip()
        if not entry:
            return False
        if self._index_of(entry) is not None:
            return False
        if index is None or index >= len(self.entries):
            self.entries.append(entry)
        else:
            self.entries.insert(max(0, index), entry)
        return True

    def remove(self, index: int) -> bool:
        """Delete the directory at ``index``."""
        if not 0 <= index < len(self.entries):
            return False
        del self.entries[index]
        return True

    def edit(self, index: int, value: str) -> bool:
        """Replace the directory at ``index``."""
        if not 0 <= index < len(self.entries):
            return False
        value = value.strip()
        if not value:
            return False
        self.entries[index] = value
        return True

    def move_up(self, index: int) -> bool:
        """Move the directory at ``index`` one place up."""
        if not 0 <= index < len(self.entries):
            return False
        if index == 0:
            return False
        self.entries[index - 1], self.entries[index] = \
            self.entries[index], self.entries[index - 1]
        return True

    def move_down(self, index: int) -> bool:
        """Move the directory at ``index`` one place down."""
        if not 0 <= index < len(self.entries):
            return False
        if index >= len(self.entries) - 1:
            return False
        self.entries[index + 1], self.entries[index] = \
            self.entries[index], self.entries[index + 1]
        return True

    def _index_of(self, entry: str) -> Optional[int]:
        low = entry.lower().rstrip("\\")
        for i, existing in enumerate(self.entries):
            if existing.strip().lower().rstrip("\\") == low:
                return i
        return None

    # -- analysis ------------------------------------------------------

    def contains_expandable(self) -> bool:
        """``True`` when any entry carries a ``%VAR%`` reference."""
        return any("%" in e for e in self.entries)

    def length(self) -> int:
        """The length of the rendered value."""
        return len(self.to_value())

    def too_long_for_shell(self) -> bool:
        """``True`` when the rendered value risks the Shell32 bug."""
        return self.length() > SHELL_SAFE_PATH_LENGTH

    def over_dialog_limit(self) -> bool:
        """``True`` when the dialog would truncate the value."""
        return self.length() > MAX_DIALOG_VALUE_LENGTH


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------

@dataclass
class VariableChange:
    """One pending edit, as shown in the dialog's summary."""

    scope: DialogScope
    name: str
    old_value: Optional[str]
    new_value: Optional[str]
    truncated: bool = False

    @property
    def kind(self) -> str:
        """``added`` / ``edited`` / ``removed``."""
        if self.old_value is None:
            return "added"
        if self.new_value is None:
            return "removed"
        return "edited"


@dataclass
class DialogResult:
    """The outcome of pressing *OK*."""

    changes: List[VariableChange] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notified: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.changes)


class EnvironmentDialog:
    """A model of the Windows *Environment Variables* dialog.

    The dialog edits a **copy** of the environment.  Nothing is written
    until :meth:`apply` is called (the *OK* button); :meth:`cancel`
    throws the copy away (the *Cancel* button).

    Example
    -------
    >>> from compatibility.environment import ScopedEnvironment, EnvScope
    >>> env = ScopedEnvironment(host_fallback=False)
    >>> dlg = EnvironmentDialog(env)
    >>> dlg.add(DialogScope.USER, "MYAPP", r"C:\\Program Files\\MyApp")
    True
    >>> result = dlg.apply()
    >>> result.changed
    True
    """

    def __init__(self, env=None, store=None) -> None:
        from .environment import EnvScope, ScopedEnvironment   # local: avoid cycle
        self._env = env if env is not None else ScopedEnvironment(
            host_fallback=False)
        self._store = store
        self._pending: Dict[DialogScope, Dict[str, Tuple[Optional[str], str]]] = {
            DialogScope.USER: {},
            DialogScope.SYSTEM: {},
        }
        self._original = {
            DialogScope.USER: dict(self._env.user.to_dict()),
            DialogScope.SYSTEM: dict(self._env.system.to_dict()),
        }

    # ------------------------------------------------------------------
    # Reading the two sections
    # ------------------------------------------------------------------

    def variables(self, scope: DialogScope) -> Dict[str, str]:
        """The variables of one section, including pending edits.

        Keys are upper-cased (Windows variable names are
        case-insensitive) while the values are untouched.
        """
        from .environment import EnvScope    # local: avoid cycle
        env_scope = (EnvScope.USER if scope is DialogScope.USER
                     else EnvScope.SYSTEM)
        base = {k.upper(): v
                for k, v in self._env.table(env_scope).to_dict().items()}
        for name, (_old, new) in self._pending[scope].items():
            if new is None:
                base.pop(name.upper(), None)
            else:
                base[name.upper()] = new
        return base

    def user_variables(self) -> Dict[str, str]:
        """The *User variables* section."""
        return self.variables(DialogScope.USER)

    def system_variables(self) -> Dict[str, str]:
        """The *System variables* section."""
        return self.variables(DialogScope.SYSTEM)

    def get(self, scope: DialogScope, name: str) -> Optional[str]:
        """The current value of one variable."""
        return self.variables(scope).get(name.upper())

    def path_editor(self, scope: DialogScope) -> PathEditor:
        """The ``Path`` variable of a section, as a directory list."""
        value = self.get(scope, "Path") or ""
        return PathEditor.from_value(value)

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def add(self, scope: DialogScope, name: str, value: str) -> bool:
        """*New* -- define a variable that does not exist yet."""
        from .environment import is_valid_variable_name   # local: avoid cycle
        if not is_valid_variable_name(name):
            return False
        if name.upper() in self.variables(scope):
            return False
        self._pending[scope][name.upper()] = (None, value)
        return True

    def edit(self, scope: DialogScope, name: str, value: str) -> bool:
        """*Edit* -- change an existing variable."""
        from .environment import is_valid_variable_name   # local: avoid cycle
        if not is_valid_variable_name(name):
            return False
        current = self.get(scope, name)
        if current is None:
            return False
        self._pending[scope][name.upper()] = (current, value)
        return True

    def remove(self, scope: DialogScope, name: str) -> bool:
        """*Delete* -- remove a variable."""
        current = self.get(scope, name)
        if current is None:
            return False
        self._pending[scope][name.upper()] = (current, None)
        return True

    def set_path(self, scope: DialogScope, editor: PathEditor) -> bool:
        """Replace the ``Path`` variable with the editor's contents."""
        return self.edit(scope, "Path", editor.to_value())

    # ------------------------------------------------------------------
    # Committing
    # ------------------------------------------------------------------

    def _truncate(self, scope: DialogScope, name: str, value: str
                 ) -> Tuple[str, bool]:
        """Apply the dialog's 4095-character display limit."""
        if len(value) <= MAX_DIALOG_VALUE_LENGTH:
            return value, False
        return value[:MAX_DIALOG_VALUE_LENGTH], True

    def apply(self) -> DialogResult:
        """*OK* -- commit every pending edit.

        The changes are written to the in-memory environment, and to the
        registry when a store was supplied.  A ``WM_SETTINGCHANGE``
        broadcast is then issued so running applications can pick the
        new values up.
        """
        from .environment import EnvScope   # local: avoid cycle
        result = DialogResult()

        for scope in (DialogScope.USER, DialogScope.SYSTEM):
            env_scope = (EnvScope.USER if scope is DialogScope.USER
                         else EnvScope.SYSTEM)
            for key, (old, new) in self._pending[scope].items():
                truncated = False
                if new is not None:
                    new, truncated = self._truncate(scope, key, new)
                    if truncated:
                        result.warnings.append(
                            f"{scope.title}: '{key}' was truncated to "
                            f"{MAX_DIALOG_VALUE_LENGTH} characters")
                change = VariableChange(scope=scope, name=key,
                                        old_value=old, new_value=new,
                                        truncated=truncated)
                result.changes.append(change)

                # Write through to the live environment.
                if new is None:
                    self._env.unset(key, env_scope)
                else:
                    self._env.set(key, new, env_scope)

                # Persist the two persistent scopes.
                if self._store is not None:
                    if new is None:
                        self._store.unset(scope.value, key)
                    else:
                        self._store.set(scope.value, key, new)

            # Warn about the Shell32 long-PATH hazard.
            path_value = self.get(scope, "Path")
            if path_value and len(path_value) > SHELL_SAFE_PATH_LENGTH:
                result.warnings.append(
                    f"{scope.title}: 'Path' is {len(path_value)} characters; "
                    f"values longer than {SHELL_SAFE_PATH_LENGTH} can prevent "
                    f"the shell from rebuilding the environment block")

        if result.changed:
            from .environment import broadcast_environment_change
            result.notified = broadcast_environment_change()
            self._pending = {DialogScope.USER: {}, DialogScope.SYSTEM: {}}
            self._original = {
                DialogScope.USER: dict(self._env.user.to_dict()),
                DialogScope.SYSTEM: dict(self._env.system.to_dict()),
            }
        return result

    def cancel(self) -> None:
        """*Cancel* -- discard every pending edit."""
        self._pending = {DialogScope.USER: {}, DialogScope.SYSTEM: {}}

    def pending_count(self) -> int:
        """How many edits are waiting to be committed."""
        return sum(len(v) for v in self._pending.values())


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    from .environment import EnvScope, ScopedEnvironment   # local: avoid cycle

    # 1. The two sections are independent.
    env = ScopedEnvironment(host_fallback=False)
    env.set("Machine", r"C:\Machine", EnvScope.SYSTEM)
    env.set("OnlyMe", r"C:\User", EnvScope.USER)
    dlg = EnvironmentDialog(env)
    if dlg.get(DialogScope.SYSTEM, "Machine") != r"C:\Machine":
        return False
    if dlg.get(DialogScope.USER, "OnlyMe") != r"C:\User":
        return False
    if dlg.get(DialogScope.USER, "Machine") is not None:
        return False

    # 2. Add / edit / remove.
    if not dlg.add(DialogScope.USER, "NEWVAR", "v"):
        return False
    if dlg.get(DialogScope.USER, "NEWVAR") != "v":
        return False
    if dlg.add(DialogScope.USER, "NEWVAR", "v2"):
        return False          # already exists
    if not dlg.edit(DialogScope.USER, "NEWVAR", "v2"):
        return False
    if dlg.get(DialogScope.USER, "NEWVAR") != "v2":
        return False
    if not dlg.remove(DialogScope.USER, "NEWVAR"):
        return False
    if dlg.get(DialogScope.USER, "NEWVAR") is not None:
        return False

    # 3. Cancel discards everything.
    dlg.add(DialogScope.USER, "GONE", "x")
    dlg.cancel()
    if dlg.pending_count() != 0:
        return False
    if dlg.get(DialogScope.USER, "GONE") is not None:
        return False

    # 4. OK commits and the live environment sees it.
    dlg.add(DialogScope.USER, "KEPT", "yes")
    result = dlg.apply()
    if not result.changed:
        return False
    if env.get("KEPT") != "yes":
        return False

    # 5. The PATH editor round-trips.
    editor = PathEditor.from_value(r"C:\A;C:\B;C:\C")
    if editor.entries != [r"C:\A", r"C:\B", r"C:\C"]:
        return False
    if not editor.move_up(2):
        return False
    if editor.entries != [r"C:\A", r"C:\C", r"C:\B"]:
        return False
    if not editor.move_down(0):
        return False
    if editor.entries != [r"C:\C", r"C:\A", r"C:\B"]:
        return False
    if editor.add(r"C:\A"):
        return False          # duplicate
    if not editor.add(r"C:\D"):
        return False
    if editor.to_value() != r"C:\C;C:\A;C:\B;C:\D":
        return False

    # 6. Blank entries survive a round-trip.
    blank = PathEditor.from_value(r"C:\A;;C:\B")
    if len(blank.entries) != 3:
        return False

    # 7. The dialog truncates over-long values.
    dlg2 = EnvironmentDialog(ScopedEnvironment(host_fallback=False))
    dlg2.add(DialogScope.USER, "LONG", "x" * 5000)
    res2 = dlg2.apply()
    if not res2.changes:
        return False
    if not res2.changes[0].truncated:
        return False
    if len(res2.changes[0].new_value or "") != MAX_DIALOG_VALUE_LENGTH:
        return False
    if not res2.warnings:
        return False

    # 8. A long Path raises the Shell32 warning.
    dlg3 = EnvironmentDialog(ScopedEnvironment(host_fallback=False))
    long_path = ";".join(r"C:\Dir%03d" % i for i in range(300))
    if len(long_path) <= SHELL_SAFE_PATH_LENGTH:
        return False
    dlg3.add(DialogScope.SYSTEM, "Path", long_path)
    res3 = dlg3.apply()
    if not any("Path" in w for w in res3.warnings):
        return False

    # 9. A short Path does not.
    dlg4 = EnvironmentDialog(ScopedEnvironment(host_fallback=False))
    dlg4.add(DialogScope.SYSTEM, "Path", r"C:\A;C:\B")
    res4 = dlg4.apply()
    if any("Path" in w for w in res4.warnings):
        return False

    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
