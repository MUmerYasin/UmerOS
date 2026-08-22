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
Umer OS /root - mail forwarding
================================
Implements the TLDP /root requirement that administrative mail should
*not* be stored inside root's home directory and should instead be
forwarded to a non-root user.

The mechanism is the classic ``~/.forward`` file, as understood by
``sendmail``, ``postfix`` and ``exim``: the first non-comment line
of ``~/.forward`` is the destination address.  The same file can
contain multiple addresses (one per line) or pipe-to-program
syntax (``| /usr/bin/procmail``) but for the UmerOS root account
we only need the simple forward case.

This module is a *policy* module: it does not talk to a real MTA.
It generates, validates, and audits ``~/.forward``.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("UmerOS.Root.Mail")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Filename (relative to root's home) the MTA looks for.
FORWARD_FILENAME: str = ".forward"

#: A reasonable local-part validation - good enough for ``.forward``
#: sanity checks; the MTA does the real validation.
_LOCAL_RE = re.compile(r"^[A-Za-z0-9._%+-]{1,64}$")
_DOMAIN_RE = re.compile(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

#: Administrative roles the TLDP /root page calls out specifically.
ADMIN_ROLES: tuple = (
    "root",
    "postmaster",
    "webmaster",
    "abuse",
    "security",
    "admin",
)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ForwardEntry:
    """One non-comment line of a ``.forward`` file."""

    raw: str
    address: str = ""
    kind: str = "local"            # "local" | "remote" | "pipe" | "file" | "?"
    valid: bool = True
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "raw":     self.raw,
            "address": self.address,
            "kind":    self.kind,
            "valid":   self.valid,
            "note":    self.note,
        }


@dataclass
class ForwardReport:
    """The audit result of a ``.forward`` file."""

    path: str
    exists: bool
    mode: int = 0
    entries: List[ForwardEntry] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    forwards_to: str = ""

    def as_dict(self) -> dict:
        return {
            "path":         self.path,
            "exists":       self.exists,
            "mode":         oct(self.mode),
            "entries":      [e.as_dict() for e in self.entries],
            "issues":       list(self.issues),
            "forwards_to":  self.forwards_to,
        }


# ---------------------------------------------------------------------------
# Parser / writer
# ---------------------------------------------------------------------------

class ForwardParser:
    """Parse a ``~/.forward`` file into :class:`ForwardEntry` rows."""

    @staticmethod
    def parse(text: str) -> List[ForwardEntry]:
        out: List[ForwardEntry] = []
        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            entry = ForwardParser._classify(stripped)
            out.append(entry)
        return out

    @staticmethod
    def _classify(line: str) -> ForwardEntry:
        if line.startswith("|"):
            return ForwardEntry(
                raw=line,
                address=line[1:].strip(),
                kind="pipe",
                valid=bool(line[1:].strip()),
                note="" if line[1:].strip() else "empty pipe target",
            )
        if line.startswith("/"):
            return ForwardEntry(
                raw=line, address=line, kind="file",
                valid=line.endswith("/"),
                note="" if line.endswith("/") else "file forwards must end with '/'",
            )
        if "@" in line:
            local, _, domain = line.partition("@")
            valid = bool(_LOCAL_RE.match(local)) and bool(_DOMAIN_RE.match(domain))
            return ForwardEntry(
                raw=line, address=line, kind="remote",
                valid=valid,
                note="" if valid else "malformed email address",
            )
        if _LOCAL_RE.match(line):
            return ForwardEntry(raw=line, address=line, kind="local", valid=True)
        return ForwardEntry(
            raw=line, address=line, kind="?",
            valid=False, note="unrecognised forward target",
        )


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class RootMailForwarder:
    """Manage the ``~/.forward`` file inside root's home."""

    def __init__(self, home: str) -> None:
        self.home = Path(home)
        self.path = self.home / FORWARD_FILENAME

    # -- read / audit ---------------------------------------------------

    def audit(self) -> ForwardReport:
        report = ForwardReport(path=str(self.path), exists=False)
        if not self.path.is_file():
            report.issues.append(f"{self.path} does not exist - "
                                 "root mail will land in /var/mail/root")
            return report
        report.exists = True
        import stat
        st = self.path.stat()
        report.mode = stat.S_IMODE(st.st_mode)
        if report.mode & 0o077:
            report.issues.append(
                f"mode is {oct(report.mode)} (world/group readable); expected 0600"
            )
        try:
            text = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            report.issues.append(f"read failed: {exc}")
            return report
        report.entries = ForwardParser.parse(text)
        valid_entries = [e for e in report.entries if e.valid]
        if not valid_entries:
            report.issues.append("no valid forward entry found")
        else:
            report.forwards_to = valid_entries[0].address
            if valid_entries[0].kind == "local" and valid_entries[0].address == "root":
                report.issues.append(
                    "forward destination is 'root' - this is a loop, mail stays on the system"
                )
        return report

    # -- write ---------------------------------------------------------

    def ensure(self, address: str, *, comment: Optional[str] = None) -> ForwardReport:
        """Create or replace the ``.forward`` file with one entry."""
        if not address:
            raise ValueError("address must not be empty")
        lines = []
        if comment:
            lines.append(f"# {comment}")
        lines.append(address)
        text = "\n".join(lines) + "\n"
        self.home.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")
        try:
            import stat
            os_chmod = getattr(self.path, "chmod", None)
            if os_chmod is None:
                import os
                os.chmod(self.path, 0o600)
            else:
                os_chmod(0o600)
        except OSError as exc:
            log.warning("could not chmod %s: %s", self.path, exc)
        return self.audit()

    # -- admin role table ----------------------------------------------

    def admin_role_forwards(self, mapping: Optional[dict] = None) -> dict:
        """Return a recommended ``{role: address}`` table.

        Default mapping uses ``admin@localhost`` for every role -
        operators typically want to override this per-deployment.
        """
        m = dict(mapping or {})
        for role in ADMIN_ROLES:
            m.setdefault(role, "admin@localhost")
        return m

    # -- render --------------------------------------------------------

    def render(self, report: ForwardReport) -> str:
        lines = [f"Umer OS /root mail forward   ({report.path})"]
        lines.append("=" * 50)
        if not report.exists:
            lines.append("  (no .forward file - root mail goes to /var/mail/root)")
            return "\n".join(lines) + "\n"
        lines.append(f"  mode:        {oct(report.mode)}")
        lines.append(f"  forwards to: {report.forwards_to or '(none valid)'}")
        lines.append(f"  entries:     {len(report.entries)}")
        for entry in report.entries:
            mark = "OK" if entry.valid else "BAD"
            lines.append(f"    [{mark}] {entry.raw}  ({entry.kind})")
        if report.issues:
            lines.append("")
            lines.append("  issues:")
            for issue in report.issues:
                lines.append(f"    - {issue}")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    import tempfile
    # 1. Parser.
    entries = ForwardParser.parse(
        "# admin forward\n"
        "admin@example.com\n"
        "  postmaster@example.com  \n"
        "| /usr/bin/procmail\n"
        "/var/spool/mail/root/\n"
    )
    kinds = [e.kind for e in entries]
    if "remote" not in kinds or "pipe" not in kinds or "file" not in kinds:
        return False
    if not all(e.valid for e in entries):
        return False
    # Malformed email is invalid.
    bad = ForwardParser.parse("nope@bad\n")[0]
    if bad.valid:
        return False
    # 2. Manager round-trip.
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        fm = RootMailForwarder(home=str(home))
        report = fm.audit()
        if report.exists:
            return False
        if not any("does not exist" in i for i in report.issues):
            return False
        report2 = fm.ensure("admin@example.com", comment="primary admin")
        if not report2.exists:
            return False
        if report2.forwards_to != "admin@example.com":
            return False
        if not all(e.valid for e in report2.entries):
            return False
        # Loop detection.
        fm.ensure("root")
        loop_report = fm.audit()
        if not any("loop" in i for i in loop_report.issues):
            return False
        # Admin table.
        table = fm.admin_role_forwards()
        if "root" not in table or "postmaster" not in table:
            return False
        # Render table.
        text = fm.render(report2)
        if "Umer OS /root mail forward" not in text:
            return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("mail selftest:", "OK" if _selftest() else "FAIL")
