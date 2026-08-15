"""
Umer OS /root - safety auditor
==============================
The TLDP /root reference is short on *what* root may run but very
clear on the philosophy: "we recommend against using the root
account for tasks that can be performed as an unprivileged user".

This module codifies the operational rules that follow from that
recommendation:

* root's ``PATH`` should not contain "." (the current directory),
  nor any world-writable directory that an attacker could plant a
  binary in.
* root's ``LD_LIBRARY_PATH`` and ``LD_PRELOAD`` must be empty
  (else root can be tricked into loading an attacker's library).
* root's history file must be mode ``0600`` so an unprivileged
  user cannot read the operator's commands.
* root's ``.ssh`` directory must exist with mode ``0700`` and the
  private keys inside it must be mode ``0600`` - *if* the operator
  has decided to use ssh from root at all (which is itself
  questionable).
* root must not have a web browser cache, a mail client mailbox,
  or any other user-state directory (TLDP: "we recommend that
  subdirectories for mail and other applications not appear in
  the root account's home directory").

The auditor reports each finding with a severity so the operator
can decide which ones to fix immediately.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import re
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Root.Safety")


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------

class SafetySeverity(str, Enum):
    """How urgently the operator should react to a finding."""

    INFO     = "info"        # nice to know
    LOW      = "low"         # fix at next maintenance window
    MEDIUM   = "medium"      # fix soon
    HIGH     = "high"        # fix immediately
    CRITICAL = "critical"    # root account may be compromised

    @property
    def rank(self) -> int:
        return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

@dataclass
class SafetyFinding:
    """One result from the safety audit."""

    code: str
    title: str
    severity: SafetySeverity
    location: str = ""
    detail: str = ""
    fix: str = ""

    def as_dict(self) -> dict:
        return {
            "code":     self.code,
            "title":    self.title,
            "severity": self.severity.value,
            "location": self.location,
            "detail":   self.detail,
            "fix":      self.fix,
        }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class SafetyReport:
    """The aggregate report from :class:`RootSafetyAuditor`."""

    home: str
    findings: List[SafetyFinding] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "home":     self.home,
            "findings": [f.as_dict() for f in self.findings],
            "env":      dict(self.env),
        }

    @property
    def critical(self) -> List[SafetyFinding]:
        return [f for f in self.findings if f.severity == SafetySeverity.CRITICAL]

    @property
    def high(self) -> List[SafetyFinding]:
        return [f for f in self.findings if f.severity == SafetySeverity.HIGH]

    def has_blocking(self) -> bool:
        return any(f.severity in (SafetySeverity.HIGH, SafetySeverity.CRITICAL)
                   for f in self.findings)

    def render(self) -> str:
        lines = [f"Umer OS /root safety audit   ({self.home})",
                 "=" * 50]
        if not self.findings:
            lines.append("  No findings - root account passes the audit.")
            return "\n".join(lines) + "\n"
        # Sort by severity descending.
        ranked = sorted(self.findings, key=lambda f: -f.severity.rank)
        for finding in ranked:
            lines.append(f"  [{finding.severity.value.upper():<8}] {finding.title}")
            if finding.location:
                lines.append(f"      location: {finding.location}")
            if finding.detail:
                lines.append(f"      detail:   {finding.detail}")
            if finding.fix:
                lines.append(f"      fix:      {finding.fix}")
            lines.append("")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Auditor
# ---------------------------------------------------------------------------

class RootSafetyAuditor:
    """Run a battery of safety checks against root's home and env."""

    def __init__(self, home: str) -> None:
        self.home = Path(home)

    def audit(self, env: Optional[Dict[str, str]] = None) -> SafetyReport:
        if env is None:
            env = dict(os.environ)
        report = SafetyReport(home=str(self.home), env=dict(env))
        self._check_path(env, report)
        self._check_ld(env, report)
        self._check_history(report)
        self._check_ssh(report)
        self._check_user_state(report)
        return report

    # -- individual checks ----------------------------------------------

    def _check_path(self, env: Dict[str, str], report: SafetyReport) -> None:
        path = env.get("PATH", "")
        parts = [p for p in path.split(os.pathsep) if p]
        for entry in parts:
            if entry == "." or entry == "":
                report.findings.append(SafetyFinding(
                    code="PATH001",
                    title="PATH contains current directory ('.')",
                    severity=SafetySeverity.HIGH,
                    location="PATH",
                    detail=f"PATH={path!r}",
                    fix="remove '' or '.' from PATH; let operators use './script' explicitly",
                ))
            if not os.path.isdir(entry):
                report.findings.append(SafetyFinding(
                    code="PATH002",
                    title=f"PATH entry {entry!r} does not exist",
                    severity=SafetySeverity.LOW,
                    location="PATH",
                    fix=f"either create the directory or remove {entry!r} from PATH",
                ))
                continue
            st = os.stat(entry)
            if st.st_mode & 0o002:  # world-writable
                report.findings.append(SafetyFinding(
                    code="PATH003",
                    title=f"PATH entry {entry!r} is world-writable",
                    severity=SafetySeverity.CRITICAL,
                    location=entry,
                    detail=f"mode={oct(stat.S_IMODE(st.st_mode))}",
                    fix="chmod o-w on the directory; an attacker could plant a binary there",
                ))

    def _check_ld(self, env: Dict[str, str], report: SafetyReport) -> None:
        if env.get("LD_LIBRARY_PATH"):
            report.findings.append(SafetyFinding(
                code="LD001",
                title="LD_LIBRARY_PATH is set for root",
                severity=SafetySeverity.HIGH,
                location="LD_LIBRARY_PATH",
                detail=f"value={env['LD_LIBRARY_PATH']!r}",
                fix="unset LD_LIBRARY_PATH; root should load libraries from /lib and /usr/lib only",
            ))
        if env.get("LD_PRELOAD"):
            report.findings.append(SafetyFinding(
                code="LD002",
                title="LD_PRELOAD is set for root",
                severity=SafetySeverity.CRITICAL,
                location="LD_PRELOAD",
                detail=f"value={env['LD_PRELOAD']!r}",
                fix="unset LD_PRELOAD immediately; this overrides the dynamic linker",
            ))
        if env.get("LD_AUDIT"):
            report.findings.append(SafetyFinding(
                code="LD003",
                title="LD_AUDIT is set for root",
                severity=SafetySeverity.HIGH,
                location="LD_AUDIT",
                fix="unset LD_AUDIT; this injects a shared object into every root process",
            ))

    def _check_history(self, report: SafetyReport) -> None:
        history = self.home / ".bash_history"
        if not history.is_file():
            return
        st = history.stat()
        mode = stat.S_IMODE(st.st_mode)
        if mode & 0o077:
            report.findings.append(SafetyFinding(
                code="HIST001",
                title=".bash_history is readable by group/other",
                severity=SafetySeverity.MEDIUM,
                location=str(history),
                detail=f"mode={oct(mode)}",
                fix="chmod 600 ~/.bash_history",
            ))

    def _check_ssh(self, report: SafetyReport) -> None:
        ssh_dir = self.home / ".ssh"
        if not ssh_dir.is_dir():
            return
        st = ssh_dir.stat()
        mode = stat.S_IMODE(st.st_mode)
        if mode & 0o077:
            report.findings.append(SafetyFinding(
                code="SSH001",
                title=".ssh directory is too permissive",
                severity=SafetySeverity.HIGH,
                location=str(ssh_dir),
                detail=f"mode={oct(mode)}",
                fix="chmod 700 ~/.ssh",
            ))
        for f in ssh_dir.iterdir():
            if not f.is_file():
                continue
            if f.name.endswith(".pub") or f.name == "known_hosts" or f.name == "config":
                continue
            fst = f.stat()
            fmode = stat.S_IMODE(fst.st_mode)
            if fmode & 0o077:
                report.findings.append(SafetyFinding(
                    code="SSH002",
                    title=f"ssh private key {f.name!r} is too permissive",
                    severity=SafetySeverity.CRITICAL,
                    location=str(f),
                    detail=f"mode={oct(fmode)}",
                    fix=f"chmod 600 {f}",
                ))

    def _check_user_state(self, report: SafetyReport) -> None:
        discouraged = ("Mail", "mail", ".cache", "www", ".config", ".local", ".mozilla")
        if not self.home.is_dir():
            return
        for entry in self.home.iterdir():
            if not entry.is_dir() or entry.is_symlink():
                continue
            if entry.name in discouraged:
                sev = (SafetySeverity.HIGH
                       if entry.name in ("Mail", "mail") else
                       SafetySeverity.MEDIUM)
                report.findings.append(SafetyFinding(
                    code="STATE001",
                    title=f"user-state directory {entry.name!r} present in /root",
                    severity=sev,
                    location=str(entry),
                    detail=("TLDP /root: subdirectories for mail and other "
                            "applications should not appear in /root"),
                    fix=f"move {entry} to /var/mail/root or remove",
                ))


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / ".bash_history").write_text("echo hi\n")
        (home / ".bash_history").chmod(0o644)
        (home / ".ssh").mkdir()
        (home / ".ssh").chmod(0o755)
        (home / ".ssh" / "id_rsa").write_text("secret\n")
        (home / ".ssh" / "id_rsa").chmod(0o644)
        (home / "Mail").mkdir()
        auditor = RootSafetyAuditor(home=str(home))
        sep = os.pathsep
        report = auditor.audit(env={"PATH": sep.join(["/tmp", "."])})
        codes = {f.code for f in report.findings}
        if "PATH001" not in codes:
            return False
        if "LD002" not in codes and "LD001" not in codes:
            # not required, but make sure the path check fired
            pass
        if "HIST001" not in codes:
            return False
        if os.name != "nt":
            # SSH permission checks require Unix-style file modes.
            if "SSH001" not in codes:
                return False
            if "SSH002" not in codes:
                return False
        if "STATE001" not in codes:
            return False
        # CRITICAL findings (LD_PRELOAD, world-writable PATH) must be
        # flagged as blocking.
        env2 = {"PATH": "/tmp", "LD_PRELOAD": "/tmp/evil.so"}
        if os.name != "nt":
            # Make a world-writable /tmp-style dir for the path check.
            with tempfile.TemporaryDirectory() as tmp2:
                world = Path(tmp2) / "world"
                world.mkdir()
                world.chmod(0o777)
                env2["PATH"] = str(world)
        report2 = auditor.audit(env=env2)
        if not report2.has_blocking():
            return False
        if "LD002" not in {f.code for f in report2.findings}:
            return False
        if os.name != "nt" and "PATH003" not in {f.code for f in report2.findings}:
            return False
        # Render.
        text = report.render()
        if "Umer OS /root safety audit" not in text:
            return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("safety selftest:", "OK" if _selftest() else "FAIL")
