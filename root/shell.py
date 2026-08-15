"""
Umer OS /root - shell environment
==================================
The environment that ``/root``-related processes expect to see.

The TLDP /root reference is short on the *contents* of root's
environment - it focuses on the directory layout - but the
"principle of least privilege" implies a few invariants we model
here:

* ``PATH`` is the system administrator's search path, with
  ``/sbin`` and ``/usr/sbin`` ahead of ``/bin`` and ``/usr/bin``.
* ``HOME`` is the resolved root home (we use
  :func:`root.home.RootHomeResolver.resolve`).
* ``SHELL`` defaults to ``/bin/bash`` unless ``/etc/passwd`` says
  otherwise.
* ``USER`` / ``LOGNAME`` are set to ``root``.
* ``PS1`` ends with a literal ``#`` (the historical root prompt).
* ``MAILCHECK`` is set to ``0`` because root's mail should be
  forwarded (see :mod:`root.mail`), not polled locally.
* ``LD_LIBRARY_PATH`` is empty by default - a hardening measure
  so root does not accidentally load libraries from a writable
  directory.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Root.Shell")


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

#: The canonical admin ``PATH``: local sbin directories first, then
#: the standard sbin, then the user binaries.  Mirrors Debian's
#: ``/etc/login.defs`` and Fedora's profile defaults.
DEFAULT_PATH: Tuple[str, ...] = (
    "/usr/local/sbin",
    "/usr/local/bin",
    "/usr/sbin",
    "/usr/bin",
    "/sbin",
    "/bin",
)

#: Shell chosen for root when ``/etc/passwd`` does not specify one.
DEFAULT_SHELL: str = "/bin/bash"

#: Hardening defaults.
HARDENED_DEFAULTS: Dict[str, str] = {
    "USER":    "root",
    "LOGNAME": "root",
    "PATH":    ":".join(DEFAULT_PATH),
    "SHELL":   DEFAULT_SHELL,
    "HOME":    "/root",
    "PS1":     r"\u@\h:\w# ",          # ends with literal '#' (root prompt)
    "MAILCHECK": "0",                  # mail is forwarded, not polled
    "ENV":     "/etc/umeros/root.env",
    "BASH_ENV": "/etc/umeros/root.bashrc",
    "LD_LIBRARY_PATH": "",            # empty - hardening measure
    "TMPDIR":  "/tmp",
    "EDITOR":  "vi",
    "PAGER":   "less",
    "LESS":    "-R",
}

#: Variables that should *not* be inherited by root.  Most distros do
#: not strip these explicitly, but UmerOS records them in the audit
#: so the operator can decide.
DANGEROUS_VARS: Tuple[str, ...] = (
    "LD_PRELOAD",
    "LD_AUDIT",
    "GCONV_PATH",
    "GETCONF_DIR",
    "HOSTALIASES",
    "LOCALDOMAIN",
    "RESOLV_HOST_CONF",
    "RES_OPTIONS",
    "TMPDIR",   # /tmp on multi-user systems is unsafe for root
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ShellEnvironment:
    """A root-friendly shell environment."""

    variables: Dict[str, str] = field(default_factory=dict)
    unset: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def as_env(self) -> Dict[str, str]:
        return dict(self.variables)

    def render(self) -> str:
        lines = [f"  {k}={v!r}" for k, v in self.variables.items()]
        if self.unset:
            lines.append("")
            lines.append("  unset:")
            for v in self.unset:
                lines.append(f"    {v}")
        if self.notes:
            lines.append("")
            lines.append("  notes:")
            for n in self.notes:
                lines.append(f"    - {n}")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class RootShellEnvironmentBuilder:
    """Builds the environment ``/root`` processes should run under.

    Three steps:

    1. Start from the hardened defaults in :data:`HARDENED_DEFAULTS`.
    2. Overlay any caller-supplied overrides (e.g. a custom
       ``PATH`` from a deployment script).
    3. Strip :data:`DANGEROUS_VARS` from the inheritance list and
       record what was removed in :attr:`ShellEnvironment.unset`.
    """

    def __init__(self,
                 shell: str = DEFAULT_SHELL,
                 home: str = "/root",
                 path: Optional[Tuple[str, ...]] = None) -> None:
        self.shell = shell
        self.home = home
        self.path = path or DEFAULT_PATH

    def build(self,
              overrides: Optional[Dict[str, str]] = None,
              *,
              inherit_from: Optional[Dict[str, str]] = None,
              strict: bool = True) -> ShellEnvironment:
        """Return a :class:`ShellEnvironment` ready to apply.

        ``inherit_from`` lets the caller pass ``os.environ`` (or a
        copy) to simulate what an actual login would see.  When
        ``strict`` is True (the default) the builder also records
        each :data:`DANGEROUS_VARS` it found in the inheritance so
        the audit can flag them.
        """
        env: Dict[str, str] = dict(HARDENED_DEFAULTS)
        env["SHELL"] = self.shell
        env["HOME"] = self.home
        env["PATH"] = ":".join(self.path)

        # Inherit, then sanitise.
        unset: List[str] = []
        notes: List[str] = []
        if inherit_from:
            for key, value in inherit_from.items():
                if strict and key in DANGEROUS_VARS and value:
                    unset.append(key)
                    continue
                # Caller-supplied overrides win over the inheritance
                # *and* over the defaults.
                if overrides and key in overrides:
                    continue
                env[key] = value

        # Apply overrides.
        if overrides:
            for key, value in overrides.items():
                env[key] = value

        if unset and strict:
            notes.append(
                f"stripped {len(unset)} dangerous variable(s) from inheritance: "
                f"{', '.join(unset)}"
            )

        return ShellEnvironment(
            variables=env, unset=unset, notes=notes,
        )

    def as_bash_exports(self) -> str:
        """Render the default environment as ``export`` lines for
        ``/etc/profile``-style consumption."""
        env = self.build()
        lines = ["# Umer OS /root default environment (generated)"]
        for key, value in env.variables.items():
            lines.append(f"export {key}={shlex.quote(value)}")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    b = RootShellEnvironmentBuilder()
    env = b.build()
    if env.variables["USER"] != "root":
        return False
    if env.variables["SHELL"] != DEFAULT_SHELL:
        return False
    if env.variables["PS1"].rstrip()[-1] != "#":
        return False
    if env.variables["PATH"].split(":")[0] != "/usr/local/sbin":
        return False
    if env.variables["LD_LIBRARY_PATH"] != "":
        return False
    # Inheriting a dangerous variable should strip it.
    env2 = b.build(inherit_from={"LD_PRELOAD": "/tmp/evil.so", "LANG": "C"})
    if "LD_PRELOAD" not in env2.unset:
        return False
    if env2.variables.get("LANG") != "C":
        return False
    # Overrides win.
    env3 = b.build(overrides={"PATH": "/custom/bin"})
    if env3.variables["PATH"] != "/custom/bin":
        return False
    # Bash export rendering.
    out = b.as_bash_exports()
    if "export USER=" not in out:
        return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("shell selftest:", "OK" if _selftest() else "FAIL")
