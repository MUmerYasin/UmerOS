"""
Umer OS /root - FHS / TLDP audit
================================
The single entry point for "is /root set up correctly?".  The other
modules each cover one slice; this one wires them together and
produces a single report.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from root.dotfiles import RootDotfilesManager
from root.home import (
    DEFAULT_ROOT_HOME, ROOT_HOME_MODE, ROOT_UID, RootHomeManager,
)
from root.mail import RootMailForwarder
from root.safety import (
    SafetyFinding, SafetyReport, SafetySeverity, RootSafetyAuditor,
)

log = logging.getLogger("UmerOS.Root.FHS")


# ---------------------------------------------------------------------------
# Issue severity + report
# ---------------------------------------------------------------------------

class FHSIssueSeverity(str, Enum):
    INFO  = "info"
    WARN  = "warn"
    ERROR = "error"


@dataclass
class FHSIssue:
    code: str
    severity: FHSIssueSeverity
    title: str
    detail: str = ""
    fix: str = ""

    def as_dict(self) -> dict:
        return {
            "code":     self.code,
            "severity": self.severity.value,
            "title":    self.title,
            "detail":   self.detail,
            "fix":      self.fix,
        }


@dataclass
class FHSReport:
    home: str
    issues: List[FHSIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == FHSIssueSeverity.ERROR for i in self.issues)

    def as_dict(self) -> dict:
        return {
            "home":   self.home,
            "ok":     self.ok,
            "issues": [i.as_dict() for i in self.issues],
        }

    def render(self) -> str:
        lines = [f"Umer OS /root FHS audit   ({self.home})", "=" * 50]
        if not self.issues:
            lines.append("  OK - /root passes the FHS audit.")
            return "\n".join(lines) + "\n"
        for issue in self.issues:
            lines.append(f"  [{issue.severity.value.upper():<5}] {issue.title}")
            if issue.detail:
                lines.append(f"      detail: {issue.detail}")
            if issue.fix:
                lines.append(f"      fix:    {issue.fix}")
            lines.append("")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Auditor
# ---------------------------------------------------------------------------

class FHSRootAuditor:
    """Single-call FHS / TLDP audit for ``/root``."""

    def __init__(self, home: str = DEFAULT_ROOT_HOME) -> None:
        self.home = home
        self.hm = RootHomeManager(default_path=home)
        self.dm = RootDotfilesManager(home=home)
        self.mm = RootMailForwarder(home=home)
        self.sa = RootSafetyAuditor(home=home)

    def audit(self, env: Optional[Dict[str, str]] = None) -> FHSReport:
        report = FHSReport(home=self.home)
        self._check_home(report)
        self._check_dotfiles(report)
        self._check_forward(report)
        return report

    # -- sub-audits -----------------------------------------------------

    def _check_home(self, report: FHSReport) -> None:
        info = self.hm.audit()
        if not info.exists:
            report.issues.append(FHSIssue(
                code="FHS001",
                severity=FHSIssueSeverity.ERROR,
                title=f"/root does not exist at {info.path!r}",
                detail=f"resolved from {info.resolved_from}",
                fix="create the directory and chmod 0700",
            ))
            return
        if info.mode & 0o007:
            report.issues.append(FHSIssue(
                code="FHS002",
                severity=FHSIssueSeverity.ERROR,
                title=f"/root is accessible to 'other' (mode {oct(info.mode)})",
                detail="FHS / TLDP: only root may enter or read the directory",
                fix=f"chmod 0700 {info.path}",
            ))
        if info.uid != ROOT_UID:
            report.issues.append(FHSIssue(
                code="FHS003",
                severity=FHSIssueSeverity.ERROR,
                title=f"/root is not owned by root (uid {info.uid})",
                fix=f"chown root:root {info.path}",
            ))
        if info.discouraged_subdirs:
            report.issues.append(FHSIssue(
                code="FHS004",
                severity=FHSIssueSeverity.WARN,
                title="discouraged subdirs present in /root",
                detail=", ".join(info.discouraged_subdirs),
                fix="TLDP recommends moving mail and app data to /var",
            ))

    def _check_dotfiles(self, report: FHSReport) -> None:
        if not Path(self.home).is_dir():
            return
        required = (".bashrc", ".profile", ".bash_logout")
        for name in required:
            if not (Path(self.home) / name).is_file():
                report.issues.append(FHSIssue(
                    code="FHS010",
                    severity=FHSIssueSeverity.WARN,
                    title=f"{name} is missing from /root",
                    detail="standard shell init dotfile expected",
                    fix=f"create {name} from the RootDotfilesManager template",
                ))

    def _check_forward(self, report: FHSReport) -> None:
        if not Path(self.home).is_dir():
            return
        forward = self.mm.audit()
        if not forward.exists:
            report.issues.append(FHSIssue(
                code="FHS020",
                severity=FHSIssueSeverity.INFO,
                title=".forward does not exist",
                detail="TLDP /root: admin mail should be forwarded to a non-root user",
                fix="create /root/.forward pointing to your admin user",
            ))
            return
        if any("loop" in i for i in forward.issues):
            report.issues.append(FHSIssue(
                code="FHS021",
                severity=FHSIssueSeverity.WARN,
                title=".forward loops back to root",
                detail=forward.forwards_to,
                fix="point .forward at a non-root user",
            ))
        if any("mode" in i for i in forward.issues):
            report.issues.append(FHSIssue(
                code="FHS022",
                severity=FHSIssueSeverity.WARN,
                title=".forward is too permissive",
                fix="chmod 600 /root/.forward",
            ))

    # -- safety bridge --------------------------------------------------

    def safety_audit(self, env: Optional[Dict[str, str]] = None) -> SafetyReport:
        return self.sa.audit(env=env)

    # -- summary --------------------------------------------------------

    def full_report(self, env: Optional[Dict[str, str]] = None) -> Dict:
        fhs = self.audit(env)
        return {
            "fhs":    fhs.as_dict(),
            "safety": self.safety_audit(env).as_dict(),
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "root"
        home.mkdir()
        home.chmod(ROOT_HOME_MODE)
        # Materialise the dotfiles.
        dm = RootDotfilesManager(home=str(home))
        dm.ensure_all(force=True)
        auditor = FHSRootAuditor(home=str(home))
        report = auditor.audit()
        # No errors expected on a freshly bootstrapped home.
        if not report.ok:
            return False
        # Drop a forbidden subdir and re-audit.
        (home / "Mail").mkdir()
        report2 = auditor.audit()
        if any(i.code == "FHS004" for i in report2.issues):
            pass
        else:
            return False
        # Tighten permissions - should now fail FHS002.
        home.chmod(0o755)
        report3 = auditor.audit()
        if not any(i.code == "FHS002" for i in report3.issues):
            return False
        # Render.
        text = report3.render()
        if "Umer OS /root FHS audit" not in text:
            return False
        # Full report combines FHS + safety.
        combined = auditor.full_report()
        if "fhs" not in combined or "safety" not in combined:
            return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("fhs selftest:", "OK" if _selftest() else "FAIL")
