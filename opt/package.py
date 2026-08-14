"""
UmerOS /opt Package Management

This module implements the core package management functionality for /opt
as per Filesystem Hierarchy standards.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Optional, Any, List
from datetime import datetime


class OptPackage:
    """
    Represents an /opt package and manages its installation.
    
    According to FHS:
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
        if self.provider:
            self.base_path = self.opt_root / self.provider / self.name
        else:
            self.base_path = self.opt_root / self.name
        
        self.bin_path = self.base_path / "bin"
        self.lib_path = self.base_path / "lib"
        self.include_path = self.base_path / "include"
        self.doc_path = self.base_path / "doc"
        self.info_path = self.base_path / "info"
        self.man_path = self.base_path / "man"
        self.src_path = self.base_path / "src"
        self.etc_path = Path("/etc/opt") / (self.provider + "/" + self.name if self.provider else self.name)
        self.var_path = Path("/var/opt") / (self.provider + "/" + self.name if self.provider else self.name)
        
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
    
    def create_launcher_script(self, script_name: str, command: str, 
                                args: List[str] = None) -> Path:
        """
        Create a launcher script in the bin directory.
        
        Args:
            script_name: Name of the launcher script
            command: Command to execute
            args: Optional list of arguments
            
        Returns:
            Path to the created script
        """
        script_path = self.bin_path / script_name
        
        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Launcher script for {self.name}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            f.write(f"exec {command} {' '.join(args) if args else ''} \"$@\"\n")
        
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
        """
        script_path = self.bin_path / script_name
        
        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Wrapper script for {self.name}\n")
            f.write(f"# Wrapper for: {target_binary}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            
            if environment:
                f.write("# Environment setup\n")
                for key, value in environment.items():
                    f.write(f'export {key}="{value}"\n')
                f.write("\n")
            
            f.write(f"exec {target_binary} ")
            if pre_args:
                f.write(' '.join(pre_args) + " ")
            f.write('$@')
            if post_args:
                f.write(" " + ' '.join(post_args))
            f.write("\n")
        
        script_path.chmod(0o755)
        return script_path
    
    def remove(self) -> bool:
        """
        Remove the entire package directory.
        
        Returns:
            True if removal was successful
        """
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
        if provider:
            package_path = self.opt_root / provider / name
        else:
            package_path = self.opt_root / name
        
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
