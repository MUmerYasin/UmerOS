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
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


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
    
    def __init__(self, opt_root: str = "/opt", profile_path: str = None):
        """
        Initialize OptPathManager.
        
        Args:
            opt_root: Root directory for opt packages
            profile_path: Path to shell profile (default: ~/.bashrc)
        """
        self.opt_root = Path(opt_root)
        self.profile_path = Path(profile_path) if profile_path else Path.home() / ".bashrc"
        self._bin_paths = []
    
    def _discover_packages(self) -> List[Path]:
        """Discover all installed packages with bin directories."""
        packages = []
        
        if not self.opt_root.exists():
            return packages
        
        for item in self.opt_root.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it's a provider directory or a package
                if item.is_dir():
                    for subitem in item.iterdir():
                        if subitem.is_dir() and not subitem.name.startswith('.'):
                            bin_path = subitem / "bin"
                            if bin_path.exists():
                                packages.append(bin_path)
                else:
                    bin_path = item / "bin"
                    if bin_path.exists():
                        packages.append(bin_path)
        
        return packages
    
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
            f"# Opt root: {self.opt_root}",
            "",
            "# Add /opt package binaries to PATH",
            "if [ -d \"$OPT_ROOT\" ]; then",
            "    # Discover packages with bin directories",
        ]
        
        for bin_path in packages:
            script_lines.append(f'    export PATH="{bin_path}:$PATH"')
        
        script_lines.extend([
            "fi",
            "",
            "export OPT_ROOT=\"{self.opt_root}\"",
            "export OPT_PATH=\"{self.opt_root}\"",
            ""
        ])
        
        return '\n'.join(script_lines)
    
    def install_profile_integration(self) -> bool:
        """
        Install PATH integration to shell profile.
        
        Returns:
            True if successful
        """
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
        except Exception as e:
            print(f"Failed to install profile integration: {e}")
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
        except Exception as e:
            print(f"Failed to uninstall profile integration: {e}")
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
            print(f"Service not found: {service_name}")
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
        except Exception as e:
            print(f"Failed to start service: {e}")
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
            print(f"Service not found: {service_name}")
            return False
        
        service_path = services[service_name]
        
        try:
            import subprocess
            result = subprocess.run([str(service_path), "stop"],
                                   capture_output=True, text=True)
            
            return result.returncode == 0
        except Exception as e:
            print(f"Failed to stop service: {e}")
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
