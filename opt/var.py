"""
UmerOS /var/opt — Variable Data for /opt Packages
===================================================

Manages per-package variable/state data stored under ``/var/opt``
per the FHS 3.0 / TLDP specification.

FHS 3.0 §3.11.3::

    /var/opt/<provider>/<pkg>/   — variable data for /opt packages

No structure is imposed on the internal arrangement.  Packages may use
this space for caches, databases, spools, logs, or any other mutable state.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Opt.Var")

# ── Constants ──────────────────────────────────────────────────────────

DEFAULT_VAR_OPT = Path("/var/opt")


# ── Data class ─────────────────────────────────────────────────────────

@dataclass
class VarDataEntry:
    """Metadata for a data directory belonging to an /opt package."""

    name: str
    provider: str = ""
    package: str = ""
    path: str = ""
    file_count: int = 0
    total_size: int = 0
    created_at: float = 0.0
    modified_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VarDataEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Manager ────────────────────────────────────────────────────────────

class VarOptManager:
    """
    Manages ``/var/opt/<provider>/<pkg>/`` variable data trees.

    Parameters
    ----------
    var_opt_root : str | Path
        Override the /var/opt root (default ``/var/opt``).
    """

    def __init__(self, var_opt_root: str | Path = DEFAULT_VAR_OPT) -> None:
        self.root = Path(var_opt_root)

    def _pkg_dir(self, package: str, provider: str = "") -> Path:
        if provider:
            return self.root / provider / package
        return self.root / package

    # ── CRUD ───────────────────────────────────────────────────────────

    def ensure_package_dir(self, package: str, provider: str = "") -> Path:
        """Ensure the /var/opt/<provider>/<pkg>/ directory exists."""
        d = self._pkg_dir(package, provider)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def remove_package_dir(self, package: str, provider: str = "") -> bool:
        """Remove the variable data directory for a package."""
        d = self._pkg_dir(package, provider)
        if not d.exists():
            return False
        try:
            shutil.rmtree(d)
            log.info("Removed /var/opt data: %s", d)
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
        """List all packages with data under /var/opt."""
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
                    entry = self._scan_dir(sub, package=sub.name, provider=item.name)
                    packages.append(entry.to_dict())
            else:
                # Direct package directory
                entry = self._scan_dir(item, package=item.name, provider="")
                packages.append(entry.to_dict())

        return packages

    def _scan_dir(self, d: Path, package: str, provider: str) -> VarDataEntry:
        file_count = 0
        total_size = 0
        oldest_ctime = d.stat().st_ctime
        newest_mtime = d.stat().st_mtime

        for f in d.rglob("*"):
            if f.is_file():
                file_count += 1
                size = f.stat().st_size
                total_size += size
                ct = f.stat().st_ctime
                mt = f.stat().st_mtime
                if ct < oldest_ctime:
                    oldest_ctime = ct
                if mt > newest_mtime:
                    newest_mtime = mt

        return VarDataEntry(
            name=d.name,
            provider=provider,
            package=package,
            path=str(d),
            file_count=file_count,
            total_size=total_size,
            created_at=oldest_ctime,
            modified_at=newest_mtime,
        )

    def get_package(self, package: str, provider: str = "") -> Optional[VarDataEntry]:
        """Get data entry for a specific package."""
        d = self._pkg_dir(package, provider)
        if not d.exists():
            return None
        return self._scan_dir(d, package=package, provider=provider)

    def list_files(self, package: str, provider: str = "") -> List[Dict[str, Any]]:
        """List all files in a package's /var/opt directory."""
        pkg_dir = self._pkg_dir(package, provider)
        if not pkg_dir.exists():
            return []

        files: List[Dict[str, Any]] = []
        for f in sorted(pkg_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(pkg_dir)
                stat = f.stat()
                files.append({
                    "name": str(rel),
                    "path": str(f),
                    "size": stat.st_size,
                    "modified": time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(stat.st_mtime),
                    ),
                })
        return files

    def write_file(self, package: str, provider: str = "",
                   filename: str = "data.bin", content: bytes = b"") -> bool:
        """Write a file to /var/opt/<provider>/<pkg>/."""
        pkg_dir = self.ensure_package_dir(package, provider)
        target = pkg_dir / filename
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                content = content.encode("utf-8")
            target.write_bytes(content)
            log.info("Wrote /var/opt file: %s", target)
            return True
        except OSError as exc:
            log.error("Failed to write %s: %s", target, exc)
            return False

    def read_file(self, package: str, provider: str = "",
                  filename: str = "data.bin") -> Optional[bytes]:
        """Read a file from /var/opt/<provider>/<pkg>/."""
        pkg_dir = self._pkg_dir(package, provider)
        target = pkg_dir / filename
        if not target.exists():
            return None
        return target.read_bytes()

    # ── Cleanup ────────────────────────────────────────────────────────

    def cleanup_empty(self) -> List[str]:
        """Remove empty package directories. Returns removed paths."""
        removed: List[str] = []
        if not self.root.exists():
            return removed

        for item in list(self.root.iterdir()):
            if not item.is_dir():
                continue
            # Check if provider directory
            sub_dirs = [d for d in item.iterdir() if d.is_dir()]
            if sub_dirs:
                for sub in list(sub_dirs):
                    if not any(sub.iterdir()):
                        sub.rmdir()
                        removed.append(str(sub))
                # Check if provider dir itself is now empty
                if not any(item.iterdir()):
                    item.rmdir()
                    removed.append(str(item))
            else:
                if not any(item.iterdir()):
                    item.rmdir()
                    removed.append(str(item))

        return removed

    def cleanup_stale(self, max_age_days: int = 90) -> int:
        """Remove package data directories not modified in max_age_days.

        Returns the number of directories removed.
        """
        if not self.root.exists():
            return 0

        cutoff = time.time() - (max_age_days * 86400)
        removed = 0

        for item in list(self.root.iterdir()):
            if not item.is_dir():
                continue

            # Check for provider dirs
            sub_dirs = [d for d in item.iterdir() if d.is_dir()]
            if sub_dirs:
                for sub in list(sub_dirs):
                    if self._is_stale(sub, cutoff):
                        shutil.rmtree(sub)
                        removed += 1
                        log.info("Cleaned stale /var/opt data: %s", sub)
                if not any(item.iterdir()):
                    item.rmdir()
            else:
                if self._is_stale(item, cutoff):
                    shutil.rmtree(item)
                    removed += 1
                    log.info("Cleaned stale /var/opt data: %s", item)

        return removed

    @staticmethod
    def _is_stale(d: Path, cutoff: float) -> bool:
        """Check if all files in a directory are older than cutoff."""
        for f in d.rglob("*"):
            if f.is_file() and f.stat().st_mtime >= cutoff:
                return False
        return True

    # ── Summary ────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Return summary of /var/opt state."""
        packages = self.list_packages()
        total_files = sum(p["file_count"] for p in packages)
        total_size = sum(p["total_size"] for p in packages)
        return {
            "var_opt_root": str(self.root),
            "total_packages": len(packages),
            "total_files": total_files,
            "total_size_bytes": total_size,
            "packages": packages,
        }


# ── Selftest ───────────────────────────────────────────────────────────

def _selftest() -> bool:
    """Run basic self-tests for VarOptManager."""
    import tempfile

    print("[opt/var] selftest …")
    ok = True

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "var-opt"
        mgr = VarOptManager(var_opt_root=root)

        # 1  ensure_package_dir
        d = mgr.ensure_package_dir("firefox", "mozilla")
        assert d.is_dir()
        print("  [PASS] ensure_package_dir (provider)")

        # 2  direct package
        d2 = mgr.ensure_package_dir("vim")
        assert d2.is_dir()
        print("  [PASS] ensure_package_dir (direct)")

        # 3  write_file / read_file
        mgr.write_file("firefox", "mozilla", "cache.dat", b"cachedata")
        content = mgr.read_file("firefox", "mozilla", "cache.dat")
        assert content == b"cachedata"
        print("  [PASS] write_file / read_file")

        # 4  write string content
        mgr.write_file("vim", filename="info.txt", content="hello")
        content = mgr.read_file("vim", filename="info.txt")
        assert content == b"hello"
        print("  [PASS] write_file (string) / read_file")

        # 5  list_files
        mgr.write_file("firefox", "mozilla", "state.json", b'{"k":1}')
        files = mgr.list_files("firefox", "mozilla")
        names = {f["name"] for f in files}
        assert "cache.dat" in names
        assert "state.json" in names
        print("  [PASS] list_files")

        # 6  get_package
        entry = mgr.get_package("firefox", "mozilla")
        assert entry is not None
        assert entry.file_count == 2
        assert entry.total_size > 0
        print("  [PASS] get_package")

        # 7  list_packages
        pkgs = mgr.list_packages()
        assert len(pkgs) == 2
        print("  [PASS] list_packages")

        # 8  read_file missing
        assert mgr.read_file("nonexistent") is None
        print("  [PASS] read_file returns None for missing")

        # 9  cleanup_empty
        empty_dir = root / "empty_pkg"
        empty_dir.mkdir()
        removed = mgr.cleanup_empty()
        assert str(empty_dir) in removed
        assert not empty_dir.exists()
        print("  [PASS] cleanup_empty")

        # 10  remove_package_dir
        assert mgr.remove_package_dir("firefox", "mozilla")
        assert not mgr.remove_package_dir("firefox", "mozilla")
        print("  [PASS] remove_package_dir")

        # 11  summary
        s = mgr.get_summary()
        assert "total_packages" in s
        print("  [PASS] get_summary")

    print("[opt/var] selftest PASSED")
    return ok


if __name__ == "__main__":
    _selftest()
