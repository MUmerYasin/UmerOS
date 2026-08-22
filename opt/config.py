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
UmerOS /opt Configuration Management

This module handles configuration files for /opt packages in /etc/opt
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

# [FIX H185] Guard against path traversal (CWE-22) in config file paths.
try:
    from core.path_guard import safe_child, safe_join, PathTraversalError
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.path_guard import safe_child, safe_join, PathTraversalError


class OptConfig:
    """
    Manages configuration files for /opt packages in /etc/opt.
    
    - Host-specific configuration files for add-on packages must be in /etc/opt/<subdir>
    - No structure is imposed on internal arrangement
    - Configuration files must be static and cannot be executable binaries
    """
    
    def __init__(self, opt_root: str = "/opt", etc_opt_root: str = "/etc/opt"):
        """
        Initialize OptConfig manager.
        
        Args:
            opt_root: Root directory for opt packages (default: /opt)
            etc_opt_root: Root directory for opt configurations (default: /etc/opt)
        """
        self.opt_root = Path(opt_root)
        self.etc_opt_root = Path(etc_opt_root)
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Create /etc/opt and /opt directories if they don't exist."""
        for directory in [self.etc_opt_root, self.opt_root]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_config_path(self, package_name: str, config_file: str = "") -> Path:
        """
        Get the path for a package's configuration file.
        
        Args:
            package_name: Name of the package
            config_file: Optional configuration file name
            
        Returns:
            Path to the configuration file
            
        Raises:
            PathTraversalError: if package_name/config_file would escape the
                /etc/opt root (fail-closed; callers catch and refuse).
        """
        # [FIX H185] Contain the package dir and (optional) nested config file
        # inside /etc/opt. A name like "../../etc/passwd" is refused.
        base = safe_child(self.etc_opt_root, package_name)
        if config_file:
            return safe_join(base, config_file)
        return base
    
    def install_config(self, package_name: str, config_data: Dict[str, Any], 
                       config_file: str = "config.json") -> Path:
        """
        Install configuration for a package.
        
        Args:
            package_name: Name of the package
            config_data: Dictionary containing configuration data
            config_file: Name of the configuration file
            
        Returns:
            Path to the installed configuration file
            
        Raises:
            ValueError: if the resolved config path would escape /etc/opt
                (path-traversal refusal).
        """
        try:
            config_path = self.get_config_path(package_name, config_file)
        except PathTraversalError as exc:
            # [FIX H185] Fail closed: never write outside /etc/opt.
            raise ValueError(f"Refusing unsafe /etc/opt config path: {exc}")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump({
                "package": package_name,
                "installed_at": datetime.now().isoformat(),
                "config": config_data
            }, f, indent=2)
        
        return config_path
    
    def get_config(self, package_name: str, config_file: str = "config.json") -> Optional[Dict[str, Any]]:
        """
        Get configuration for a package.
        
        Args:
            package_name: Name of the package
            config_file: Name of the configuration file
            
        Returns:
            Configuration dictionary or None if not found
        """
        try:
            config_path = self.get_config_path(package_name, config_file)
        except PathTraversalError:
            return None
        if config_path.exists():
            with open(config_path, 'r') as f:
                data = json.load(f)
                return data.get("config", {})
        return None
    
    def remove_config(self, package_name: str) -> bool:
        """
        Remove all configuration for a package.
        
        Args:
            package_name: Name of the package
            
        Returns:
            True if removal was successful
        """
        try:
            config_path = safe_child(self.etc_opt_root, package_name)
        except PathTraversalError:
            # [FIX H185] Refuse to delete anything outside /etc/opt.
            return False
        if config_path.exists():
            if config_path.is_dir():
                import shutil
                shutil.rmtree(config_path)
            else:
                config_path.unlink()
            return True
        return False
    
    def list_configs(self) -> list:
        """
        List all configured packages.
        
        Returns:
            List of package names with configurations
        """
        if not self.etc_opt_root.exists():
            return []
        
        return [d.name for d in self.etc_opt_root.iterdir() if d.is_dir()]
    
    def validate_config(self, package_name: str, schema: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate package configuration.
        
        Args:
            package_name: Name of the package
            schema: Optional JSON schema for validation
            
        Returns:
            True if configuration is valid
        """
        config = self.get_config(package_name)
        if config is None:
            return False
        
        if schema is None:
            return True
        
        # Basic validation - in production, use a proper JSON schema validator
        required = schema.get("required", [])
        for field in required:
            if field not in config:
                return False
        
        return True


class OptIntegration:
    """
    Manages integration between /opt, /etc/opt, and /var/opt.
    
    According to FHS:
    - Package files that are variable must be installed in /var/opt
    - Host-specific configuration files are installed in /etc/opt
    - All data required to support a package must be present within /opt, /var/opt, and /etc/opt
    """
    
    def __init__(self, opt_root: str = "/opt", etc_opt_root: str = "/etc/opt", 
                 var_opt_root: str = "/var/opt"):
        """
        Initialize OptIntegration manager.
        
        Args:
            opt_root: Root directory for opt packages (default: /opt)
            etc_opt_root: Root directory for opt configurations (default: /etc/opt)
            var_opt_root: Root directory for opt variable data (default: /var/opt)
        """
        self.opt_root = Path(opt_root)
        self.etc_opt_root = Path(etc_opt_root)
        self.var_opt_root = Path(var_opt_root)
        self._ensure_directories()
        self.config_manager = OptConfig(opt_root, etc_opt_root)
    
    def _ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        for directory in [self.opt_root, self.etc_opt_root, self.var_opt_root]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def install_package(self, package_name: str, provider: str = "") -> Dict[str, Path]:
        """
        Create standard directory structure for a package.
        
        Args:
            package_name: Name of the package
            provider: Optional provider name for /opt/provider/package structure
            
        Returns:
            Dictionary with paths for each directory
        """
        self._ensure_directories()
        
        if provider:
            package_path = self.opt_root / provider / package_name
            etc_path = self.etc_opt_root / provider / package_name
            var_path = self.var_opt_root / provider / package_name
        else:
            package_path = self.opt_root / package_name
            etc_path = self.etc_opt_root / package_name
            var_path = self.var_opt_root / package_name
        
        # Create standard subdirectories
        paths = {
            "package": package_path,
            "etc": etc_path,
            "var": var_path,
            "bin": package_path / "bin",
            "lib": package_path / "lib",
            "include": package_path / "include",
            "doc": package_path / "doc",
            "info": package_path / "info",
            "man": package_path / "man",
            "src": package_path / "src",
        }
        
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        
        return paths
    
    def setup_integration(self, package_name: str, provider: str = "") -> Dict[str, bool]:
        """
        Set up integration between /opt, /etc/opt, and /var/opt for a package.
        
        Args:
            package_name: Name of the package
            provider: Optional provider name
            
        Returns:
            Dictionary indicating success status for each integration point
        """
        paths = self.install_package(package_name, provider)
        
        # Create integration markers
        integration_markers = {
            "etc": paths["etc"] / ".opt-integration",
            "var": paths["var"] / ".opt-integration",
        }
        
        results = {}
        for name, marker_path in integration_markers.items():
            try:
                with open(marker_path, 'w') as f:
                    f.write(f"Package: {package_name}\n")
                    f.write(f"Provider: {provider}\n")
                    f.write(f"Installed: {datetime.now().isoformat()}\n")
                results[name] = True
            except Exception:
                results[name] = False
        
        return results
    
    def get_package_paths(self, package_name: str, provider: str = "") -> Dict[str, Path]:
        """
        Get all paths for a package.
        
        Args:
            package_name: Name of the package
            provider: Optional provider name
            
        Returns:
            Dictionary with all package paths
        """
        if provider:
            package_path = self.opt_root / provider / package_name
            etc_path = self.etc_opt_root / provider / package_name
            var_path = self.var_opt_root / provider / package_name
        else:
            package_path = self.opt_root / package_name
            etc_path = self.etc_opt_root / package_name
            var_path = self.var_opt_root / package_name
        
        return {
            "opt": package_path,
            "etc": etc_path,
            "var": var_path,
            "bin": package_path / "bin",
            "lib": package_path / "lib",
            "include": package_path / "include",
            "doc": package_path / "doc",
            "info": package_path / "info",
            "man": package_path / "man",
        }
    
    def remove_package(self, package_name: str, provider: str = "") -> bool:
        """
        Remove all traces of a package from /opt, /etc/opt, and /var/opt.
        
        Args:
            package_name: Name of the package
            provider: Optional provider name
            
        Returns:
            True if removal was successful
        """
        import shutil
        
        if provider:
            opt_path = self.opt_root / provider / package_name
            etc_path = self.etc_opt_root / provider / package_name
            var_path = self.var_opt_root / provider / package_name
        else:
            opt_path = self.opt_root / package_name
            etc_path = self.etc_opt_root / package_name
            var_path = self.var_opt_root / package_name
        
        removed = True
        
        for path in [opt_path, etc_path, var_path]:
            if path.exists():
                try:
                    shutil.rmtree(path)
                except Exception:
                    removed = False
        
        return removed
    
    def list_packages(self) -> list:
        """
        List all installed packages.
        
        Returns:
            List of package names
        """
        packages = []
        
        if self.opt_root.exists():
            for item in self.opt_root.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    packages.append(item.name)
        
        return sorted(packages)


if __name__ == "__main__":
    # Demo usage
    import sys
    
    # Set up paths for demo
    opt_root = Path(__file__).parent
    etc_opt_root = Path(__file__).parent / "demo_etc_opt"
    var_opt_root = Path(__file__).parent / "demo_var_opt"
    
    print("UmerOS /opt Integration Demo")
    print("=" * 50)
    
    # Create integration manager
    integration = OptIntegration(
        opt_root=str(opt_root),
        etc_opt_root=str(etc_opt_root),
        var_opt_root=str(var_opt_root)
    )
    
    # Install a sample package
    print("\n1. Installing 'sample-app' package...")
    paths = integration.install_package("sample-app")
    print(f"   Created directories:")
    for name, path in paths.items():
        print(f"   - {name}: {path}")
    
    # Setup integration
    print("\n2. Setting up integration...")
    results = integration.setup_integration("sample-app")
    print(f"   Integration results: {results}")
    
    # Install configuration
    print("\n3. Installing configuration...")
    config_manager = OptConfig(str(opt_root), str(etc_opt_root))
    config_path = config_manager.install_config(
        "sample-app",
        {"version": "1.0.0", "settings": {"debug": False, "port": 8080}}
    )
    print(f"   Configuration installed at: {config_path}")
    
    # Get configuration
    print("\n4. Reading configuration...")
    config = config_manager.get_config("sample-app")
    print(f"   Configuration: {config}")
    
    # List packages
    print("\n5. Listing packages...")
    packages = integration.list_packages()
    print(f"   Installed packages: {packages}")
    
    # Show package paths
    print("\n6. Getting package paths...")
    package_paths = integration.get_package_paths("sample-app")
    print(f"   Package paths:")
    for name, path in package_paths.items():
        print(f"   - {name}: {path}")
    
    # Cleanup demo directories
    import shutil
    if etc_opt_root.exists():
        shutil.rmtree(etc_opt_root)
    if var_opt_root.exists():
        shutil.rmtree(var_opt_root)
    
    print("\nDemo completed successfully!")
