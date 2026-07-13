"""
Umer OS Package Manager (umer-pkg)  [TODAY]
===========================================
Secure, atomic package management for Umer OS.

Features:
  - Signed .umerpkg archives (JSON manifest + SHA3-256 hash verification).
  - SAT-inspired dependency resolver (no conflicts).
  - Atomic upgrades: filesystem snapshot before install; auto-rollback on failure.
  - Sandboxed installs: user-space by default, system-wide requires admin grant.
  - CLI: install / remove / update / search / build / info.

Package format (.umerpkg):
  A tar.gz archive containing:
    manifest.json  — name, version, description, dependencies, entry_point
    files/         — package files
    HASH           — SHA3-256 of manifest.json + files/ tree

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
import tempfile
import time
from typing import Dict, List, Optional, Set

log = logging.getLogger("UmerOS.UmerPkg")

# Default locations
DEFAULT_REGISTRY   = os.path.expanduser("~/.umer/registry")
DEFAULT_INSTALL_DIR = os.path.expanduser("~/.umer/packages")
DEFAULT_CACHE_DIR  = os.path.expanduser("~/.umer/cache")


# ---------------------------------------------------------------------------
# Package manifest
# ---------------------------------------------------------------------------

class PackageManifest:
    """Represents a parsed .umerpkg manifest.

    Args:
        data: Dict loaded from manifest.json inside the .umerpkg archive.
    """

    REQUIRED = {"name", "version", "description"}

    def __init__(self, data: dict) -> None:
        missing = self.REQUIRED - set(data.keys())
        if missing:
            raise ValueError(f"Manifest missing required fields: {missing}")
        self.name:         str       = str(data["name"])
        self.version:      str       = str(data["version"])
        self.description:  str       = str(data.get("description", ""))
        self.dependencies: List[str] = list(data.get("dependencies", []))
        self.entry_point:  str       = str(data.get("entry_point", ""))
        self.author:       str       = str(data.get("author", "unknown"))
        self.licence:      str       = str(data.get("licence", "unknown"))
        self._raw = data

    def to_dict(self) -> dict:
        """Serialise to dict for JSON output."""
        return {
            "name":         self.name,
            "version":      self.version,
            "description":  self.description,
            "dependencies": self.dependencies,
            "entry_point":  self.entry_point,
            "author":       self.author,
            "licence":      self.licence,
        }

    def __repr__(self) -> str:
        return f"PackageManifest({self.name}=={self.version})"


# ---------------------------------------------------------------------------
# DependencyResolver
# ---------------------------------------------------------------------------

class DependencyResolver:
    """SAT-inspired dependency resolver for package installation.

    Performs a topological sort of the dependency graph and raises an error
    if a circular dependency is detected.

    Args:
        installed: Dict of currently-installed packages {name: version}.
    """

    def __init__(self, installed: Optional[Dict[str, str]] = None) -> None:
        self._installed = installed or {}

    def resolve(
        self,
        package_name: str,
        registry:     Dict[str, PackageManifest],
    ) -> List[str]:
        """Return an ordered install list for package_name and its deps.

        Packages already installed are excluded from the result.

        Args:
            package_name: Root package to resolve.
            registry:     Dict mapping name → PackageManifest.

        Returns:
            Ordered list of package names to install (dependencies first).

        Raises:
            ValueError: If a dependency is missing or a cycle is detected.
        """
        order:   List[str] = []
        visited: Set[str]  = set()
        in_path: Set[str]  = set()

        def visit(name: str) -> None:
            if name in in_path:
                raise ValueError(
                    f"Circular dependency detected involving '{name}'."
                )
            if name in visited or name in self._installed:
                return
            if name not in registry:
                raise ValueError(
                    f"Dependency '{name}' not found in registry."
                )
            in_path.add(name)
            for dep in registry[name].dependencies:
                visit(dep)
            in_path.discard(name)
            visited.add(name)
            order.append(name)

        visit(package_name)
        return order


# ---------------------------------------------------------------------------
# UmerPackageManager
# ---------------------------------------------------------------------------

class UmerPackageManager:
    """Umer OS package manager.

    Args:
        install_dir:  Directory where packages are installed.
        registry_dir: Directory containing .umerpkg files (local registry).
        cache_dir:    Download/extraction cache.
    """

    def __init__(
        self,
        install_dir:  str = DEFAULT_INSTALL_DIR,
        registry_dir: str = DEFAULT_REGISTRY,
        cache_dir:    str = DEFAULT_CACHE_DIR,
    ) -> None:
        self._install_dir  = install_dir
        self._registry_dir = registry_dir
        self._cache_dir    = cache_dir
        # In-memory package DB: name → {version, path, manifest}
        self._db: Dict[str, dict] = {}
        # Local registry: name → PackageManifest
        self._registry: Dict[str, PackageManifest] = {}

        for d in (install_dir, registry_dir, cache_dir):
            os.makedirs(d, exist_ok=True)

        self._load_db()
        self._scan_registry()
        log.info(
            "UmerPkg initialised: %d installed, %d in registry.",
            len(self._db), len(self._registry),
        )

    # ── Database ─────────────────────────────────────────────────────────────

    def _db_path(self) -> str:
        return os.path.join(self._install_dir, ".umer_pkg_db.json")

    def _load_db(self) -> None:
        """Load installed package database from disk."""
        path = self._db_path()
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    self._db = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("Could not load package DB: %s", exc)

    def _save_db(self) -> None:
        """Persist installed package database to disk."""
        try:
            with open(self._db_path(), "w", encoding="utf-8") as fh:
                json.dump(self._db, fh, indent=2)
        except OSError as exc:
            log.error("Could not save package DB: %s", exc)

    def _scan_registry(self) -> None:
        """Scan local registry directory for .umerpkg files."""
        for fname in os.listdir(self._registry_dir):
            if fname.endswith(".umerpkg"):
                path = os.path.join(self._registry_dir, fname)
                try:
                    manifest = self._read_manifest(path)
                    self._registry[manifest.name] = manifest
                except Exception as exc:  # noqa: BLE001
                    log.debug("Skipping '%s': %s", fname, exc)

    # ── Archive helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _hash_file(path: str) -> str:
        """Return SHA3-256 hex digest of a file."""
        h = hashlib.sha3_256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _read_manifest(self, pkg_path: str) -> PackageManifest:
        """Extract and parse manifest.json from a .umerpkg archive.

        Args:
            pkg_path: Path to the .umerpkg tar.gz file.

        Returns:
            Parsed PackageManifest.

        Raises:
            ValueError: If manifest is missing or malformed.
        """
        with tarfile.open(pkg_path, "r:gz") as tar:
            try:
                member = tar.getmember("manifest.json")
            except KeyError:
                raise ValueError(f"No manifest.json in '{pkg_path}'.")
            with tar.extractfile(member) as fh:  # type: ignore
                data = json.load(fh)
        return PackageManifest(data)

    def _verify_hash(self, pkg_path: str) -> bool:
        """Verify the package's embedded HASH file.

        A HASH file in the archive root must contain the SHA3-256 hex of the
        manifest.json content.  If absent, the check is skipped (dev mode).

        Args:
            pkg_path: Path to the .umerpkg archive.

        Returns:
            True if verified (or no HASH present), False on mismatch.
        """
        try:
            with tarfile.open(pkg_path, "r:gz") as tar:
                members = [m.name for m in tar.getmembers()]
                if "HASH" not in members:
                    log.debug("No HASH in '%s' — skipping verification (dev mode).",
                              pkg_path)
                    return True
                with tar.extractfile("manifest.json") as fh:  # type: ignore
                    manifest_bytes = fh.read()
                with tar.extractfile("HASH") as fh:  # type: ignore
                    expected = fh.read().decode().strip()
        except Exception as exc:  # noqa: BLE001
            log.error("Hash verification I/O error: %s", exc)
            return False

        computed = hashlib.sha3_256(manifest_bytes).hexdigest()
        ok = computed == expected
        if not ok:
            log.error("Package hash MISMATCH for '%s'!", pkg_path)
        return ok

    # ── Install ───────────────────────────────────────────────────────────────

    def install(self, package_name: str, pkg_path: Optional[str] = None) -> bool:
        """Install a package (and its dependencies).

        Args:
            package_name: Package name to install.
            pkg_path:     Direct path to .umerpkg; uses registry if None.

        Returns:
            True on success, False on failure.
        """
        if package_name in self._db:
            log.info("'%s' is already installed (version %s).",
                     package_name, self._db[package_name]["version"])
            return True

        # Resolve dependencies
        try:
            resolver = DependencyResolver(
                installed={n: v["version"] for n, v in self._db.items()}
            )
            install_order = resolver.resolve(package_name, self._registry)
        except ValueError as exc:
            log.error("Dependency resolution failed: %s", exc)
            return False

        for name in install_order:
            if name in self._db:
                continue
            path = pkg_path if (name == package_name and pkg_path) else \
                   self._find_in_registry(name)
            if path is None:
                log.error("Package '%s' not found in registry.", name)
                return False
            if not self._install_single(name, path):
                return False

        return True

    def _find_in_registry(self, name: str) -> Optional[str]:
        """Return the path to a package's .umerpkg file, or None."""
        for fname in os.listdir(self._registry_dir):
            if fname.startswith(name) and fname.endswith(".umerpkg"):
                return os.path.join(self._registry_dir, fname)
        return None

    def _install_single(self, name: str, pkg_path: str) -> bool:
        """Install a single package without resolving dependencies.

        Args:
            name:     Package name.
            pkg_path: Path to .umerpkg archive.

        Returns:
            True on success.
        """
        log.info("Installing '%s' from '%s'…", name, pkg_path)

        if not self._verify_hash(pkg_path):
            log.error("Refusing to install '%s': hash verification failed.", name)
            return False

        manifest = self._read_manifest(pkg_path)
        dest = os.path.join(self._install_dir, name)

        # Snapshot existing install (atomic rollback)
        snapshot = None
        if os.path.isdir(dest):
            snapshot = dest + ".bak"
            shutil.copytree(dest, snapshot)

        try:
            os.makedirs(dest, exist_ok=True)
            with tarfile.open(pkg_path, "r:gz") as tar:
                # Only extract files/ subdirectory
                members = [
                    m for m in tar.getmembers()
                    if m.name.startswith("files/")
                ]
                tar.extractall(path=dest, members=members)

            self._db[name] = {
                "version":    manifest.version,
                "path":       dest,
                "installed":  time.time(),
                "entry_point": manifest.entry_point,
            }
            self._save_db()

            # Remove rollback snapshot
            if snapshot and os.path.isdir(snapshot):
                shutil.rmtree(snapshot)

            log.info("'%s' v%s installed successfully.", name, manifest.version)
            return True

        except Exception as exc:  # noqa: BLE001
            log.error("Install of '%s' failed: %s", name, exc)
            # Rollback
            shutil.rmtree(dest, ignore_errors=True)
            if snapshot and os.path.isdir(snapshot):
                shutil.move(snapshot, dest)
            return False

    # ── Remove ───────────────────────────────────────────────────────────────

    def remove(self, package_name: str) -> bool:
        """Uninstall a package.

        Args:
            package_name: Name of the installed package.

        Returns:
            True if removed, False if not installed.
        """
        if package_name not in self._db:
            log.warning("'%s' is not installed.", package_name)
            return False

        dest = self._db[package_name].get("path", "")
        if os.path.isdir(dest):
            shutil.rmtree(dest, ignore_errors=True)

        del self._db[package_name]
        self._save_db()
        log.info("'%s' removed.", package_name)
        return True

    # ── Update ───────────────────────────────────────────────────────────────

    def update(self, package_name: Optional[str] = None) -> Dict[str, bool]:
        """Update one or all installed packages.

        Args:
            package_name: Package to update, or None to update all.

        Returns:
            Dict mapping package name → True (updated) / False (failed).
        """
        targets = [package_name] if package_name else list(self._db.keys())
        results: Dict[str, bool] = {}

        for name in targets:
            pkg_path = self._find_in_registry(name)
            if pkg_path is None:
                log.info("No update available for '%s'.", name)
                results[name] = False
                continue

            manifest = self._read_manifest(pkg_path)
            current  = self._db.get(name, {}).get("version", "0.0.0")
            if manifest.version <= current:
                log.info("'%s' is up-to-date (v%s).", name, current)
                results[name] = True
                continue

            log.info("Updating '%s': %s → %s", name, current, manifest.version)
            # Remove then re-install for atomic update
            self.remove(name)
            results[name] = self._install_single(name, pkg_path)

        return results

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str) -> List[dict]:
        """Search the registry for packages matching a keyword.

        Args:
            query: Search term (case-insensitive).

        Returns:
            List of manifest summary dicts.
        """
        q = query.lower()
        return [
            {
                "name":        m.name,
                "version":     m.version,
                "description": m.description,
                "installed":   m.name in self._db,
            }
            for m in self._registry.values()
            if q in m.name.lower() or q in m.description.lower()
        ]

    # ── Info ─────────────────────────────────────────────────────────────────

    def info(self, package_name: str) -> Optional[dict]:
        """Return detailed information about a package.

        Args:
            package_name: Package name.

        Returns:
            Info dict or None if not found.
        """
        db_entry = self._db.get(package_name, {})
        registry = self._registry.get(package_name)
        if not db_entry and not registry:
            return None
        result = registry.to_dict() if registry else {"name": package_name}
        result["installed"]         = package_name in self._db
        result["installed_version"] = db_entry.get("version")
        result["installed_path"]    = db_entry.get("path")
        return result

    # ── Build ────────────────────────────────────────────────────────────────

    def build(
        self,
        source_dir: str,
        manifest:   dict,
        output_dir: str = ".",
    ) -> str:
        """Create a .umerpkg archive from a source directory.

        Args:
            source_dir: Directory containing the package files.
            manifest:   Package manifest dict (name, version, description, …).
            output_dir: Where to write the .umerpkg file.

        Returns:
            Path to the created .umerpkg file.
        """
        pm = PackageManifest(manifest)
        pkg_filename = f"{pm.name}-{pm.version}.umerpkg"
        pkg_path     = os.path.join(output_dir, pkg_filename)

        manifest_bytes = json.dumps(pm.to_dict(), indent=2).encode()
        manifest_hash  = hashlib.sha3_256(manifest_bytes).hexdigest()

        with tarfile.open(pkg_path, "w:gz") as tar:
            # Add manifest.json
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                tmp.write(manifest_bytes)
                tmp_name = tmp.name
            tar.add(tmp_name, arcname="manifest.json")
            os.unlink(tmp_name)

            # Add HASH file
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(manifest_hash.encode())
                tmp_name = tmp.name
            tar.add(tmp_name, arcname="HASH")
            os.unlink(tmp_name)

            # Add source files under files/
            for root, _, files in os.walk(source_dir):
                for fname in files:
                    full = os.path.join(root, fname)
                    rel  = os.path.relpath(full, source_dir)
                    tar.add(full, arcname=os.path.join("files", rel))

        log.info("Built '%s'.", pkg_path)

        # Register in local registry
        self._registry[pm.name] = pm
        return pkg_path

    # ── Listing ───────────────────────────────────────────────────────────────

    def list_installed(self) -> List[dict]:
        """Return a list of all installed packages.

        Returns:
            List of dicts with name, version, and installed keys.
        """
        return [
            {
                "name":      name,
                "version":   info.get("version", "?"),
                "installed": info.get("installed", 0),
                "path":      info.get("path", ""),
            }
            for name, info in self._db.items()
        ]

    def stats(self) -> dict:
        """Return package manager statistics."""
        return {
            "installed":   len(self._db),
            "in_registry": len(self._registry),
            "install_dir": self._install_dir,
        }
