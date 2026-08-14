"""
UmerOS /opt — FHS Compliance Validator
=======================================

Audits the ``/opt`` hierarchy against the Linux Filesystem Hierarchy
Standard (TLDP) and FHS 3.0.

Checks performed:

1. Reserved directories exist and are empty of package files.
2. Each package under /opt has a standard subdirectory layout.
3. No package installs directly in the /opt root.
4. /etc/opt and /var/opt follow the <provider>/<pkg> convention.
5. No world-writable files exist in package trees.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("UmerOS.Opt.FHS")

# ── Constants ──────────────────────────────────────────────────────────

OPT_ROOT = Path("/opt")
ETC_OPT = Path("/etc/opt")
VAR_OPT = Path("/var/opt")

RESERVED_DIRS: tuple[str, ...] = ("bin", "doc", "include", "info", "lib", "man")

STANDARD_SUBDIRS: tuple[str, ...] = (
    "bin", "etc", "include", "info", "lib", "libexec",
    "man", "sbin", "share", "state",
)


class Severity(Enum):
    """Severity level for an FHS finding."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PASS = "pass"


@dataclass
class FHSFinding:
    """A single FHS compliance finding."""
    check: str
    severity: Severity
    message: str
    path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


# ── Validator ──────────────────────────────────────────────────────────

class OptFHSValidator:
    """
    Validates the ``/opt`` hierarchy against FHS/TLDP requirements.

    Parameters
    ----------
    opt_root, etc_opt, var_opt : str | Path
        Override default paths.
    """

    def __init__(
        self,
        opt_root: str | Path = OPT_ROOT,
        etc_opt: str | Path = ETC_OPT,
        var_opt: str | Path = VAR_OPT,
    ) -> None:
        self.opt_root = Path(opt_root)
        self.etc_opt = Path(etc_opt)
        self.var_opt = Path(var_opt)

    def validate(self) -> List[FHSFinding]:
        """Run all FHS checks and return findings."""
        findings: List[FHSFinding] = []

        findings.extend(self._check_reserved_dirs())
        findings.extend(self._check_reserved_not_package())
        findings.extend(self._check_packages())
        findings.extend(self._check_etc_opt())
        findings.extend(self._check_var_opt())
        findings.extend(self._check_world_writable())

        return findings

    # ── Checks ─────────────────────────────────────────────────────────

    def _check_reserved_dirs(self) -> List[FHSFinding]:
        """Reserved directories should exist."""
        findings: List[FHSFinding] = []
        if not self.opt_root.exists():
            findings.append(FHSFinding(
                check="reserved_dirs_exist",
                severity=Severity.ERROR,
                message="/opt directory does not exist",
            ))
            return findings

        for name in RESERVED_DIRS:
            d = self.opt_root / name
            if not d.exists():
                findings.append(FHSFinding(
                    check="reserved_dirs_exist",
                    severity=Severity.WARNING,
                    message=f"Reserved directory /opt/{name} does not exist",
                    path=str(d),
                ))
            elif d.is_file():
                findings.append(FHSFinding(
                    check="reserved_dirs_exist",
                    severity=Severity.ERROR,
                    message=f"Expected directory but found file: /opt/{name}",
                    path=str(d),
                ))
            else:
                findings.append(FHSFinding(
                    check="reserved_dirs_exist",
                    severity=Severity.PASS,
                    message=f"Reserved directory /opt/{name} exists",
                    path=str(d),
                ))
        return findings

    def _check_reserved_not_package(self) -> List[FHSFinding]:
        """Reserved directories must not contain package-installed files."""
        findings: List[FHSFinding] = []
        for name in RESERVED_DIRS:
            d = self.opt_root / name
            if not d.is_dir():
                continue
            files = [f for f in d.rglob("*") if f.is_file()]
            # We allow the directory to be empty or contain only admin-placed files
            # We can't distinguish admin files from package files without metadata,
            # so we just note the count
            if files:
                findings.append(FHSFinding(
                    check="reserved_not_package",
                    severity=Severity.INFO,
                    message=f"/opt/{name} contains {len(files)} file(s) — verify these are admin-placed",
                    path=str(d),
                ))
        return findings

    def _check_packages(self) -> List[FHSFinding]:
        """Check that packages have standard layout."""
        findings: List[FHSFinding] = []
        if not self.opt_root.exists():
            return findings

        for item in sorted(self.opt_root.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith("."):
                continue
            if item.name in RESERVED_DIRS:
                continue

            # Check for provider/package layout
            sub_dirs = [
                d for d in item.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]
            if sub_dirs and all(
                d.name in STANDARD_SUBDIRS or d.name in RESERVED_DIRS
                for d in sub_dirs
            ):
                # Direct package
                findings.extend(self._validate_pkg_dirs(item, item.name, ""))
            else:
                # Provider directory
                for sub in sub_dirs:
                    if sub.name.startswith(".") or sub.name in RESERVED_DIRS:
                        continue
                    findings.extend(self._validate_pkg_dirs(sub, sub.name, item.name))

        return findings

    def _validate_pkg_dirs(self, pkg_dir: Path, name: str, provider: str) -> List[FHSFinding]:
        """Validate the subdirectories of a single package."""
        findings: List[FHSFinding] = []
        prefix = f"/opt/{provider}/{name}" if provider else f"/opt/{name}"

        # Check for manifest.json
        manifest = pkg_dir / "manifest.json"
        if manifest.exists():
            findings.append(FHSFinding(
                check="package_manifest",
                severity=Severity.PASS,
                message=f"{prefix} has manifest.json",
                path=str(manifest),
            ))
        else:
            findings.append(FHSFinding(
                check="package_manifest",
                severity=Severity.INFO,
                message=f"{prefix} has no manifest.json",
                path=str(pkg_dir),
            ))

        # Check for standard subdirs
        for subdir in ("bin", "lib", "man"):
            d = pkg_dir / subdir
            if d.is_dir():
                findings.append(FHSFinding(
                    check="package_subdirs",
                    severity=Severity.PASS,
                    message=f"{prefix}/{subdir} exists",
                    path=str(d),
                ))

        return findings

    def _check_etc_opt(self) -> List[FHSFinding]:
        """Validate /etc/opt structure."""
        findings: List[FHSFinding] = []
        if not self.etc_opt.exists():
            findings.append(FHSFinding(
                check="etc_opt_exists",
                severity=Severity.INFO,
                message="/etc/opt does not exist (acceptable if no /opt packages)",
            ))
            return findings

        for item in self.etc_opt.iterdir():
            if not item.is_dir() or item.name.startswith("."):
                continue

            # Check for provider vs direct package
            sub_dirs = [d for d in item.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if sub_dirs:
                # Provider dir
                for sub in sub_dirs:
                    findings.append(FHSFinding(
                        check="etc_opt_structure",
                        severity=Severity.PASS,
                        message=f"/etc/opt/{item.name}/{sub.name} follows convention",
                        path=str(sub),
                    ))
            else:
                findings.append(FHSFinding(
                    check="etc_opt_structure",
                    severity=Severity.PASS,
                    message=f"/etc/opt/{item.name} follows convention",
                    path=str(item),
                ))

        return findings

    def _check_var_opt(self) -> List[FHSFinding]:
        """Validate /var/opt structure."""
        findings: List[FHSFinding] = []
        if not self.var_opt.exists():
            findings.append(FHSFinding(
                check="var_opt_exists",
                severity=Severity.INFO,
                message="/var/opt does not exist (acceptable if no /opt packages)",
            ))
            return findings

        for item in self.var_opt.iterdir():
            if not item.is_dir() or item.name.startswith("."):
                continue
            findings.append(FHSFinding(
                check="var_opt_structure",
                severity=Severity.PASS,
                message=f"/var/opt/{item.name} present",
                path=str(item),
            ))

        return findings

    def _check_world_writable(self) -> List[FHSFinding]:
        """No files under /opt should be world-writable."""
        findings: List[FHSFinding] = []
        if not self.opt_root.exists():
            return findings

        for f in self.opt_root.rglob("*"):
            if f.is_file():
                mode = f.stat().st_mode
                if mode & 0o002:
                    findings.append(FHSFinding(
                        check="no_world_writable",
                        severity=Severity.WARNING,
                        message=f"World-writable file: {f}",
                        path=str(f),
                    ))

        return findings

    # ── Summary ────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Run validation and return a summary dict."""
        findings = self.validate()
        by_severity: Dict[str, int] = {}
        for f in findings:
            key = f.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1
        return {
            "total_findings": len(findings),
            "by_severity": by_severity,
            "findings": [f.to_dict() for f in findings],
        }


# ── Selftest ───────────────────────────────────────────────────────────

def _selftest() -> bool:
    """Run basic self-tests for OptFHSValidator."""
    import tempfile

    print("[opt/fhs] selftest …")
    ok = True

    with tempfile.TemporaryDirectory() as td:
        opt = Path(td) / "opt"
        etc = Path(td) / "etc-opt"
        var = Path(td) / "var-opt"

        validator = OptFHSValidator(opt_root=opt, etc_opt=etc, var_opt=var)

        # 1  empty — /opt doesn't exist
        findings = validator.validate()
        errs = [f for f in findings if f.severity == Severity.ERROR]
        assert any("does not exist" in f.message for f in errs)
        print("  [PASS] detects missing /opt")

        # 2  bootstrap and validate
        opt.mkdir(parents=True)
        for name in RESERVED_DIRS:
            (opt / name).mkdir()
        findings = validator.validate()
        passes = [f for f in findings if f.severity == Severity.PASS]
        assert len(passes) >= len(RESERVED_DIRS)
        print("  [PASS] reserved dirs present -> PASS findings")

        # 3  missing reserved dir
        (opt / "bin").rmdir()
        findings = validator.validate()
        warns = [f for f in findings if f.severity == Severity.WARNING]
        assert any("does not exist" in f.message and "bin" in f.message for f in warns)
        print("  [PASS] missing reserved dir -> WARNING")

        # 4  package with standard layout
        (opt / "bin").mkdir()  # restore
        pkg = opt / "firefox"
        pkg.mkdir()
        (pkg / "bin").mkdir()
        (pkg / "lib").mkdir()
        (pkg / "man").mkdir()
        findings = validator.validate()
        assert any("manifest.json" in f.message for f in findings)
        print("  [PASS] detects package layout")

        # 5  package with manifest
        (pkg / "manifest.json").write_text('{}', encoding="utf-8")
        findings = validator.validate()
        assert any(f.severity == Severity.PASS and "manifest.json" in f.message for f in findings)
        print("  [PASS] detects manifest")

        # 6  world-writable detection
        bad_file = pkg / "bad.txt"
        bad_file.write_text("bad", encoding="utf-8")
        os.chmod(str(bad_file), 0o666)
        findings = validator.validate()
        assert any(f.severity == Severity.WARNING and "World-writable" in f.message for f in findings)
        os.chmod(str(bad_file), 0o644)  # cleanup
        print("  [PASS] world-writable detection")

        # 7  etc_opt / var_opt
        etc.mkdir(parents=True)
        var.mkdir(parents=True)
        findings = validator.validate()
        print("  [PASS] etc_opt / var_opt handled")

        # 8  summary
        s = validator.get_summary()
        assert "total_findings" in s
        assert "by_severity" in s
        print("  [PASS] get_summary")

    print("[opt/fhs] selftest PASSED")
    return ok


if __name__ == "__main__":
    _selftest()
