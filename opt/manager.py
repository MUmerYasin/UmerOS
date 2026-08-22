"""
UmerOS /opt Package Manager - Main Interface

This module provides a high-level interface for managing /opt packages
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Optional, Any, List
from datetime import datetime

from .config import OptConfig, OptIntegration
from .package import OptPackage, OptManager as PackageOptManager

# [FIX H186] Guard against path traversal (CWE-22) in privileged rmtree paths.
try:
    from core.path_guard import safe_child, PathTraversalError
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.path_guard import safe_child, PathTraversalError


class OptManager:
    """
    High-level /opt package manager combining configuration, integration,
    and package management functionality.
    
    This is the main interface for managing /opt packages in UmerOS.
    """
    
    def __init__(self, opt_root: str = "/opt", etc_opt_root: str = "/etc/opt",
                 var_opt_root: str = "/var/opt", database_path: str = ""):
        """
        Initialize the OptManager.
        
        Args:
            opt_root: Root directory for opt packages
            etc_opt_root: Root directory for opt configurations
            var_opt_root: Root directory for opt variable data
            database_path: Path to package database (default: /opt/.packages.json)
        """
        self.opt_root = Path(opt_root)
        self.etc_opt_root = Path(etc_opt_root)
        self.var_opt_root = Path(var_opt_root)
        self.database_path = Path(database_path) if database_path else self.opt_root / ".packages.json"
        
        # Initialize sub-managers
        self.config_manager = OptConfig(str(opt_root), str(etc_opt_root))
        self.integration = OptIntegration(str(opt_root), str(etc_opt_root), str(var_opt_root))
        self.package_manager = PackageOptManager(str(opt_root))
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Initialize package database
        self._init_database()
    
    def _ensure_directories(self) -> None:
        """Create all required directories."""
        for directory in [self.opt_root, self.etc_opt_root, self.var_opt_root]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self) -> None:
        """Initialize the package database."""
        if not self.database_path.exists():
            self._write_database({})
    
    def _read_database(self) -> Dict[str, Any]:
        """Read the package database."""
        if self.database_path.exists():
            with open(self.database_path, 'r') as f:
                return json.load(f)
        return {}
    
    def _write_database(self, data: Dict[str, Any]) -> None:
        """Write to the package database."""
        with open(self.database_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _get_package_db_key(self, name: str, provider: str = "") -> str:
        """Generate database key for a package."""
        if provider:
            return f"{provider}/{name}"
        return name
    
    def install(self, name: str, provider: str = "", version: str = "1.0.0",
                description: str = "", binaries: List[str] = None,
                libraries: List[str] = None, documents: List[str] = None,
                config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Install a package to /opt.
        
        Args:
            name: Package name
            provider: Optional provider name
            version: Package version
            description: Package description
            binaries: List of binary paths to install
            libraries: List of library paths to install
            documents: List of documentation paths to install
            config: Configuration data to store
            
        Returns:
            Dictionary with installation results
        """
        result = {
            "success": False,
            "package": name,
            "provider": provider,
            "installed_at": datetime.now().isoformat(),
            "paths": {},
            "errors": []
        }
        
        try:
            # Create package structure
            package = OptPackage(name, provider, str(self.opt_root))
            result["paths"]["package"] = str(package.base_path)
            
            # Install binaries
            if binaries:
                for binary_path in binaries:
                    try:
                        installed = package.install_binary(binary_path)
                        result["paths"]["binaries"] = result["paths"].get("binaries", [])
                        result["paths"]["binaries"].append(str(installed))
                    except Exception as e:
                        result["errors"].append(f"Failed to install binary {binary_path}: {str(e)}")
            
            # Install libraries
            if libraries:
                for lib_path in libraries:
                    try:
                        installed = package.install_library(lib_path)
                        result["paths"]["libraries"] = result["paths"].get("libraries", [])
                        result["paths"]["libraries"].append(str(installed))
                    except Exception as e:
                        result["errors"].append(f"Failed to install library {lib_path}: {str(e)}")
            
            # Install documents
            if documents:
                for doc_path in documents:
                    try:
                        installed = package.install_documentation(doc_path)
                        result["paths"]["documents"] = result["paths"].get("documents", [])
                        result["paths"]["documents"].append(str(installed))
                    except Exception as e:
                        result["errors"].append(f"Failed to install document {doc_path}: {str(e)}")
            
            # Setup integration
            integration_results = self.integration.setup_integration(name, provider)
            result["paths"]["etc_integration"] = integration_results.get("etc", False)
            result["paths"]["var_integration"] = integration_results.get("var", False)
            
            # Store configuration
            if config:
                config_path = self.config_manager.install_config(name, config)
                result["paths"]["config"] = str(config_path)
            
            # Update database
            db = self._read_database()
            package_key = self._get_package_db_key(name, provider)
            db[package_key] = {
                "name": name,
                "provider": provider,
                "version": version,
                "description": description,
                "installed_at": result["installed_at"],
                "status": "installed",
                "paths": result["paths"]
            }
            self._write_database(db)
            
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(f"Installation failed: {str(e)}")
        
        return result
    
    def _scoped_path(self, root: Path, name: str, provider: str = "") -> Path:
        """[FIX H186] Build a path under ``root`` containing name/provider.

        Replaces the previous ``root / (provider + "/" + name)`` string join,
        which let a traversal name (``"../../etc"``) escape the managed root.
        """
        p = safe_child(root, provider) if provider else Path(root)
        return safe_child(p, name)

    def remove(self, name: str, provider: str = "") -> Dict[str, Any]:
        """
        Remove a package from /opt.
        
        Args:
            name: Package name
            provider: Optional provider name
            
        Returns:
            Dictionary with removal results
        """
        result = {
            "success": False,
            "package": name,
            "provider": provider,
            "removed_at": datetime.now().isoformat(),
            "paths_removed": [],
            "errors": []
        }
        
        try:
            # Remove from /opt
            package_key = self._get_package_db_key(name, provider)

            # [FIX H186] Contain every target inside its managed root. A
            # traversal name ("../../etc") is refused and never rmtree'd.
            try:
                package_path = self._scoped_path(self.opt_root, name, provider)
            except PathTraversalError as exc:
                result["errors"].append(f"Refusing unsafe /opt path: {exc}")
                package_path = None
            try:
                etc_path = self._scoped_path(self.etc_opt_root, name, provider)
            except PathTraversalError as exc:
                result["errors"].append(f"Refusing unsafe /etc/opt path: {exc}")
                etc_path = None
            try:
                var_path = self._scoped_path(self.var_opt_root, name, provider)
            except PathTraversalError as exc:
                result["errors"].append(f"Refusing unsafe /var/opt path: {exc}")
                var_path = None

            for path in (package_path, etc_path, var_path):
                if path is None:
                    continue
                if path.exists():
                    shutil.rmtree(path)
                    result["paths_removed"].append(str(path))
            
            # Remove from database
            db = self._read_database()
            if package_key in db:
                del db[package_key]
                self._write_database(db)
            
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(f"Removal failed: {str(e)}")
        
        return result
    
    def update(self, name: str, provider: str = "", version: str = None,
               config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Update a package.
        
        Args:
            name: Package name
            provider: Optional provider name
            version: New version (optional)
            config: New configuration (optional)
            
        Returns:
            Dictionary with update results
        """
        result = {
            "success": False,
            "package": name,
            "provider": provider,
            "updated_at": datetime.now().isoformat(),
            "errors": []
        }
        
        try:
            db = self._read_database()
            package_key = self._get_package_db_key(name, provider)
            
            if package_key not in db:
                result["errors"].append(f"Package not found: {package_key}")
                return result
            
            # Update version if provided
            if version:
                db[package_key]["version"] = version
            
            # Update configuration if provided
            if config:
                config_path = self.config_manager.install_config(name, config)
                db[package_key]["paths"]["config"] = str(config_path)
            
            db[package_key]["updated_at"] = result["updated_at"]
            self._write_database(db)
            
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(f"Update failed: {str(e)}")
        
        return result
    
    def get(self, name: str, provider: str = "") -> Optional[Dict[str, Any]]:
        """
        Get package information.
        
        Args:
            name: Package name
            provider: Optional provider name
            
        Returns:
            Package information or None
        """
        db = self._read_database()
        package_key = self._get_package_db_key(name, provider)
        return db.get(package_key)
    
    def list(self) -> List[Dict[str, Any]]:
        """
        List all installed packages.
        
        Returns:
            List of package information
        """
        db = self._read_database()
        return list(db.values())
    
    def verify(self, name: str = None, provider: str = None) -> Dict[str, Any]:
        """
        Verify package integrity.
        
        Args:
            name: Package name (optional, verifies all if None)
            provider: Optional provider name
            
        Returns:
            Verification results
        """
        if name:
            package = self.package_manager.get_package(name, provider)
            return {
                "package": f"{provider}/{name}" if provider else name,
                "integrity": package.verify_integrity()
            }
        
        # Verify all packages
        packages = self.list()
        results = {}
        
        for pkg_info in packages:
            pkg_name = pkg_info["name"]
            pkg_provider = pkg_info.get("provider", "")
            package = self.package_manager.get_package(pkg_name, pkg_provider)
            key = f"{pkg_provider}/{pkg_name}" if pkg_provider else pkg_name
            results[key] = package.verify_integrity()
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get /opt statistics.
        
        Returns:
            Dictionary with statistics
        """
        packages = self.list()
        
        stats = {
            "total_packages": len(packages),
            "directories": {
                "opt": str(self.opt_root),
                "etc_opt": str(self.etc_opt_root),
                "var_opt": str(self.var_opt_root)
            },
            "database": str(self.database_path)
        }
        
        # Count packages with providers
        with_provider = sum(1 for p in packages if p.get("provider"))
        stats["packages_with_provider"] = with_provider
        stats["packages_without_provider"] = len(packages) - with_provider
        
        return stats
    
    def create_package_structure(self, name: str, provider: str = "") -> Dict[str, Path]:
        """
        Create package directory structure without installing.
        
        Args:
            name: Package name
            provider: Optional provider name
            
        Returns:
            Dictionary with created paths
        """
        return self.integration.install_package(name, provider)
    
    def install_binary_to_package(self, package_name: str, source_path: str,
                                   provider: str = "", target_name: str = "") -> str:
        """
        Install a binary to an existing package.
        
        Args:
            package_name: Package name
            source_path: Path to binary source
            provider: Optional provider name
            target_name: Optional target name
            
        Returns:
            Path to installed binary or error message
        """
        try:
            package = self.package_manager.get_package(package_name, provider)
            installed = package.install_binary(source_path, target_name)
            return str(installed)
        except Exception as e:
            return f"Error: {str(e)}"


# Convenience functions
def install_package(name: str, provider: str = "", **kwargs) -> Dict[str, Any]:
    """Install a package with default settings."""
    manager = OptManager()
    return manager.install(name, provider, **kwargs)


def remove_package(name: str, provider: str = "") -> Dict[str, Any]:
    """Remove a package."""
    manager = OptManager()
    return manager.remove(name, provider)


def list_packages() -> List[Dict[str, Any]]:
    """List all installed packages."""
    manager = OptManager()
    return manager.list()


def get_package(name: str, provider: str = "") -> Optional[Dict[str, Any]]:
    """Get package information."""
    manager = OptManager()
    return manager.get(name, provider)


if __name__ == "__main__":
    # Demo usage
    import tempfile
    import os
    
    print("UmerOS /opt Manager Demo")
    print("=" * 50)
    
    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as tmpdir:
        opt_root = Path(tmpdir) / "opt"
        etc_opt_root = Path(tmpdir) / "etc_opt"
        var_opt_root = Path(tmpdir) / "var_opt"
        
        # Create manager
        manager = OptManager(
            opt_root=str(opt_root),
            etc_opt_root=str(etc_opt_root),
            var_opt_root=str(var_opt_root)
        )
        print(f"\n1. Created /opt at: {opt_root}")
        
        # Create demo binary file
        demo_binary = Path(tmpdir) / "demo_app.py"
        demo_binary.write_text('#!/usr/bin/env python3\nprint("Hello from demo app")\n')
        
        # Install a package
        print("\n2. Installing 'demo-app' package...")
        result = manager.install(
            "demo-app",
            version="1.0.0",
            description="A demonstration application",
            binaries=[str(demo_binary)],
            config={"settings": {"debug": True, "port": 8080}}
        )
        
        if result["success"]:
            print(f"   ✓ Installation successful!")
            print(f"   Package path: {result['paths']['package']}")
            if result['paths'].get('binaries'):
                print(f"   Binary installed: {result['paths']['binaries'][0]}")
            if result['paths'].get('config'):
                print(f"   Config installed: {result['paths']['config']}")
        else:
            print(f"   ✗ Installation failed: {result['errors']}")
        
        # List packages
        print("\n3. Listing installed packages...")
        packages = manager.list()
        for pkg in packages:
            print(f"   - {pkg['name']} v{pkg['version']}")
        
        # Get package info
        print("\n4. Getting 'demo-app' info...")
        pkg_info = manager.get("demo-app")
        if pkg_info:
            print(f"   Name: {pkg_info['name']}")
            print(f"   Version: {pkg_info['version']}")
            print(f"   Description: {pkg_info['description']}")
        
        # Verify integrity
        print("\n5. Verifying package integrity...")
        verification = manager.verify("demo-app")
        for dir_name, exists in verification['integrity'].items():
            status = "✓" if exists else "✗"
            print(f"   {status} {dir_name}")
        
        # Get statistics
        print("\n6. Getting /opt statistics...")
        stats = manager.get_stats()
        for key, value in stats.items():
            if key != "directories":  # Skip path details for clean output
                print(f"   {key}: {value}")
        
        # Update package
        print("\n7. Updating package version...")
        update_result = manager.update("demo-app", version="1.1.0")
        if update_result["success"]:
            print(f"   ✓ Updated to version 1.1.0")
        
        # Remove package
        print("\n8. Removing package...")
        remove_result = manager.remove("demo-app")
        if remove_result["success"]:
            print(f"   ✓ Package removed successfully")
            for path in remove_result["paths_removed"]:
                print(f"      - Removed: {path}")
    
    print("\nDemo completed successfully!")
