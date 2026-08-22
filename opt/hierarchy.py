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
UmerOS /opt — TLDP Directory Hierarchy Manager
================================================

Manages the ``/opt`` directory tree per the Filesystem Hierarchy
Standard (TLDP) and FHS 3.0.

Responsibilities
----------------
* Create the canonical ``/opt`` subdirectories.
* Protect reserved directories that packages must NOT use.
* Provide a ``bootstrap()`` that creates the full skeleton on first boot.
* Maintain a lightweight registry of installed packages under ``/opt``.

Reserved directories (TLDP §3.11)::

    /opt/bin   — local sysadmin binaries
    /opt/doc   — local documentation
    /opt/include — local C/C++ headers
    /opt/info  — local info documents
    /opt/lib   — local libraries
    /opt/man   — local man pages

These directories are created by ``bootstrap()`` and are protected from
package installation by ``validate_package_path()``.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Opt.Hierarchy")

# ── Constants ──────────────────────────────────────────────────────────

OPT_ROOT = Path("/opt")

RESERVED_DIRS: tuple[str, ...] = (
    "bin",
    "doc",
    "include",
    "info",
    "lib",
    "man",
)

OPTIONAL_RESERVED: tuple[str, ...] = (
    "sbin",
    "games",
)

KNOWN_SUBDIRS: tuple[str, ...] = (
    "bin",
    "etc",
    "include",
    "info",
    "lib",
    "libexec",
    "man",
    "sbin",
    "share",
    "state",
)

REGISTRY_PATH = Path("/var/lib/umeros/opt-registry.json")


# ── Data classes ───────────────────────────────────────────────────────

@dataclass
class PackageEntry:
    """Lightweight record of a package installed under /opt."""

    name: str
    provider: str = ""
    version: str = ""
    install_path: str = ""
    installed_at: float = 0.0
    file_count: int = 0
    total_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @property
    def full_name(self) -> str:
        """Provider/name or just name."""
        if self.provider:
            return f"{self.provider}/{self.name}"
        return self.name

    @property
    def opt_path(self) -> Path:
        """Resolved path under /opt."""
        if self.provider:
            return OPT_ROOT / self.provider / self.name
        return OPT_ROOT / self.name


# ── Manager ────────────────────────────────────────────────────────────

class OptHierarchy:
    """
    Manages the ``/opt`` directory tree and package registry.

    Parameters
    ----------
    opt_root : str | Path
        Override the root path (default ``/opt``).
    """

    def __init__(self, opt_root: str | Path = OPT_ROOT) -> None:
        self.root = Path(opt_root)
        self.registry_path = REGISTRY_PATH

    # ── Bootstrap ──────────────────────────────────────────────────────

    def bootstrap(self) -> None:
        """
        Create the full ``/opt`` skeleton and empty reserved directories.

        Safe to call multiple times (idempotent).
        """
        self.root.mkdir(parents=True, exist_ok=True)

        for name in RESERVED_DIRS + OPTIONAL_RESERVED:
            d = self.root / name
            d.mkdir(parents=True, exist_ok=True)
            log.debug("Ensured reserved dir: %s", d)

        # Ensure the registry directory exists
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self.registry_path.write_text("{}", encoding="utf-8")
            log.info("Created empty opt-registry at %s", self.registry_path)

        log.info("Bootstrap complete for /opt hierarchy")

    # ── Registry ───────────────────────────────────────────────────────

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        if not self.registry_path.exists():
            return {}
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Corrupt opt-registry, starting fresh: %s", exc)
            return {}

    def _save_registry(self, registry: Dict[str, Dict[str, Any]]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def register_package(self, entry: PackageEntry) -> None:
        """Add or update a package entry in the registry."""
        reg = self._load_registry()
        reg[entry.full_name] = entry.to_dict()
        self._save_registry(reg)
        log.info("Registered package: %s", entry.full_name)

    def unregister_package(self, full_name: str) -> bool:
        """Remove a package from the registry. Returns True if found."""
        reg = self._load_registry()
        if full_name in reg:
            del reg[full_name]
            self._save_registry(reg)
            log.info("Unregistered package: %s", full_name)
            return True
        return False

    def get_package(self, full_name: str) -> Optional[PackageEntry]:
        """Look up a single package by provider/name or name."""
        reg = self._load_registry()
        data = reg.get(full_name)
        if data is None:
            return None
        return PackageEntry.from_dict(data)

    def list_packages(self) -> List[PackageEntry]:
        """Return all registered packages."""
        reg = self._load_registry()
        return [PackageEntry.from_dict(v) for v in reg.values()]

    # ── Validation ─────────────────────────────────────────────────────

    def is_reserved(self, name: str) -> bool:
        """Return True if *name* is a reserved top-level /opt directory."""
        return name in RESERVED_DIRS

    def validate_package_path(self, package_path: str | Path) -> List[str]:
        """
        Validate that a proposed package installation path does not
        conflict with reserved directories.

        Returns a list of error strings (empty = valid).
        """
        p = Path(package_path)
        errors: List[str] = []

        try:
            rel = p.relative_to(self.root)
        except ValueError:
            # Outside /opt — not our concern
            return []

        parts = rel.parts
        if not parts:
            errors.append("Cannot install directly in /opt root")
            return errors

        first = parts[0]
        if first in RESERVED_DIRS:
            errors.append(
                f"Path conflicts with reserved directory /opt/{first}"
            )

        if len(parts) >= 2 and parts[0] == "etc":
            errors.append(
                "Package config belongs in /etc/opt, not /opt/etc"
            )
        if len(parts) >= 2 and parts[0] == "var":
            errors.append(
                "Package variable data belongs in /var/opt, not /opt/var"
            )

        return errors

    # ── Scanning ───────────────────────────────────────────────────────

    def scan_installed(self) -> List[PackageEntry]:
        """
        Walk ``/opt`` and return a ``PackageEntry`` for each directory
        that looks like an installed package.

        This does NOT touch the JSON registry — it is purely filesystem-based.
        """
        if not self.root.exists():
            return []

        entries: List[PackageEntry] = []

        for item in sorted(self.root.iterdir()):
            if not item.is_dir():
                continue
            if item.name in RESERVED_DIRS or item.name in OPTIONAL_RESERVED:
                continue

            # Check for provider/package layout
            sub_items = [d for d in item.iterdir() if d.is_dir()]
            if sub_items and all(
                d.name in KNOWN_SUBDIRS or d.name.startswith(".")
                for d in sub_items
            ):
                # Looks like a direct package: /opt/<pkg>/bin, etc.
                entries.append(self._entry_from_dir(item, provider=""))
            else:
                # Possibly a provider directory: /opt/<provider>/<pkg>/...
                for sub in sub_items:
                    if sub.name.startswith("."):
                        continue
                    if sub.name in RESERVED_DIRS:
                        continue
                    entries.append(self._entry_from_dir(sub, provider=item.name))

        return entries

    def _entry_from_dir(self, pkg_dir: Path, provider: str) -> PackageEntry:
        file_count = sum(1 for _ in pkg_dir.rglob("*") if _.is_file())
        total_size = sum(f.stat().st_size for f in pkg_dir.rglob("*") if f.is_file())
        return PackageEntry(
            name=pkg_dir.name,
            provider=provider,
            install_path=str(pkg_dir),
            installed_at=pkg_dir.stat().st_ctime,
            file_count=file_count,
            total_size=total_size,
        )

    # ── Cleanup ────────────────────────────────────────────────────────

    def remove_empty_reserved(self) -> List[str]:
        """Remove reserved directories that are empty. Returns removed names."""
        removed: List[str] = []
        for name in RESERVED_DIRS:
            d = self.root / name
            if d.exists() and d.is_dir() and not any(d.iterdir()):
                d.rmdir()
                removed.append(name)
                log.info("Removed empty reserved dir: %s", d)
        return removed

    # ── Summary ────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary dict of the /opt hierarchy."""
        entries = self.list_packages()
        return {
            "opt_root": str(self.root),
            "registered_packages": len(entries),
            "reserved_dirs": list(RESERVED_DIRS),
            "reserved_present": [
                d for d in RESERVED_DIRS if (self.root / d).exists()
            ],
            "total_files": sum(e.file_count for e in entries),
            "total_size_bytes": sum(e.total_size for e in entries),
        }


# ── Selftest ───────────────────────────────────────────────────────────

def _selftest() -> bool:
    """Run basic self-tests for OptHierarchy."""
    import tempfile

    print("[opt/hierarchy] selftest …")
    ok = True

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "opt"
        mgr = OptHierarchy(opt_root=root)

        # 1  bootstrap creates dirs
        mgr.bootstrap()
        for name in RESERVED_DIRS + OPTIONAL_RESERVED:
            assert (root / name).is_dir(), f"missing reserved dir {name}"
        print("  [PASS] bootstrap creates reserved dirs")

        # 2  bootstrap is idempotent
        mgr.bootstrap()
        print("  [PASS] bootstrap is idempotent")

        # 3  is_reserved
        assert mgr.is_reserved("bin")
        assert mgr.is_reserved("man")
        assert not mgr.is_reserved("firefox")
        print("  [PASS] is_reserved")

        # 4  validate_package_path
        errs = mgr.validate_package_path(root / "firefox" / "bin")
        assert errs == [], f"unexpected errors: {errs}"
        errs = mgr.validate_package_path(root / "bin" / "foo")
        assert len(errs) == 1, "expected error for /opt/bin"
        print("  [PASS] validate_package_path rejects reserved dirs")

        # 5  register / unregister
        entry = PackageEntry(
            name="firefox",
            provider="mozilla",
            version="128.0",
            install_path=str(root / "mozilla" / "firefox"),
        )
        mgr.register_package(entry)
        got = mgr.get_package("mozilla/firefox")
        assert got is not None
        assert got.version == "128.0"
        assert mgr.unregister_package("mozilla/firefox")
        assert mgr.get_package("mozilla/firefox") is None
        print("  [PASS] register / unregister round-trip")

        # 6  list_packages
        mgr.register_package(PackageEntry(name="a", install_path="/opt/a"))
        mgr.register_package(PackageEntry(name="b", provider="x", install_path="/opt/x/b"))
        pkgs = mgr.list_packages()
        assert len(pkgs) == 2
        print("  [PASS] list_packages")

        # 7  scan_installed
        (root / "firefox").mkdir(parents=True)
        (root / "firefox" / "bin").mkdir()
        (root / "firefox" / "bin" / "firefox").write_text("#!", encoding="utf-8")
        scanned = mgr.scan_installed()
        names = {e.name for e in scanned}
        assert "firefox" in names
        print("  [PASS] scan_installed detects /opt/<pkg>")

        # 8  scan provider layout
        (root / "mozilla").mkdir(parents=True)
        (root / "mozilla" / "thunderbird").mkdir()
        (root / "mozilla" / "thunderbird" / "bin").mkdir()
        scanned = mgr.scan_installed()
        providers = {e.provider: e.name for e in scanned if e.provider}
        assert "mozilla" in providers
        print("  [PASS] scan_installed detects /opt/<provider>/<pkg>")

        # 9  summary
        s = mgr.get_summary()
        assert "reserved_dirs" in s
        assert "registered_packages" in s
        print("  [PASS] get_summary")

        # 10  registry file created
        assert mgr.registry_path.exists()
        print("  [PASS] registry file created by bootstrap")

    print("[opt/hierarchy] selftest PASSED")
    return ok


if __name__ == "__main__":
    _selftest()
