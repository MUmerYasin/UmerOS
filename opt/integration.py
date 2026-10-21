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
UmerOS /opt Integration Modules

This module provides integration points between /opt and the rest of the UmerOS system.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

log = logging.getLogger("UmerOS.Opt.Integration")


# a newline would let an attacker-controlled path escape a
# "#" comment line in a login-sourced script, so comments are flattened.
def _comment_safe(text: str) -> str:
    """Collapse CR/LF so *text* cannot escape a ``#`` comment line."""
    return text.replace("\r", " ").replace("\n", " ")


#  characters with no legitimate use in an /opt package directory
# name.  A name reaching a shell snippet as *code* instead of *data* is what
# made the old ``export PATH="{bin_path}:$PATH"`` interpolation exploitable.
_UNSAFE_NAME_CHARS = frozenset("\"'`$\\;&|<>()\n\r\t*?[]{}!#~")


def _drop_shell_unsafe(dirs: List[Path], root: Path) -> List[Path]:
    """
    Return *dirs* without any package whose name below *root* is shell-hostile.

    Only the components below *root* are inspected: the root is chosen by the
    administrator and every path that survives is still ``shlex.quote``-d, so
    this is defence in depth on the one segment a package install controls.
    """
    safe: List[Path] = []
    for directory in dirs:
        try:
            relative = directory.relative_to(root)
        except ValueError:
            log.warning("ignoring /opt path %r: not below %s", directory, root)
            continue
        if any(_UNSAFE_NAME_CHARS & set(part) for part in relative.parts):
            log.warning(
                "ignoring /opt path %r: a component contains shell metacharacters",
                directory,
            )
            continue
        safe.append(directory)
    return safe


class OptEnvironment:
    """
    Manages environment variables and PATH integration for /opt packages.
    
    Provides functionality to:
    - Add /opt package binaries to PATH
    - Set up library paths
    - Configure environment for /opt applications
    """
    
    def __init__(self, opt_root: str = "/opt", system_path: str = None):
        """
        Initialize OptEnvironment.
        
        Args:
            opt_root: Root directory for opt packages
            system_path: System PATH (default: os.environ['PATH'])
        """
        self.opt_root = Path(opt_root)
        self.system_path = system_path or os.environ.get('PATH', '')
        self._bin_paths = []
        self._lib_paths = []
    
    def _discover_packages(self) -> List[Path]:
        """Discover all installed packages in /opt."""
        packages = []
        
        if not self.opt_root.exists():
            return packages
        
        for item in self.opt_root.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it's a provider directory or a package
                if item.is_dir():
                    for subitem in item.iterdir():
                        if subitem.is_dir() and not subitem.name.startswith('.'):
                            packages.append(subitem)
                else:
                    packages.append(item)
        
        return packages
    
    def add_to_path(self, package_name: str, provider: str = "") -> bool:
        """
        Add a package's bin directory to PATH.
        
        Args:
            package_name: Package name
            provider: Optional provider name
            
        Returns:
            True if successful
        """
        if provider:
            package_path = self.opt_root / provider / package_name
        else:
            package_path = self.opt_root / package_name
        
        bin_path = package_path / "bin"
        if bin_path.exists() and bin_path.is_dir():
            self._bin_paths.append(str(bin_path))
            return True
        return False
    
    def add_library_path(self, package_name: str, provider: str = "") -> bool:
        """
        Add a package's lib directory to library paths.
        
        Args:
            package_name: Package name
            provider: Optional provider name
            
        Returns:
            True if successful
        """
        if provider:
            package_path = self.opt_root / provider / package_name
        else:
            package_path = self.opt_root / package_name
        
        lib_path = package_path / "lib"
        if lib_path.exists() and lib_path.is_dir():
            self._lib_paths.append(str(lib_path))
            return True
        return False
    
    def get_path_string(self) -> str:
        """Get updated PATH string with /opt packages."""
        current_paths = self.system_path.split(os.pathsep)
        
        # Add /opt bin paths
        for path in reversed(self._bin_paths):
            if path not in current_paths:
                current_paths.insert(0, path)
        
        return os.pathsep.join(current_paths)
    
    def get_library_path_string(self) -> str:
        """Get library path string with /opt packages."""
        return os.pathsep.join(self._lib_paths)
    
    def setup_package_environment(self, package_name: str, provider: str = "") -> Dict[str, str]:
        """
        Set up environment variables for a package.
        
        Args:
            package_name: Package name
            provider: Optional provider name
            
        Returns:
            Dictionary of environment variables
        """
        env = {}
        
        if provider:
            package_path = self.opt_root / provider / package_name
        else:
            package_path = self.opt_root / package_name
        
        # Set package-specific paths
        env['OPT_PACKAGE_ROOT'] = str(package_path)
        env['OPT_PACKAGE_BIN'] = str(package_path / "bin")
        env['OPT_PACKAGE_LIB'] = str(package_path / "lib")
        env['OPT_PACKAGE_INCLUDE'] = str(package_path / "include")
        env['OPT_PACKAGE_DOC'] = str(package_path / "doc")
        
        return env
    
    def setup_all_packages(self) -> Dict[str, Dict[str, str]]:
        """
        Set up environment for all installed packages.
        
        Returns:
            Dictionary mapping package names to their environment variables
        """
        packages = self._discover_packages()
        environments = {}
        
        for package_path in packages:
            package_name = package_path.name
            environments[package_name] = self.setup_package_environment(package_name)
        
        return environments


class OptPathManager:
    """
    Manages PATH integration for /opt packages.
    
    Creates wrapper scripts and updates system PATH to include /opt packages.
    """
    
    def __init__(
        self,
        opt_root: str = "/opt",
        profile_path: str = None,
        *,
        allow_home_profile: bool = False,
    ):
        """
        Initialize OptPathManager.
        
        Args:
            opt_root: Root directory for opt packages
            profile_path: Path to shell profile (default: ~/.bashrc)
            allow_home_profile: opt-in required before the user's
                default dotfile may be mutated (H188).
        """
        self.opt_root = Path(opt_root)
        self._explicit_profile = profile_path is not None
        self.allow_home_profile = allow_home_profile
        self.profile_path = Path(profile_path) if profile_path else Path.home() / ".bashrc"
        self._bin_paths = []

    def _require_profile_consent(self) -> None:
        """Refuse to touch the user's login file implicitly."""
        if self._explicit_profile or self.allow_home_profile:
            return
        raise PermissionError(
            "OptPathManager would append to "
            + str(self.profile_path)
            + ", the user's login file. Pass profile_path=... explicitly or "
            "set allow_home_profile=True. The supported route is "
            "/etc/profile.d via opt.env.OptEnvManager.write_profile_d(), "
            "which is capability-gated (CAP_FS_ADMIN)."
        )
    
    def _discover_packages(self) -> List[Path]:
        """Discover all installed packages with bin directories."""
        packages = []

        if not self.opt_root.exists():
            return packages

        for item in sorted(self.opt_root.iterdir()):
            if not (item.is_dir() and not item.name.startswith('.')):
                continue
            # the previous `if item.is_dir():` was always true
            # (the enclosing test had already checked it), so the flat
            # /opt/<pkg>/bin layout was never discovered - only the
            # /opt/<prov>/<pkg>/bin one was.
            if (item / "bin").is_dir():
                packages.append(item / "bin")
                continue
            for subitem in sorted(item.iterdir()):
                if not (subitem.is_dir() and not subitem.name.startswith('.')):
                    continue
                bin_path = subitem / "bin"
                if bin_path.is_dir():
                    packages.append(bin_path)

        # drop hostile package names before they can be interpolated
        return _drop_shell_unsafe(packages, self.opt_root)
    
    def generate_profile_script(self) -> str:
        """
        Generate a shell script to add /opt packages to PATH.
        
        Returns:
            Shell script content
        """
        packages = self._discover_packages()
        
        script_lines = [
            "#!/bin/bash",
            "# UmerOS /opt PATH Integration",
            f"# Generated: {datetime.now().isoformat()}",
            f"# Opt root: {_comment_safe(str(self.opt_root))}",
            "",
            "# Add /opt package binaries to PATH",
            "if [ -d \"$OPT_ROOT\" ]; then",
            "    # Discover packages with bin directories",
        ]
        
        for bin_path in packages:
            # shlex.quote every path: this script is sourced
            # by every interactive shell
            script_lines.append(
                "    export PATH="
                + shlex.quote(str(bin_path).replace("\\", "/"))
                + ":$PATH"
            )
        
        script_lines.extend([
            "fi",
            "",
            # the two lines below were missing their `f`
            # prefix, so they emitted the literal text "{self.opt_root}".
            f"export OPT_ROOT={shlex.quote(str(self.opt_root))}",
            f"export OPT_PATH={shlex.quote(str(self.opt_root))}",
            ""
        ])
        
        return '\n'.join(script_lines)
    
    def install_profile_integration(self) -> bool:
        """
        Install PATH integration to shell profile.
        
        Returns:
            True if successful
        """
        self._require_profile_consent()
        script = self.generate_profile_script()
        
        # Check if already installed
        if self._is_installed():
            return True  # Already installed, no need to modify
        
        try:
            with open(self.profile_path, 'a') as f:
                f.write('\n# UmerOS /opt PATH integration\n')
                f.write(script)
                f.write('\n')
            return True
        except OSError as exc:
            log.error("Failed to install profile integration in %s: %s", self.profile_path, exc)
            return False
    
    def _is_installed(self) -> bool:
        """Check if PATH integration is already installed."""
        if not self.profile_path.exists():
            return False
        
        with open(self.profile_path, 'r') as f:
            content = f.read()
            return "UmerOS /opt PATH integration" in content
    
    def uninstall_profile_integration(self) -> bool:
        """
        Remove PATH integration from shell profile.
        
        Returns:
            True if successful
        """
        self._require_profile_consent()
        if not self._is_installed():
            return True  # Not installed, nothing to remove
        
        try:
            with open(self.profile_path, 'r') as f:
                lines = f.readlines()
            
            # Remove the integration section
            new_lines = []
            skip = False
            for line in lines:
                if "UmerOS /opt PATH integration" in line:
                    skip = True
                    continue
                if skip and line.strip() == "":
                    skip = False
                    continue
                if not skip:
                    new_lines.append(line)
            
            with open(self.profile_path, 'w') as f:
                f.writelines(new_lines)
            
            return True
        except OSError as exc:
            log.error(
                "Failed to uninstall profile integration from %s: %s", self.profile_path, exc
            )
            return False
    
    def get_package_paths(self) -> Dict[str, Path]:
        """
        Get all package bin paths.
        
        Returns:
            Dictionary mapping package names to their bin paths
        """
        packages = self._discover_packages()
        result = {}
        
        for bin_path in packages:
            # Get package name from path
            parts = bin_path.parts
            if len(parts) >= 2:
                package_name = parts[-2]
                result[package_name] = bin_path
        
        return result


class OptServiceManager:
    """
    Manages /opt package services.
    
    Provides functionality for starting, stopping, and managing
    services installed in /opt packages.
    """
    
    def __init__(self, opt_root: str = "/opt"):
        """
        Initialize OptServiceManager.
        
        Args:
            opt_root: Root directory for opt packages
        """
        self.opt_root = Path(opt_root)
        self._services = {}
    
    def discover_services(self) -> Dict[str, Path]:
        """
        Discover services in installed packages.
        
        Returns:
            Dictionary mapping service names to their paths
        """
        services = {}
        
        if not self.opt_root.exists():
            return services
        
        for item in self.opt_root.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it's a provider directory or a package
                if item.is_dir():
                    for subitem in item.iterdir():
                        if subitem.is_dir() and not subitem.name.startswith('.'):
                            self._discover_package_services(subitem, services)
                else:
                    self._discover_package_services(item, services)
        
        return services
    
    def _discover_package_services(self, package_path: Path, services: Dict[str, Path]) -> None:
        """Discover services in a package."""
        # Look for service scripts in common locations
        service_locations = [
            package_path / "bin",
            package_path / "sbin",
            package_path / "scripts",
            package_path / "services",
        ]
        
        for location in service_locations:
            if location.exists() and location.is_dir():
                for service_script in location.iterdir():
                    if service_script.is_file() and service_script.suffix in ['.sh', '']:
                        # Check if it's a service script
                        if self._is_service_script(service_script):
                            services[service_script.stem] = service_script
    
    def _is_service_script(self, script_path: Path) -> bool:
        """Check if a script appears to be a service script."""
        try:
            with open(script_path, 'r') as f:
                content = f.read(1024)  # Read first 1KB
                return any(keyword in content for keyword in 
                          ['start', 'stop', 'restart', 'status', 'daemon'])
        except Exception:
            return False
    
    def start_service(self, service_name: str) -> bool:
        """
        Start a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if successful
        """
        services = self.discover_services()
        
        if service_name not in services:
            log.warning("Service not found: %s", service_name)
            return False
        
        service_path = services[service_name]
        
        try:
            # Make executable if needed
            service_path.chmod(0o755)
            
            # Execute the service start command
            import subprocess
            result = subprocess.run([str(service_path), "start"], 
                                   capture_output=True, text=True)
            
            return result.returncode == 0
        except Exception as exc:
            log.error("Failed to start service %s: %s", service_name, exc)
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """
        Stop a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if successful
        """
        services = self.discover_services()
        
        if service_name not in services:
            log.warning("Service not found: %s", service_name)
            return False
        
        service_path = services[service_name]
        
        try:
            import subprocess
            result = subprocess.run([str(service_path), "stop"],
                                   capture_output=True, text=True)
            
            return result.returncode == 0
        except Exception as exc:
            log.error("Failed to stop service %s: %s", service_name, exc)
            return False
    
    def restart_service(self, service_name: str) -> bool:
        """
        Restart a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if successful
        """
        self.stop_service(service_name)
        return self.start_service(service_name)
    
    def get_service_status(self, service_name: str) -> str:
        """
        Get service status.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service status string
        """
        services = self.discover_services()
        
        if service_name not in services:
            return f"Service not found: {service_name}"
        
        service_path = services[service_name]
        
        try:
            import subprocess
            result = subprocess.run([str(service_path), "status"],
                                   capture_output=True, text=True)
            
            return result.stdout.strip()
        except Exception as e:
            return f"Error getting status: {e}"


if __name__ == "__main__":
    # Demo usage
    import tempfile
    
    print("UmerOS /opt Integration Demo")
    print("=" * 50)
    
    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        
        # Create demo packages
        demo_app = opt_root / "demo-app" / "bin"
        demo_app.mkdir(parents=True)
        
        # Create a demo binary
        (demo_app / "demo").write_text('#!/bin/bash\necho "Demo app running"\n')
        demo_app.chmod(0o755)
        
        # Test OptEnvironment
        print("\n1. Testing OptEnvironment...")
        env = OptEnvironment(str(opt_root))
        
        packages = env._discover_packages()
        print(f"   Found {len(packages)} packages")
        
        # Test OptPathManager
        print("\n2. Testing OptPathManager...")
        path_manager = OptPathManager(str(opt_root))
        
        bin_paths = path_manager.get_package_paths()
        print(f"   Found {len(bin_paths)} packages with binaries")
        for name, path in bin_paths.items():
            print(f"   - {name}: {path}")
        
        # Generate profile script
        print("\n3. Generating profile script...")
        script = path_manager.generate_profile_script()
        print("   Generated script (first 500 chars):")
        print("   " + script[:500].replace("\n", "\n   "))
    
    print("\nDemo completed successfully!")
