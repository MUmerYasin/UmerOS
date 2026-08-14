"""
UmerOS /opt — Third-Party Package Manager
===========================================

Handles installation, removal, and querying of third-party software
packages under the ``/opt`` directory tree.

Package layout (TLDP §3.11)::

    /opt/<provider>/<pkg>/
        bin/         — program binaries
        etc/         — package-specific configuration
        include/     — C/C++ headers
        info/        — GNU info documents
        lib/         — shared and static libraries
        libexec/     — helper binaries
        man/         — man pages
        sbin/        — system binaries
        share/       — architecture-independent data
        state/       — variable/state data

Each package has a ``manifest.json`` stored alongside the install tree
containing metadata (name, provider, version, dependencies, etc.).

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tarfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Opt.Package")

# ── Constants ──────────────────────────────────────────────────────────

OPT_ROOT = Path("/opt")
DEFAULT_ETC_OPT = Path("/etc/opt")
DEFAULT_VAR_OPT = Path("/var/opt")

MANIFEST_NAME = "manifest.json"

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


# ── Data classes ───────────────────────────────────────────────────────

@dataclass
class PackageManifest:
    """Structured metadata for an installed /opt package."""

    name: str
    provider: str = ""
    version: str = ""
    description: str = ""
    arch: str = "all"
    dependencies: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    maintainer: str = ""
    homepage: str = ""
    license: str = ""
    installed_at: float = 0.0
    install_path: str = ""
    file_count: int = 0
    total_size: int = 0
    checksum: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageManifest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_file(cls, path: str | Path) -> Optional["PackageManifest"]:
        """Load a manifest from a JSON file."""
        p = Path(path)
        if not p.exists():
            return None
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            return cls.from_dict(raw)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Failed to load manifest %s: %s", p, exc)
            return None

    def save(self, path: str | Path) -> None:
        """Persist manifest to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @property
    def full_name(self) -> str:
        if self.provider:
            return f"{self.provider}/{self.name}"
        return self.name


@dataclass
class InstalledPackage:
    """Runtime representation of an installed package with resolved paths."""

    manifest: PackageManifest
    opt_path: Path
    etc_path: Optional[Path] = None
    var_path: Optional[Path] = None

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def provider(self) -> str:
        return self.manifest.provider

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def full_name(self) -> str:
        return self.manifest.full_name

    @property
    def has_bin(self) -> bool:
        return (self.opt_path / "bin").is_dir()

    @property
    def bin_dir(self) -> Optional[Path]:
        d = self.opt_path / "bin"
        return d if d.is_dir() else None

    @property
    def has_man(self) -> bool:
        return (self.opt_path / "man").is_dir() or (self.opt_path / "share" / "man").is_dir()

    def list_binaries(self) -> List[str]:
        """List executables in the package bin/ and sbin/ directories."""
        bins: List[str] = []
        for subdir in ("bin", "sbin"):
            d = self.opt_path / subdir
            if d.is_dir():
                bins.extend(
                    f.name for f in d.iterdir() if f.is_file()
                )
        return sorted(bins)

    def list_man_sections(self) -> Dict[str, int]:
        """Count man pages per section."""
        sections: Dict[str, int] = {}
        for base in (self.opt_path / "man", self.opt_path / "share" / "man"):
            if not base.is_dir():
                continue
            for sec_dir in base.iterdir():
                if sec_dir.is_dir() and sec_dir.name.startswith("man"):
                    count = sum(1 for _ in sec_dir.rglob("*") if _.is_file())
                    if count:
                        sections[sec_dir.name] = count
        return sections

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "version": self.version,
            "full_name": self.full_name,
            "opt_path": str(self.opt_path),
            "etc_path": str(self.etc_path) if self.etc_path else None,
            "var_path": str(self.var_path) if self.var_path else None,
            "has_bin": self.has_bin,
            "has_man": self.has_man,
            "binaries": self.list_binaries(),
            "man_sections": self.list_man_sections(),
            "description": self.manifest.description,
            "installed_at": self.manifest.installed_at,
            "file_count": self.manifest.file_count,
            "total_size": self.manifest.total_size,
        }


# ── Manager ────────────────────────────────────────────────────────────

class OptPackageManager:
    """
    Manages third-party package installation under ``/opt``.

    Parameters
    ----------
    opt_root : str | Path
        Override the /opt root (default ``/opt``).
    """

    def __init__(self, opt_root: str | Path = OPT_ROOT) -> None:
        self.root = Path(opt_root)

    def _pkg_dir(self, name: str, provider: str = "") -> Path:
        if provider:
            return self.root / provider / name
        return self.root / name

    def _manifest_path(self, name: str, provider: str = "") -> Path:
        return self._pkg_dir(name, provider) / MANIFEST_NAME

    def is_installed(self, name: str, provider: str = "") -> bool:
        """Check if a package is installed."""
        return self._manifest_path(name, provider).exists()

    def get_package(self, name: str, provider: str = "") -> Optional[InstalledPackage]:
        """Retrieve information about an installed package."""
        mp = self._manifest_path(name, provider)
        manifest = PackageManifest.from_file(mp)
        if manifest is None:
            return None

        pkg_dir = self._pkg_dir(name, provider)
        etc_p = Path("/etc/opt") / (provider + "/" + name if provider else name)
        var_p = Path("/var/opt") / (provider + "/" + name if provider else name)

        return InstalledPackage(
            manifest=manifest,
            opt_path=pkg_dir,
            etc_path=etc_p if etc_p.exists() else None,
            var_path=var_p if var_p.exists() else None,
        )

    def list_packages(self) -> List[InstalledPackage]:
        """List all installed packages under /opt."""
        if not self.root.exists():
            return []

        packages: List[InstalledPackage] = []

        for item in sorted(self.root.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith("."):
                continue

            # Direct package: /opt/<pkg>/manifest.json
            if (item / MANIFEST_NAME).exists():
                pkg = self._load_installed(item, provider="")
                if pkg:
                    packages.append(pkg)
                continue

            # Provider directory: /opt/<provider>/<pkg>/manifest.json
            for sub in sorted(item.iterdir()):
                if not sub.is_dir() or sub.name.startswith("."):
                    continue
                if (sub / MANIFEST_NAME).exists():
                    pkg = self._load_installed(sub, provider=item.name)
                    if pkg:
                        packages.append(pkg)

        return packages

    def _load_installed(self, pkg_dir: Path, provider: str) -> Optional[InstalledPackage]:
        manifest = PackageManifest.from_file(pkg_dir / MANIFEST_NAME)
        if manifest is None:
            return None
        etc_p = Path("/etc/opt") / (provider + "/" + pkg_dir.name if provider else pkg_dir.name)
        var_p = Path("/var/opt") / (provider + "/" + pkg_dir.name if provider else pkg_dir.name)
        return InstalledPackage(
            manifest=manifest,
            opt_path=pkg_dir,
            etc_path=etc_p if etc_p.exists() else None,
            var_path=var_p if var_p.exists() else None,
        )

    def install(
        self,
        name: str,
        source: str | Path,
        provider: str = "",
        *,
        version: str = "",
        description: str = "",
        dependencies: Optional[List[str]] = None,
        checksum: str = "",
    ) -> InstalledPackage:
        """
        Install a package from a tar.gz archive into /opt.

        The archive root must contain ``bin/``, ``lib/``, etc. directories.
        A ``manifest.json`` is written automatically.

        Parameters
        ----------
        name : str
            Package name.
        source : str | Path
            Path to a ``.tar.gz`` or ``.tgz`` archive.
        provider : str, optional
            Provider/vendor name (creates ``/opt/<provider>/<name>/``).
        version : str, optional
            Package version string.
        description : str, optional
            Human-readable description.
        dependencies : list[str], optional
            List of required package names.
        checksum : str, optional
            SHA-256 checksum of the archive for verification.

        Returns
        -------
        InstalledPackage
        """
        dest = self._pkg_dir(name, provider)
        if dest.exists():
            raise FileExistsError(f"Package already installed: {dest}")

        src_path = Path(source)
        if not src_path.exists():
            raise FileNotFoundError(f"Source archive not found: {src_path}")

        # Verify checksum if provided
        if checksum:
            actual = self._sha256(src_path)
            if actual != checksum:
                raise ValueError(
                    f"Checksum mismatch: expected {checksum}, got {actual}"
                )

        # Extract
        dest.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(str(src_path), "r:gz") as tar:
                tar.extractall(path=str(dest))
        except Exception as exc:
            # Clean up on failure
            if dest.exists():
                shutil.rmtree(dest)
            raise RuntimeError(f"Failed to extract {src_path}: {exc}") from exc

        # Build manifest
        file_count = sum(1 for _ in dest.rglob("*") if _.is_file())
        total_size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())

        manifest = PackageManifest(
            name=name,
            provider=provider,
            version=version,
            description=description,
            dependencies=dependencies or [],
            installed_at=time.time(),
            install_path=str(dest),
            file_count=file_count,
            total_size=total_size,
            checksum=checksum or self._sha256(src_path),
        )
        manifest.save(dest / MANIFEST_NAME)

        log.info(
            "Installed package: %s (%d files, %d bytes)",
            manifest.full_name,
            file_count,
            total_size,
        )

        return InstalledPackage(manifest=manifest, opt_path=dest)

    def uninstall(self, name: str, provider: str = "", *, keep_config: bool = True) -> bool:
        """
        Remove an installed package from /opt.

        Parameters
        ----------
        name : str
            Package name.
        provider : str, optional
            Provider name.
        keep_config : bool
            If True, preserve /etc/opt/<pkg> (default True).

        Returns
        -------
        bool
            True if the package was found and removed.
        """
        pkg_dir = self._pkg_dir(name, provider)
        mp = pkg_dir / MANIFEST_NAME
        if not mp.exists():
            log.warning("Package not found: %s", name)
            return False

        try:
            shutil.rmtree(pkg_dir)
        except OSError as exc:
            log.error("Failed to remove %s: %s", pkg_dir, exc)
            return False

        # Clean up empty provider directory
        if provider:
            provider_dir = self.root / provider
            if provider_dir.exists() and not any(provider_dir.iterdir()):
                provider_dir.rmdir()

        if not keep_config:
            etc_pkg = DEFAULT_ETC_OPT / (provider + "/" + name if provider else name)
            if etc_pkg.exists():
                shutil.rmtree(etc_pkg)

        log.info("Uninstalled package: %s", name)
        return True

    def upgrade(
        self,
        name: str,
        source: str | Path,
        provider: str = "",
        *,
        version: str = "",
        **kwargs: Any,
    ) -> InstalledPackage:
        """
        Upgrade a package by uninstalling then reinstalling.

        The existing ``/etc/opt/<pkg>`` configuration is preserved.
        """
        old_etc = DEFAULT_ETC_OPT / (provider + "/" + name if provider else name)
        had_etc = old_etc.exists()

        self.uninstall(name, provider, keep_config=True)
        pkg = self.install(name, source, provider, version=version, **kwargs)

        if not had_etc and old_etc.exists():
            # Installer shouldn't have created etc, clean it
            pass

        log.info("Upgraded package: %s -> %s", name, pkg.version)
        return pkg

    def info(self, name: str, provider: str = "") -> Optional[Dict[str, Any]]:
        """Return package information as a dict."""
        pkg = self.get_package(name, provider)
        if pkg is None:
            return None
        return pkg.to_dict()

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # ── Summary ────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of installed packages."""
        packages = self.list_packages()
        total_files = sum(p.manifest.file_count for p in packages)
        total_size = sum(p.manifest.total_size for p in packages)
        return {
            "total_packages": len(packages),
            "total_files": total_files,
            "total_size_bytes": total_size,
            "packages": [p.to_dict() for p in packages],
        }


# ── Selftest ───────────────────────────────────────────────────────────

def _selftest() -> bool:
    """Run basic self-tests for OptPackageManager."""
    import tempfile

    print("[opt/package] selftest …")
    ok = True

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "opt"
        mgr = OptPackageManager(opt_root=root)

        # 1  empty state
        assert not mgr.is_installed("foo")
        assert mgr.list_packages() == []
        print("  [PASS] empty state")

        # 2  create a fake tar.gz package
        #    Archive root must contain bin/, lib/ directly so they land
        #    in dest/ after extraction (not dest/<name>/).
        staging = Path(td) / "staging"
        (staging / "bin").mkdir(parents=True)
        (staging / "bin" / "myapp").write_text("#!/bin/sh\necho hi", encoding="utf-8")
        (staging / "lib").mkdir()
        (staging / "lib" / "libmy.so").write_bytes(b"\x00" * 100)
        tar_path = Path(td) / "myapp.tar.gz"
        with tarfile.open(str(tar_path), "w:gz") as tar:
            tar.add(str(staging / "bin"), arcname="bin")
            tar.add(str(staging / "lib"), arcname="lib")
        print("  [PASS] created test archive")

        # 3  install
        pkg = mgr.install(
            "myapp",
            tar_path,
            provider="testvendor",
            version="1.0.0",
            description="Test app",
            dependencies=["libc"],
        )
        assert pkg.name == "myapp"
        assert pkg.provider == "testvendor"
        assert pkg.version == "1.0.0"
        assert pkg.has_bin
        assert "myapp" in pkg.list_binaries()
        print("  [PASS] install + metadata")

        # 4  is_installed
        assert mgr.is_installed("myapp", "testvendor")
        assert not mgr.is_installed("myapp")
        print("  [PASS] is_installed")

        # 5  get_package
        got = mgr.get_package("myapp", "testvendor")
        assert got is not None
        assert got.manifest.dependencies == ["libc"]
        assert got.opt_path.is_dir()
        print("  [PASS] get_package")

        # 6  list_packages
        pkgs = mgr.list_packages()
        assert len(pkgs) == 1
        assert pkgs[0].full_name == "testvendor/myapp"
        print("  [PASS] list_packages")

        # 7  info
        info = mgr.info("myapp", "testvendor")
        assert info is not None
        assert info["name"] == "myapp"
        print("  [PASS] info")

        # 8  checksum verification
        bad = Path(td) / "bad.tar.gz"
        shutil.copy2(tar_path, bad)
        try:
            mgr.install("bad", bad, checksum="wrongchecksum")
            assert False, "should have raised"
        except ValueError:
            print("  [PASS] checksum verification")

        # 9  uninstall
        assert mgr.uninstall("myapp", "testvendor")
        assert not mgr.is_installed("myapp", "testvendor")
        assert mgr.list_packages() == []
        print("  [PASS] uninstall")

        # 10  install duplicate raises
        mgr.install("dup", tar_path, version="1.0")
        try:
            mgr.install("dup", tar_path, version="2.0")
            assert False, "should have raised FileExistsError"
        except FileExistsError:
            print("  [PASS] duplicate install raises FileExistsError")
        mgr.uninstall("dup")

        # 11  missing source raises
        try:
            mgr.install("nope", "/nonexistent/tar.gz")
            assert False, "should have raised"
        except FileNotFoundError:
            print("  [PASS] missing source raises FileNotFoundError")

        # 12  summary
        mgr.install("s", tar_path, version="1.0")
        s = mgr.get_summary()
        assert s["total_packages"] == 1
        print("  [PASS] get_summary")

    print("[opt/package] selftest PASSED")
    return ok


if __name__ == "__main__":
    _selftest()
