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
UmerOS /opt Package Management

This module implements the core package management functionality for /opt
as per Filesystem Hierarchy standards.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

# Add canonical GPL-3.0 licence tag (repo is GPL-3.0 per LICENSE/setup.py/README).

from __future__ import annotations

import os
import re
import shlex
import sys
import shutil
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Any, List
from datetime import datetime

# Privileged /opt mutations go through the zero-trust capability
# bridge (permissive when no CapabilityManager is wired, fail-closed when one
# is). Same pattern as the mnt/ media/ usr/ var/ clusters.
try:
    from core.capability_gate import gate, CAP_FS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_FS_ADMIN

# Guard against path traversal (CWE-22) when building /opt package
# paths from caller-supplied name/provider.
try:
    from core.path_guard import safe_child, PathTraversalError
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.path_guard import safe_child, PathTraversalError


# Integrity manifest: SHA3-512 is the UmerOS design-mandate hash (the
# same algorithm the installer and initrd builders use).  The manifest is
# written *outside* the package tree it protects - under /etc/opt - so
# tampering with installed files cannot rewrite the record they are
# checked against.
MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1
HASH_ALGORITHM = "sha3-512"


def _sha3_512_file(path: Path) -> str:
    """Return the streamed SHA3-512 hex digest of ``path``."""
    digest = hashlib.sha3_512()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class OptPackage:
    """
    Represents an /opt package and manages its installation.
    
    - Packages are normally installed in /opt/'package' or /opt/'provider'/'package'
    - All static files must be in a separate directory tree
    - Programs to be invoked by users are in /opt/'package'/bin
    - Manual pages are in /opt/'package'/man
    """
    
    def __init__(
        self,
        name: str,
        provider: str = "",
        opt_root: str = "/opt",
        etc_opt_root: str = "/etc/opt",
        var_opt_root: str = "/var/opt",
    ):
        """
        Initialize OptPackage.
        
        Args:
            name: Package name
            provider: Optional provider name
            opt_root: Root directory for opt packages
            etc_opt_root: Root directory for opt configurations
            var_opt_root: Root directory for opt variable data
        """
        self.name = name
        self.provider = provider
        self.opt_root = Path(opt_root)
        # The etc/var roots are constructor-injectable so a
        # temp-root run cannot resolve them to the real system dirs.
        self.etc_opt_root = Path(etc_opt_root)
        self.var_opt_root = Path(var_opt_root)
        self._ensure_root()
        self._setup_paths()
    
    def _ensure_root(self) -> None:
        """Ensure /opt root directory exists."""
        self.opt_root.mkdir(parents=True, exist_ok=True)
    
    def _setup_paths(self) -> None:
        """Set up standard directory structure."""
        # Contain provider/name inside opt_root (CWE-22). A malicious
        # name like "../../etc" raises PathTraversalError so the constructor
        # fails closed instead of creating / removing anything outside /opt.
        if self.provider:
            scoped = safe_child(self.opt_root, self.provider)
        else:
            scoped = self.opt_root
        self.base_path = safe_child(scoped, self.name)

        self.bin_path = self.base_path / "bin"
        self.lib_path = self.base_path / "lib"
        self.include_path = self.base_path / "include"
        self.doc_path = self.base_path / "doc"
        self.info_path = self.base_path / "info"
        self.man_path = self.base_path / "man"
        self.src_path = self.base_path / "src"
        # etc/var roots are also contained against provider/name.
        # contained against provider/name *and* honouring the
        # constructor overrides, so a temp-root run cannot resolve the
        # package's etc/var trees to the real system directories.
        if self.provider:
            etc_root = safe_child(self.etc_opt_root, self.provider)
            var_root = safe_child(self.var_opt_root, self.provider)
        else:
            etc_root = Path(self.etc_opt_root)
            var_root = Path(self.var_opt_root)
        self.etc_path = safe_child(etc_root, self.name)
        self.var_path = safe_child(var_root, self.name)

        # Create all directories
        for path in [self.base_path, self.bin_path, self.lib_path, self.include_path,
                     self.doc_path, self.info_path, self.man_path, self.src_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def install_binary(self, source_path: str, target_name: str = "") -> Path:
        """
        Install a binary executable to the package's bin directory.
        
        Args:
            source_path: Path to the source binary
            target_name: Optional target name (defaults to source filename)
            
        Returns:
            Path to the installed binary
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        if not target_name:
            target_name = source.name
        
        target = self.bin_path / target_name
        shutil.copy2(source, target)
        target.chmod(0o755)  # Make executable
        
        return target
    
    def install_library(self, source_path: str, target_name: str = "") -> Path:
        """
        Install a library file to the package's lib directory.
        
        Args:
            source_path: Path to the source library
            target_name: Optional target name (defaults to source filename)
            
        Returns:
            Path to the installed library
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        if not target_name:
            target_name = source.name
        
        target = self.lib_path / target_name
        shutil.copy2(source, target)
        
        return target
    
    def install_documentation(self, source_path: str, target_name: str = "") -> Path:
        """
        Install documentation to the package's doc directory.
        
        Args:
            source_path: Path to the source documentation
            target_name: Optional target name (defaults to source filename)
            
        Returns:
            Path to the installed documentation
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        if not target_name:
            target_name = source.name
        
        target = self.doc_path / target_name
        shutil.copy2(source, target)
        
        return target
    
    def install_man_page(self, source_path: str, section: str = "1") -> Path:
        """
        Install a manual page to the package's man directory.
        
        Args:
            source_path: Path to the source man page
            section: Man page section (1=user commands, 2=system calls, etc.)
            
        Returns:
            Path to the installed man page
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        # Man pages are organized as man<section>/<name>
        man_section_path = self.man_path / f"man{section}"
        man_section_path.mkdir(parents=True, exist_ok=True)
        
        target = man_section_path / source.name
        shutil.copy2(source, target)
        
        return target
    
    # --- script-generation hardening helpers ----------------------

    @staticmethod
    def _validate_script_name(script_name: str) -> str:
        """Reject path traversal / separators in generated script names."""
        if not script_name or os.path.basename(script_name) != script_name \
                or script_name in (".", "..") or "/" in script_name or "\\" in script_name:
            raise ValueError(f"unsafe launcher script name: {script_name!r}")
        return script_name

    @staticmethod
    def _reject_shell_metachar(token: str) -> str:
        """Refuse control chars / newlines that could forge extra shell lines."""
        if not token or any(ord(c) < 32 for c in token):
            raise ValueError(f"unsafe shell token (control characters): {token!r}")
        return token

    @staticmethod
    def _comment_safe(text: str) -> str:
        """Neutralize newlines so comments cannot smuggle shell lines."""
        return text.replace("\n", " ").replace("\r", " ")

    def create_launcher_script(self, script_name: str, command: str,
                                args: List[str] = None) -> Path:
        """
        Create a launcher script in the bin directory.

        The exec line is built with ``shlex.quote`` so neither the
        command nor any argument can break out of its shell word (previously
        ``exec {command} {' '.join(args)} "$@"`` interpolated raw — a crafted
        arg like ``; rm -rf / #`` injected commands). Control characters are
        rejected and script names cannot traverse out of bin/.

        Raises:
            ValueError: on unsafe names / commands / arguments.
        """
        safe_name = self._validate_script_name(script_name)
        clean_command = self._reject_shell_metachar(command)
        clean_args = [self._reject_shell_metachar(a) for a in (args or [])]

        script_path = self.bin_path / safe_name

        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Launcher script for {self._comment_safe(self.name)}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            quoted = " ".join(shlex.quote(a) for a in clean_args)
            f.write(f"exec {shlex.quote(clean_command)} {quoted} \"$@\"\n")

        script_path.chmod(0o755)
        return script_path
    
    def create_wrapper_script(self, script_name: str, target_binary: str,
                              environment: Dict[str, str] = None,
                              pre_args: List[str] = None,
                              post_args: List[str] = None) -> Path:
        """
        Create a wrapper script with environment setup.
        
        Args:
            script_name: Name of the wrapper script
            target_binary: Binary to execute
            environment: Optional environment variables
            pre_args: Arguments to pass before user args
            post_args: Arguments to pass after user args
            
        Returns:
            Path to the created script

        Same hardening as the launcher: every dynamic token is
        validated and ``shlex.quote``d; environment keys must be POSIX
        identifiers and values are single-quoted so ``"$(cmd)"`` or backtick
        payloads cannot execute when the wrapper is sourced.
        """
        safe_name = self._validate_script_name(script_name)
        clean_target = self._reject_shell_metachar(target_binary)
        clean_pre = [self._reject_shell_metachar(a) for a in (pre_args or [])]
        clean_post = [self._reject_shell_metachar(a) for a in (post_args or [])]

        script_path = self.bin_path / safe_name

        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Wrapper script for {self._comment_safe(self.name)}\n")
            f.write(f"# Wrapper for: {self._comment_safe(clean_target)}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")

            if environment:
                f.write("# Environment setup\n")
                for key, value in environment.items():
                    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                        raise ValueError(f"unsafe env var name: {key!r}")
                    safe_val = self._reject_shell_metachar(str(value))
                    f.write(f"export {key}={shlex.quote(safe_val)}\n")
                f.write("\n")

            f.write(f"exec {shlex.quote(clean_target)} ")
            if clean_pre:
                f.write(" ".join(shlex.quote(a) for a in clean_pre) + " ")
            f.write('$@')
            if clean_post:
                f.write(" " + " ".join(shlex.quote(a) for a in clean_post))
            f.write("\n")
        
        script_path.chmod(0o755)
        return script_path
    
    def remove(self) -> bool:
        """
        Remove the entire package directory.

        requires CAP_FS_ADMIN (privileged rmtree under /opt).

        Returns:
            True if removal was successful
        """
        gate.require(CAP_FS_ADMIN)
        try:
            if self.base_path.exists():
                shutil.rmtree(self.base_path)
            # Drop the integrity manifest as well, so a later
            # reinstall cannot inherit a stale record from this one.
            try:
                if self.manifest_path.exists():
                    self.manifest_path.unlink()
            except OSError:
                pass
            return True
        except Exception:
            return False
    
    def exists(self) -> bool:
        """Check if the package directory exists."""
        return self.base_path.exists()
    
    def get_installed_files(self) -> List[Path]:
        """Get list of all installed files."""
        if not self.base_path.exists():
            return []
        
        files = []
        for root, dirs, filenames in os.walk(self.base_path):
            for filename in filenames:
                files.append(Path(root) / filename)
        
        return files
    
    @property
    def manifest_path(self) -> Path:
        """Location of the integrity manifest (outside the package tree)."""
        return self.etc_path / MANIFEST_NAME

    def check_structure(self) -> Dict[str, bool]:
        """
        Check that the standard FHS subdirectories exist.

        This is the former ``verify_integrity`` body under an honest
        name: it says nothing about file contents and cannot detect
        tampering.
        """
        return {
            "bin": self.bin_path.exists() and self.bin_path.is_dir(),
            "lib": self.lib_path.exists() and self.lib_path.is_dir(),
            "include": self.include_path.exists() and self.include_path.is_dir(),
            "doc": self.doc_path.exists() and self.doc_path.is_dir(),
            "info": self.info_path.exists() and self.info_path.is_dir(),
            "man": self.man_path.exists() and self.man_path.is_dir(),
            "src": self.src_path.exists() and self.src_path.is_dir(),
        }

    def write_manifest(self) -> Path:
        """
        Record a SHA3-512 manifest of the package tree.

        Every regular file is hashed (streamed), every symlink has its
        target recorded, and every directory is listed, so content,
        permission and layout tampering are all detectable.  Symlinks
        are recorded as links instead of being followed, so the walk
        never crosses a link out of the package tree.

        The manifest is written under ``/etc/opt`` - *outside* the tree
        it protects - so rewriting installed files cannot rewrite the
        record they are verified against.

        Returns:
            Path to the written manifest.
        """
        entries: Dict[str, Any] = {}
        if self.base_path.is_symlink():
            # A package directory that is itself a link (the classic
            # /opt/foo -> /opt/foo-1.2.3 layout) is recorded as the link
            # it is; the target tree is verified when it is managed as a
            # package in its own right.  Otherwise the walk could leave
            # the package tree entirely.
            entries["."] = {"type": "link", "target": os.readlink(self.base_path)}
        elif self.base_path.exists():
            for root, dirs, filenames in os.walk(self.base_path):
                dirs.sort()
                base = Path(root)
                for dirname in list(dirs):
                    path = base / dirname
                    rel = path.relative_to(self.base_path).as_posix()
                    if path.is_symlink():
                        entries[rel] = {"type": "link", "target": os.readlink(path)}
                        dirs.remove(dirname)
                    else:
                        entries[rel] = {"type": "dir"}
                for filename in sorted(filenames):
                    path = base / filename
                    rel = path.relative_to(self.base_path).as_posix()
                    if path.is_symlink():
                        entries[rel] = {"type": "link", "target": os.readlink(path)}
                    elif path.is_file():
                        entries[rel] = {
                            "type": "file",
                            HASH_ALGORITHM: _sha3_512_file(path),
                            "mode": oct(path.stat().st_mode & 0o7777),
                        }
        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "algorithm": HASH_ALGORITHM,
            "package": self.name,
            "provider": self.provider,
            "generated": datetime.now().isoformat(),
            "entries": entries,
        }
        self.etc_path.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self.manifest_path

    def _read_manifest(self) -> Optional[Dict[str, Any]]:
        """Load and shape-check the manifest; ``None`` when unusable."""
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(raw, dict) or not isinstance(raw.get("entries"), dict):
            return None
        return raw

    def verify_integrity(self) -> Dict[str, bool]:
        """
        Verify the package against its recorded manifest.

        The previous implementation only checked that the seven standard
        subdirectories existed, while every caller (``OptManager.verify``,
        ``verify_all``, ``get_stats``, ``list_packages``) presented the
        result as package "integrity" - false assurance with no tamper
        detection.  It now compares the tree against the SHA3-512
        manifest written by ``write_manifest()``.

        Fails closed: with no manifest nothing can be confirmed, so
        ``manifest``/``complete``/``unmodified``/``clean`` are all False.

        Every value is a boolean so ``all(result.values())`` keeps
        working for the aggregate callers.

        Keys:
            structure   - standard bin/lib/include/doc/info/man/src dirs exist
            manifest    - a manifest exists and parses
            complete    - no manifest-listed entry is missing
            unmodified  - every entry matches its recorded digest/mode/target
            clean       - nothing untracked was added afterwards
        """
        results = {
            "structure": all(self.check_structure().values()),
            "manifest": False,
            "complete": False,
            "unmodified": False,
            "clean": False,
        }
        manifest = self._read_manifest()
        if manifest is None:
            return results
        results["manifest"] = True

        differences = self._compare_manifest(manifest)
        results["complete"] = not differences["missing"]
        results["unmodified"] = not differences["modified"]
        results["clean"] = not differences["untracked"]
        return results

    def _compare_manifest(self, manifest: Dict[str, Any]) -> Dict[str, List[str]]:
        """Diff the live package tree against a parsed manifest."""
        recorded = manifest.get("entries", {})
        missing: List[str] = []
        modified: List[str] = []
        seen: set = set()

        for rel, entry in sorted(recorded.items()):
            if not isinstance(entry, dict):
                modified.append(rel)
                continue
            path = self.base_path if rel == "." else self.base_path / rel
            if not path.exists() and not path.is_symlink():
                missing.append(rel)
                continue
            seen.add(rel)
            kind = entry.get("type")
            if kind == "link":
                if not path.is_symlink() or os.readlink(path) != entry.get("target"):
                    modified.append(rel)
            elif kind == "file":
                if path.is_symlink() or not path.is_file():
                    modified.append(rel)
                elif _sha3_512_file(path) != entry.get(HASH_ALGORITHM):
                    modified.append(rel)
                elif oct(path.stat().st_mode & 0o7777) != entry.get("mode"):
                    modified.append(rel)
            elif kind == "dir":
                if path.is_symlink() or not path.is_dir():
                    modified.append(rel)

        untracked: List[str] = []
        if self.base_path.exists() and not self.base_path.is_symlink():
            for root, dirs, filenames in os.walk(self.base_path):
                dirs.sort()
                base = Path(root)
                for dirname in dirs:
                    rel = (base / dirname).relative_to(self.base_path).as_posix()
                    if rel not in seen:
                        untracked.append(rel)
                for filename in sorted(filenames):
                    rel = (base / filename).relative_to(self.base_path).as_posix()
                    if rel not in seen:
                        untracked.append(rel)

        return {"missing": missing, "modified": modified, "untracked": untracked}

    def integrity_details(self) -> Dict[str, Any]:
        """
        Diagnostic detail behind ``verify_integrity``.

        Returns the per-category difference lists so an operator can see
        *what* changed, not merely that something did.
        """
        details: Dict[str, Any] = {
            "manifest_present": False,
            "manifest_path": str(self.manifest_path),
            "algorithm": HASH_ALGORITHM,
            "missing": [],
            "modified": [],
            "untracked": [],
            "structure": self.check_structure(),
        }
        manifest = self._read_manifest()
        if manifest is None:
            return details
        details["manifest_present"] = True
        details.update(self._compare_manifest(manifest))
        return details

class OptManager:
    """
    Manages all /opt packages.
    
    Provides functionality for:
    - Installing packages to /opt
    - Removing packages from /opt
    - Listing installed packages
    - Verifying package integrity
    - Managing package dependencies
    """
    
    def __init__(
        self,
        opt_root: str = "/opt",
        etc_opt_root: str = "/etc/opt",
        var_opt_root: str = "/var/opt",
    ):
        """
        Initialize OptManager.
        
        Args:
            opt_root: Root directory for opt packages
            etc_opt_root: Root directory for opt configurations
            var_opt_root: Root directory for opt variable data
        """
        self.opt_root = Path(opt_root)
        # forward the overrides so every OptPackage this manager
        # builds stays inside the caller's roots.
        self.etc_opt_root = Path(etc_opt_root)
        self.var_opt_root = Path(var_opt_root)
        self._ensure_root()
    
    def _ensure_root(self) -> None:
        """Ensure /opt root directory exists."""
        self.opt_root.mkdir(parents=True, exist_ok=True)
    
    def install_package(self, name: str, provider: str = "",
                       binary_path: str = "", doc_path: str = "") -> OptPackage:
        """
        Install a package to /opt.
        
        Args:
            name: Package name
            provider: Optional provider name
            binary_path: Optional path to binary to install
            doc_path: Optional path to documentation to install
            
        Returns:
            OptPackage instance
        """
        gate.require(CAP_FS_ADMIN)  # privileged /opt install
        package = OptPackage(
            name, provider, str(self.opt_root), str(self.etc_opt_root), str(self.var_opt_root)
        )
        
        # Install binary if provided
        if binary_path:
            package.install_binary(binary_path)
        
        # Install documentation if provided
        if doc_path:
            package.install_documentation(doc_path)

        # Record the integrity manifest so verify_integrity() has
        # real digests to check against instead of directory names.
        package.write_manifest()
        return package
    
    def remove_package(self, name: str, provider: str = "") -> bool:
        """
        Remove a package from /opt.
        
        Args:
            name: Package name
            provider: Optional provider name
            
        Returns:
            True if removal was successful
        """
        gate.require(CAP_FS_ADMIN)  # privileged /opt remove
        # Contain the package path; refuse traversal names.
        try:
            if provider:
                package_path = safe_child(safe_child(self.opt_root, provider), name)
            else:
                package_path = safe_child(self.opt_root, name)
        except PathTraversalError:
            return False

        if package_path.exists():
            shutil.rmtree(package_path)
            return True
        return False
    
    def get_package(self, name: str, provider: str = "") -> OptPackage:
        """
        Get an OptPackage instance for an existing package.
        
        Args:
            name: Package name
            provider: Optional provider name
            
        Returns:
            OptPackage instance
        """
        return OptPackage(
            name, provider, str(self.opt_root), str(self.etc_opt_root), str(self.var_opt_root)
        )
    
    def list_packages(self) -> List[Dict[str, Any]]:
        """
        List all installed packages.
        
        Returns:
            List of dictionaries with package information
        """
        packages = []
        
        if not self.opt_root.exists():
            return packages
        
        for item in sorted(self.opt_root.iterdir()):
            if not (item.is_dir() and not item.name.startswith('.')):
                continue
            # The previous `if item.is_dir():` was always true (the
            # enclosing test had already checked it), so the `else` was dead
            # code: the flat /opt/<pkg>/ layout was never listed and every
            # *subdirectory* of a package (bin, lib, include, ...) was reported
            # as a package in its own right.
            if (item / "bin").is_dir():
                packages.append({
                    "name": item.name,
                    "provider": "",
                    "path": item,
                    "integrity": OptPackage(
                        item.name,
                        "",
                        str(self.opt_root),
                        str(self.etc_opt_root),
                        str(self.var_opt_root),
                    ).verify_integrity()
                })
                continue
            for subitem in sorted(item.iterdir()):
                if not (subitem.is_dir() and not subitem.name.startswith('.')):
                    continue
                packages.append({
                    "name": subitem.name,
                    "provider": item.name,
                    "path": subitem,
                    "integrity": OptPackage(
                        subitem.name,
                        item.name,
                        str(self.opt_root),
                        str(self.etc_opt_root),
                        str(self.var_opt_root),
                    ).verify_integrity()
                })
        
        return sorted(packages, key=lambda x: x["name"])
    
    def verify_all(self) -> Dict[str, bool]:
        """
        Verify integrity of all installed packages.
        
        Returns:
            Dictionary with verification results
        """
        results = {}
        packages = self.list_packages()
        
        for package in packages:
            key = f"{package['provider']}/{package['name']}" if package['provider'] else package['name']
            results[key] = all(package['integrity'].values())
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about /opt packages.
        
        Returns:
            Dictionary with package statistics
        """
        packages = self.list_packages()
        
        stats = {
            "total_packages": len(packages),
            "total_providers": len(set(p["provider"] for p in packages if p["provider"])),
            "packages_without_provider": sum(1 for p in packages if not p["provider"]),
            "packages_with_provider": sum(1 for p in packages if p["provider"]),
            "packages_with_integrity_issues": sum(1 for p in packages if not all(p["integrity"].values()))
        }
        
        return stats


def _selftest() -> bool:
    """Run basic self-tests for OptPackage and the /opt package manager."""
    import tempfile

    print("[opt/package] selftest \u2026")

    with tempfile.TemporaryDirectory() as td:
        opt = Path(td) / "opt"
        etc = Path(td) / "etc-opt"
        var = Path(td) / "var-opt"

        # 1  constructor builds the standard FHS layout
        pkg = OptPackage("demo", "acme", str(opt), str(etc), str(var))
        # safe_child resolves paths while tempfile hands back Windows 8.3
        # short names, so compare resolved forms (the H189 lesson)
        assert Path(str(pkg.base_path)).resolve() == (opt / "acme" / "demo").resolve()
        assert Path(str(pkg.etc_path)).resolve() == (etc / "acme" / "demo").resolve()
        assert Path(str(pkg.var_path)).resolve() == (var / "acme" / "demo").resolve()
        for path in (pkg.bin_path, pkg.lib_path, pkg.include_path, pkg.doc_path,
                     pkg.info_path, pkg.man_path, pkg.src_path):
            assert path.is_dir(), path
        assert all(pkg.check_structure().values())
        print("  [PASS] constructor builds the standard layout")

        # 2  traversal names/providers fail closed (CWE-22)
        for bad_name, bad_provider in (("../../etc", ""), ("ok", "../../etc"),
                                       ("..", ""), ("a/../../b", "")):
            try:
                OptPackage(bad_name, bad_provider, str(opt), str(etc), str(var))
            except PathTraversalError:
                pass
            else:
                raise AssertionError(
                    f"traversal accepted: {bad_name!r}/{bad_provider!r}"
                )
        print("  [PASS] traversal name/provider refused")

        # 3  install helpers
        source = Path(td) / "tool"
        source.write_bytes(b"tool")
        assert pkg.install_binary(str(source)) == pkg.bin_path / "tool"
        library = Path(td) / "lib.so"
        library.write_bytes(b"\x00")
        assert pkg.install_library(str(library)) == pkg.lib_path / "lib.so"
        documentation = Path(td) / "README.md"
        documentation.write_text("# doc", encoding="utf-8")
        assert pkg.install_documentation(str(documentation)) == pkg.doc_path / "README.md"
        man_page = Path(td) / "tool.1"
        man_page.write_text(".TH TOOL 1", encoding="utf-8")
        assert pkg.install_man_page(str(man_page)) == pkg.man_path / "man1" / "tool.1"
        assert len(pkg.get_installed_files()) == 4
        print("  [PASS] install_binary/library/documentation/man_page")

        # 4  launcher/wrapper scripts quote every token (H187)
        launcher = pkg.create_launcher_script("run", "python3", ["-m", "demo; rm -rf /"])
        exec_line = [ln for ln in launcher.read_text(encoding="utf-8").splitlines()
                     if ln.startswith("exec ")][0]
        tokens = shlex.split(exec_line)
        assert tokens[1:3] == ["python3", "-m"], tokens
        assert ";" not in tokens and "rm" not in tokens, tokens
        assert tokens[-1] == "$@"
        wrapper = pkg.create_wrapper_script(
            "wrap", "python3", environment={"MODE": "1"}, pre_args=["--flag"]
        )
        wrapper_text = wrapper.read_text(encoding="utf-8")
        assert "export MODE=1" in wrapper_text, wrapper_text
        for bad_script in ("../escape.sh", "sub/dir.sh", "..", ""):
            try:
                pkg.create_launcher_script(bad_script, "true")
            except ValueError:
                pass
            else:
                raise AssertionError(f"unsafe script name accepted: {bad_script!r}")
        print("  [PASS] launcher/wrapper scripts quote every token")

        # 5  integrity: manifest verification detects tampering (H190)
        pkg.write_manifest()
        assert all(pkg.verify_integrity().values())
        victim = pkg.bin_path / "tool"
        original = victim.read_bytes()
        try:
            victim.write_bytes(b"evil")
            result = pkg.verify_integrity()
            assert result["unmodified"] is False, result
            assert pkg.integrity_details()["modified"] == ["bin/tool"]
        finally:
            victim.write_bytes(original)
        assert all(pkg.verify_integrity().values())
        print("  [PASS] manifest verification detects tampering")

        # 6  remove clears the tree and the manifest
        assert pkg.remove() is True
        assert not pkg.base_path.exists()
        assert not pkg.manifest_path.exists()
        print("  [PASS] remove clears package and manifest")

        # 7  OptManager: install/list/verify_all/stats/remove
        manager = OptManager(str(opt), str(etc), str(var))
        manager.install_package("alpha")
        manager.install_package("beta", "prov")
        assert {e["name"] for e in manager.list_packages()} == {"alpha", "beta"}
        assert manager.verify_all() == {"alpha": True, "prov/beta": True}
        assert manager.get_stats()["total_packages"] == 2
        assert manager.remove_package("alpha") is True
        assert manager.remove_package("../../etc") is False
        assert manager.remove_package("..") is False
        print("  [PASS] OptManager install/list/verify_all/remove")

        # 8  cap-gate: remove is privileged, fail-closed when strict
        gated = OptPackage("gated", "", str(opt), str(etc), str(var))
        previous = gate.strict
        try:
            gate.set_strict(True)
            try:
                gated.remove()
            except PermissionError:
                pass
            else:
                raise AssertionError("remove is not capability-gated")
            try:
                manager.install_package("gated")
            except PermissionError:
                pass
            else:
                raise AssertionError("install_package is not capability-gated")
        finally:
            gate.set_strict(previous)
        print("  [PASS] remove / install_package are capability-gated")

    print("[opt/package] selftest PASSED")
    return True


if __name__ == "__main__":
    # Self-test first: fail fast if the subsystem regressed.
    if not _selftest():
        raise SystemExit(1)

    # Demo usage
    import tempfile
    
    print("UmerOS /opt Package Manager Demo")
    print("=" * 50)
    
    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        
        # Create manager
        manager = OptManager(
            str(opt_root),
            str(Path(tmpdir) / "etc" / "opt"),
            str(Path(tmpdir) / "var" / "opt"),
        )
        print(f"\n1. Created /opt at: {opt_root}")
        
        # Install a package with binary
        print("\n2. Installing 'editor' package...")
        package = manager.install_package(
            "editor",
            binary_path=__file__,  # Using this file as a demo binary
            doc_path=__file__      # Using this file as demo documentation
        )
        print(f"   Package installed at: {package.base_path}")
        
        # Create launcher script
        print("\n3. Creating launcher script...")
        launcher = package.create_launcher_script("editor-launch", "python3", ["-m", "editor"])
        print(f"   Launcher created: {launcher}")
        
        # Record the integrity manifest (digests live outside /opt)
        manifest_path = package.write_manifest()
        print(f"   Manifest written: {manifest_path}")

        # Verify integrity
        print("\n4. Verifying package integrity...")
        integrity = package.verify_integrity()
        for check, ok in integrity.items():
            status = "✓" if ok else "✗"
            print(f"   {status} {check}")

        # Tamper with the installed binary and show it is detected
        installed_bin = package.bin_path / Path(__file__).name
        original = installed_bin.read_bytes()
        try:
            installed_bin.write_bytes(original + b"# tampered\n")
            detected = package.integrity_details()["modified"]
            print(f"   tampered file detected: {detected}")
        finally:
            installed_bin.write_bytes(original)
        restored = all(package.verify_integrity().values())
        print(f"   restored and verified: {restored}")
        
        # List packages
        print("\n5. Listing packages...")
        packages = manager.list_packages()
        for pkg in packages:
            provider = f" [{pkg['provider']}]" if pkg['provider'] else ""
            print(f"   - {pkg['name']}{provider}")
        
        # Get stats
        print("\n6. Getting statistics...")
        stats = manager.get_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        # Remove package
        print("\n7. Removing package...")
        removed = manager.remove_package("editor")
        print(f"   Removal successful: {removed}")
    
    print("\nDemo completed successfully!")
