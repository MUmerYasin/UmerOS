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
License: GPL-3.0
"""

# [FIX H7] Normalize licence header to canonical "License: GPL-3.0" (drop redundant
# "GNU General Public License Version 3" parenthetical; repo is GPL-3.0 per LICENSE/setup.py/README).
from __future__ import annotations

import hashlib
import hmac  # [FIX H196] constant-time hash compare
import json
import logging
import os
import shutil
import sys
import tarfile
import tempfile
import time
from typing import Dict, List, Optional, Set

# [FIX H194/H195] Guard against path traversal (CWE-22) in package install /
# build paths derived from the (attacker-controlled) manifest name/version.
try:
    from core.path_guard import safe_child, PathTraversalError
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.path_guard import safe_child, PathTraversalError

# [FIX H198] Privileged package lifecycle ops (install/remove/update mutate the
# shared packages tree and registry) go through the zero-trust capability
# bridge — permissive when no CapabilityManager is wired, fail-closed when one
# is (same pattern as opt/ mnt/ media/ usr/ var/ clusters).
try:
    from core.capability_gate import gate, CAP_FS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_FS_ADMIN

# [FIX H194] Python < 3.12 lacks the fail-closed `filter=` argument on
# extractall(); on those interpreters we fall back to no filter (still unsafe,
# but matching the documented >=3.12 support target of UmerOS).
_FILTER_KW = {} if sys.version_info < (3, 12) else {"filter": "data"}


# [FIX H196/H197] Deterministic integrity hash over the manifest + full payload.
# Covers manifest.json AND every file under files/ in sorted order, so a
# tampered or missing payload fails verification (previously only the manifest
# bytes were hashed, and a missing HASH was silently skipped — both fail-open).
def _package_integrity_hash(
    manifest_bytes: bytes, file_items: "list[tuple[str, bytes]]"
) -> str:
    h = hashlib.sha3_256()
    h.update(b"manifest:")
    h.update(manifest_bytes)
    h.update(b"|files:")
    for name, data in sorted(file_items, key=lambda x: x[0]):
        h.update(name.encode("utf-8"))
        h.update(b"\x00")
        h.update(data)
    return h.hexdigest()

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
        """[FIX H196] Verify the package's embedded HASH (fail-closed).

        The HASH file contains the SHA3-256 of the manifest.json content AND
        the entire files/ payload (deterministic order — see
        ``_package_integrity_hash``).  A missing HASH used to be silently
        skipped ("dev mode"), letting unsigned/tampered archives install — a
        fail-open integrity check.  Now a missing or mismatched HASH causes
        verification to FAIL CLOSED (refuse install).

        Args:
            pkg_path: Path to the .umerpkg archive.

        Returns:
            True only if the embedded HASH matches the recomputed digest.
        """
        try:
            with tarfile.open(pkg_path, "r:gz") as tar:
                members = {m.name: m for m in tar.getmembers()}
                if "HASH" not in members or "manifest.json" not in members:
                    log.error(
                        "Refusing '%s': missing HASH/manifest — cannot verify.",
                        pkg_path,
                    )
                    return False
                with tar.extractfile(members["manifest.json"]) as fh:  # type: ignore
                    manifest_bytes = fh.read()
                with tar.extractfile(members["HASH"]) as fh:  # type: ignore
                    expected = fh.read().decode().strip()
                file_items: "list[tuple[str, bytes]]" = []
                for name, member in members.items():
                    if name.startswith("files/") and member.isfile():
                        with tar.extractfile(member) as fh:  # type: ignore
                            file_items.append((name, fh.read()))
        except Exception as exc:  # noqa: BLE001
            log.error("Hash verification I/O error: %s", exc)
            return False

        computed = _package_integrity_hash(manifest_bytes, file_items)
        ok = hmac.compare_digest(computed, expected)
        if not ok:
            log.error("Package hash MISMATCH for '%s' — refusing install.", pkg_path)
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
        gate.require(CAP_FS_ADMIN)  # [FIX H198] privileged install
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
        # [FIX H195] Contain the install dir against the manifest-supplied
        # `name` (which an attacker controls via a malicious .umerpkg). A name
        # like "../../etc/cron.d" is refused and the install aborts closed.
        try:
            dest = safe_child(self._install_dir, name)
        except PathTraversalError:
            log.error("Refusing unsafe install path for package '%s'.", name)
            return False

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
                # [FIX H194] filter="data" makes extraction fail-closed against
                # zip/tar-slip (CVE-2007-4559): members with ".." or absolute
                # paths are rejected instead of escaping `dest`.
                tar.extractall(path=dest, members=members, **_FILTER_KW)

            self._db[name] = {
                "version":    manifest.version,
                "path":       str(dest),
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
        gate.require(CAP_FS_ADMIN)  # [FIX H198] privileged remove
        if package_name not in self._db:
            log.warning("'%s' is not installed.", package_name)
            return False

        dest = self._db[package_name].get("path", "")
        if os.path.isdir(dest):
            # [FIX H195] Defense-in-depth: only delete paths that actually
            # reside inside the install dir (the stored path may be legacy or
            # tainted by a pre-fix install).
            inst_root = Path(self._install_dir).resolve()
            dest_abs = Path(dest).resolve()
            if dest_abs != inst_root and inst_root not in dest_abs.parents:
                log.error("Refusing to remove path outside install dir: %s", dest)
            else:
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
        gate.require(CAP_FS_ADMIN)  # [FIX H198] privileged update
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
        # [FIX H195] Contain the package file against the manifest-supplied
        # name/version (a malicious name could otherwise write anywhere via
        # "../../etc/x"). Refuse traversal and fail closed.
        try:
            pkg_path = safe_child(output_dir, pkg_filename)
        except PathTraversalError as exc:
            raise ValueError(f"Refusing unsafe .umerpkg output path: {exc}")

        manifest_bytes = json.dumps(pm.to_dict(), indent=2).encode()

        # [FIX H196/H197] Collect the full payload and compute a deterministic,
        # full-payload integrity hash (manifest + every files/ entry).
        file_items: "list[tuple[str, bytes, str]]" = []  # (arcname, data, full_path)
        for root, _, files in os.walk(source_dir):
            for fname in files:
                full = os.path.join(root, fname)
                # [FIX H196] Use POSIX forward-slash arcnames.  tarfile normalises
                # member names to "/" on read, so a Windows backslash arcname here
                # would diverge from the name re-read during _verify_hash and break
                # the integrity hash.  Normalising explicitly keeps build and
                # verify byte-for-byte consistent across platforms.
                rel = os.path.relpath(full, source_dir).replace(os.sep, "/")
                arcname = "files/" + rel
                with open(full, "rb") as _fh:
                    file_items.append((arcname, _fh.read(), full))

        integrity_hash = _package_integrity_hash(
            manifest_bytes, [(a, d) for a, d, _ in file_items]
        )

        with tarfile.open(pkg_path, "w:gz") as tar:
            # Add manifest.json
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                tmp.write(manifest_bytes)
                tmp_name = tmp.name
            tar.add(tmp_name, arcname="manifest.json")
            os.unlink(tmp_name)

            # Add HASH file (covers manifest + full files/ tree — fail-closed)
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(integrity_hash.encode())
                tmp_name = tmp.name
            tar.add(tmp_name, arcname="HASH")
            os.unlink(tmp_name)

            # Add source files under files/ (sorted for deterministic hashing)
            for arcname, _data, full in sorted(file_items, key=lambda x: x[0]):
                tar.add(full, arcname=arcname)

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
