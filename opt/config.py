"""
UmerOS /etc/opt — Host-Specific Package Configuration
=======================================================

Manages per-package configuration files stored under ``/etc/opt``
per the FHS 3.0 / TLDP specification.

FHS 3.0 §3.11.2::

    /etc/opt/<provider>/<pkg>/   — host-specific config for /opt packages

If a package has a global config file (e.g. ``/etc/<pkg>.conf``), it may
also be placed directly in ``/etc`` instead.  This module handles the
``/etc/opt`` hierarchy.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Opt.Config")

# ── Constants ──────────────────────────────────────────────────────────

DEFAULT_ETC_OPT = Path("/etc/opt")


# ── Data class ─────────────────────────────────────────────────────────

@dataclass
class PackageConfig:
    """Metadata for a configuration item belonging to an /opt package."""

    name: str
    provider: str = ""
    package: str = ""
    description: str = ""
    permissions: str = "644"
    created_at: float = 0.0
    modified_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Manager ────────────────────────────────────────────────────────────

class EtcOptManager:
    """
    Manages ``/etc/opt/<provider>/<pkg>/`` configuration trees.

    Parameters
    ----------
    etc_opt_root : str | Path
        Override the /etc/opt root (default ``/etc/opt``).
    """

    def __init__(self, etc_opt_root: str | Path = DEFAULT_ETC_OPT) -> None:
        self.root = Path(etc_opt_root)

    def _pkg_dir(self, package: str, provider: str = "") -> Path:
        if provider:
            return self.root / provider / package
        return self.root / package

    def _metadata_path(self, package: str, provider: str = "") -> Path:
        return self._pkg_dir(package, provider) / ".umeros-config.json"

    # ── CRUD ───────────────────────────────────────────────────────────

    def ensure_package_dir(self, package: str, provider: str = "") -> Path:
        """Ensure the /etc/opt/<provider>/<pkg>/ directory exists."""
        d = self._pkg_dir(package, provider)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def remove_package_dir(self, package: str, provider: str = "") -> bool:
        """Remove the configuration directory for a package."""
        d = self._pkg_dir(package, provider)
        if not d.exists():
            return False
        try:
            shutil.rmtree(d)
            log.info("Removed /etc/opt config: %s", d)
            # Clean empty provider dir
            if provider:
                parent = self.root / provider
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
            return True
        except OSError as exc:
            log.error("Failed to remove %s: %s", d, exc)
            return False

    def list_packages(self) -> List[Dict[str, Any]]:
        """List all packages with configuration under /etc/opt."""
        if not self.root.exists():
            return []

        packages: List[Dict[str, Any]] = []

        for item in sorted(self.root.iterdir()):
            if not item.is_dir() or item.name.startswith("."):
                continue

            # Check for provider directory
            sub_dirs = [d for d in item.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if sub_dirs:
                # Provider directory
                for sub in sub_dirs:
                    file_count = sum(1 for _ in sub.rglob("*") if _.is_file())
                    packages.append({
                        "package": sub.name,
                        "provider": item.name,
                        "path": str(sub),
                        "file_count": file_count,
                    })
            else:
                # Direct package directory
                file_count = sum(1 for _ in item.rglob("*") if _.is_file())
                packages.append({
                    "package": item.name,
                    "provider": "",
                    "path": str(item),
                    "file_count": file_count,
                })

        return packages

    def read_config(self, package: str, provider: str = "",
                    filename: str = "") -> Optional[str]:
        """Read a configuration file from /etc/opt/<provider>/<pkg>/."""
        pkg_dir = self._pkg_dir(package, provider)
        if not pkg_dir.exists():
            return None

        if filename:
            f = pkg_dir / filename
            if f.exists() and f.is_file():
                return f.read_text(encoding="utf-8")
            return None

        # Return the first config file found (non-hidden, non-json-meta)
        for f in sorted(pkg_dir.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                return f.read_text(encoding="utf-8")

        return None

    def write_config(self, package: str, provider: str = "",
                     filename: str = "config.conf", content: str = "",
                     *, permissions: str = "644") -> bool:
        """Write a configuration file to /etc/opt/<provider>/<pkg>/."""
        pkg_dir = self.ensure_package_dir(package, provider)
        target = pkg_dir / filename
        try:
            target.write_text(content, encoding="utf-8")
            # Set permissions
            mode = int(permissions, 8)
            os.chmod(str(target), mode)

            # Update metadata
            meta = PackageConfig(
                name=filename,
                provider=provider,
                package=package,
                permissions=permissions,
                created_at=os.path.getctime(str(target)),
                modified_at=os.path.getmtime(str(target)),
            )
            meta_path = self._metadata_path(package, provider)
            meta_path.write_text(
                json.dumps(meta.to_dict(), indent=2),
                encoding="utf-8",
            )

            log.info("Wrote /etc/opt config: %s/%s/%s", provider or "-", package, filename)
            return True
        except OSError as exc:
            log.error("Failed to write config: %s", exc)
            return False

    def list_files(self, package: str, provider: str = "") -> List[Dict[str, Any]]:
        """List all files in a package's /etc/opt directory."""
        pkg_dir = self._pkg_dir(package, provider)
        if not pkg_dir.exists():
            return []

        files: List[Dict[str, Any]] = []
        for f in sorted(pkg_dir.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                rel = f.relative_to(pkg_dir)
                files.append({
                    "name": str(rel),
                    "path": str(f),
                    "size": f.stat().st_size,
                    "permissions": oct(f.stat().st_mode)[-3:],
                })
        return files

    def copy_from(self, package: str, provider: str = "",
                  source_dir: str | Path = "") -> int:
        """Copy all files from a local directory into /etc/opt/<pkg>/.

        Returns the number of files copied.
        """
        src = Path(source_dir)
        if not src.is_dir():
            log.warning("Source directory does not exist: %s", src)
            return 0

        dest = self.ensure_package_dir(package, provider)
        count = 0
        for f in src.rglob("*"):
            if f.is_file():
                rel = f.relative_to(src)
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(f), str(target))
                count += 1

        log.info("Copied %d files to /etc/opt/%s", count, package)
        return count

    # ── Validation ─────────────────────────────────────────────────────

    def validate(self) -> List[Dict[str, str]]:
        """
        Validate the /etc/opt hierarchy.

        Returns a list of findings (level, message).
        """
        findings: List[Dict[str, str]] = []

        if not self.root.exists():
            findings.append({"level": "info", "message": "/etc/opt does not exist"})
            return findings

        for item in self.root.iterdir():
            if not item.is_dir() or item.name.startswith("."):
                continue

            # Check for world-writable files
            for f in item.rglob("*"):
                if f.is_file():
                    mode = f.stat().st_mode
                    if mode & 0o002:
                        findings.append({
                            "level": "warning",
                            "message": f"World-writable config file: {f}",
                        })

            # Check for empty directories
            if not any(item.iterdir()):
                findings.append({
                    "level": "info",
                    "message": f"Empty directory: {item}",
                })

        return findings

    # ── Summary ────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Return summary of /etc/opt state."""
        packages = self.list_packages()
        total_files = sum(p["file_count"] for p in packages)
        return {
            "etc_opt_root": str(self.root),
            "total_packages": len(packages),
            "total_files": total_files,
            "packages": packages,
        }


# ── Selftest ───────────────────────────────────────────────────────────

def _selftest() -> bool:
    """Run basic self-tests for EtcOptManager."""
    import tempfile

    print("[opt/config] selftest …")
    ok = True

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "etc-opt"
        mgr = EtcOptManager(etc_opt_root=root)

        # 1  ensure_package_dir
        d = mgr.ensure_package_dir("firefox", "mozilla")
        assert d.is_dir()
        assert "mozilla" in str(d)
        assert "firefox" in str(d)
        print("  [PASS] ensure_package_dir (provider)")

        # 2  direct package (no provider)
        d2 = mgr.ensure_package_dir("vim")
        assert d2.is_dir()
        assert "vim" in str(d2)
        print("  [PASS] ensure_package_dir (direct)")

        # 3  write_config
        ok = mgr.write_config("firefox", "mozilla", "prefs.js", "user_pref('x', 1);")
        assert ok
        content = mgr.read_config("firefox", "mozilla", "prefs.js")
        assert content == "user_pref('x', 1);"
        print("  [PASS] write_config / read_config")

        # 4  list_files
        mgr.write_config("firefox", "mozilla", "profiles.ini", "[Profile0]")
        files = mgr.list_files("firefox", "mozilla")
        names = {f["name"] for f in files}
        assert "prefs.js" in names
        assert "profiles.ini" in names
        print("  [PASS] list_files")

        # 5  list_packages
        pkgs = mgr.list_packages()
        assert len(pkgs) == 2  # mozilla/firefox + vim
        print("  [PASS] list_packages")

        # 6  copy_from
        src_dir = Path(td) / "src"
        src_dir.mkdir()
        (src_dir / "settings.conf").write_text("key=value", encoding="utf-8")
        (src_dir / "sub").mkdir()
        (src_dir / "sub" / "extra.conf").write_text("extra=1", encoding="utf-8")
        count = mgr.copy_from("app", source_dir=src_dir)
        assert count == 2
        assert mgr.read_config("app", filename="settings.conf") == "key=value"
        print("  [PASS] copy_from")

        # 7  validate
        findings = mgr.validate()
        assert isinstance(findings, list)
        print("  [PASS] validate")

        # 8  remove_package_dir
        assert mgr.remove_package_dir("firefox", "mozilla")
        assert not mgr.remove_package_dir("firefox", "mozilla")  # already removed
        print("  [PASS] remove_package_dir")

        # 9  summary
        s = mgr.get_summary()
        assert "total_packages" in s
        print("  [PASS] get_summary")

    print("[opt/config] selftest PASSED")
    return ok


if __name__ == "__main__":
    _selftest()
