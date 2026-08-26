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

License: GPL-3.0
"""

# [FIX H7] Add canonical GPL-3.0 licence tag (repo is GPL-3.0 per LICENSE/setup.py/README).

import os
import re
import shlex
import sys
import shutil
from pathlib import Path
from typing import Dict, Optional, Any, List
from datetime import datetime

# [FIX H184] Privileged /opt mutations go through the zero-trust capability
# bridge (permissive when no CapabilityManager is wired, fail-closed when one
# is). Same pattern as the mnt/ media/ usr/ var/ clusters.
try:
    from core.capability_gate import gate, CAP_FS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_FS_ADMIN

# [FIX H186] Guard against path traversal (CWE-22) when building /opt package
# paths from caller-supplied name/provider.
try:
    from core.path_guard import safe_child, PathTraversalError
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.path_guard import safe_child, PathTraversalError


class OptPackage:
    """
    Represents an /opt package and manages its installation.
    
    - Packages are normally installed in /opt/'package' or /opt/'provider'/'package'
    - All static files must be in a separate directory tree
    - Programs to be invoked by users are in /opt/'package'/bin
    - Manual pages are in /opt/'package'/man
    """
    
    def __init__(self, name: str, provider: str = "", opt_root: str = "/opt"):
        """
        Initialize OptPackage.
        
        Args:
            name: Package name
            provider: Optional provider name
            opt_root: Root directory for opt packages
        """
        self.name = name
        self.provider = provider
        self.opt_root = Path(opt_root)
        self._ensure_root()
        self._setup_paths()
    
    def _ensure_root(self) -> None:
        """Ensure /opt root directory exists."""
        self.opt_root.mkdir(parents=True, exist_ok=True)
    
    def _setup_paths(self) -> None:
        """Set up standard directory structure."""
        # [FIX H186] Contain provider/name inside opt_root (CWE-22). A malicious
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
        # [FIX H186] etc/var roots are also contained against provider/name.
        if self.provider:
            etc_root = safe_child(Path("/etc/opt"), self.provider)
            var_root = safe_child(Path("/var/opt"), self.provider)
        else:
            etc_root = Path("/etc/opt")
            var_root = Path("/var/opt")
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
    
    # -- [FIX H187] script-generation hardening helpers ----------------------

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

        [FIX H187] The exec line is built with ``shlex.quote`` so neither the
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

        [FIX H187] Same hardening as the launcher: every dynamic token is
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

        [FIX H184] requires CAP_FS_ADMIN (privileged rmtree under /opt).

        Returns:
            True if removal was successful
        """
        gate.require(CAP_FS_ADMIN)
        try:
            if self.base_path.exists():
                shutil.rmtree(self.base_path)
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
    
    def verify_integrity(self) -> Dict[str, bool]:
        """
        Verify the package integrity by checking required directories.
        
        Returns:
            Dictionary with verification results
        """
        results = {
            "bin": self.bin_path.exists() and self.bin_path.is_dir(),
            "lib": self.lib_path.exists() and self.lib_path.is_dir(),
            "include": self.include_path.exists() and self.include_path.is_dir(),
            "doc": self.doc_path.exists() and self.doc_path.is_dir(),
            "info": self.info_path.exists() and self.info_path.is_dir(),
            "man": self.man_path.exists() and self.man_path.is_dir(),
            "src": self.src_path.exists() and self.src_path.is_dir(),
        }
        
        return results


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
    
    def __init__(self, opt_root: str = "/opt"):
        """
        Initialize OptManager.
        
        Args:
            opt_root: Root directory for opt packages
        """
        self.opt_root = Path(opt_root)
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
        gate.require(CAP_FS_ADMIN)  # [FIX H184] privileged /opt install
        package = OptPackage(name, provider, str(self.opt_root))
        
        # Install binary if provided
        if binary_path:
            package.install_binary(binary_path)
        
        # Install documentation if provided
        if doc_path:
            package.install_documentation(doc_path)
        
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
        gate.require(CAP_FS_ADMIN)  # [FIX H184] privileged /opt remove
        # [FIX H186] Contain the package path; refuse traversal names.
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
        return OptPackage(name, provider, str(self.opt_root))
    
    def list_packages(self) -> List[Dict[str, Any]]:
        """
        List all installed packages.
        
        Returns:
            List of dictionaries with package information
        """
        packages = []
        
        if not self.opt_root.exists():
            return packages
        
        for item in self.opt_root.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it's a provider directory or a package
                if item.is_dir():
                    for subitem in item.iterdir():
                        if subitem.is_dir() and not subitem.name.startswith('.'):
                            package = OptPackage(subitem.name, item.name, str(self.opt_root))
                            packages.append({
                                "name": subitem.name,
                                "provider": item.name,
                                "path": subitem,
                                "integrity": package.verify_integrity()
                            })
                else:
                    package = OptPackage(item.name, "", str(self.opt_root))
                    packages.append({
                        "name": item.name,
                        "provider": "",
                        "path": item,
                        "integrity": package.verify_integrity()
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


if __name__ == "__main__":
    # Demo usage
    import tempfile
    
    print("UmerOS /opt Package Manager Demo")
    print("=" * 50)
    
    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        
        # Create manager
        manager = OptManager(str(opt_root))
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
        
        # Verify integrity
        print("\n4. Verifying package integrity...")
        integrity = package.verify_integrity()
        for dir_name, exists in integrity.items():
            status = "✓" if exists else "✗"
            print(f"   {status} {dir_name}")
        
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
