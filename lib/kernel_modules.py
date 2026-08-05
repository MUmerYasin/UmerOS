"""
UmerOS Kernel Module Management
=================================
Manages loadable kernel modules in /lib/modules.

FHS 3.0:
  /lib/modules/<kernel-version>/ — Kernel modules
  /lib/modules/<kernel-version>/kernel/ — Core kernel modules
  /lib/modules/<kernel-version>/extra/ — Extra modules

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Lib.KernelModules")


@dataclass
class KernelModule:
    """Represents a kernel module."""
    name: str
    path: str
    size: int = 0
    version: str = ""
    description: str = ""
    author: str = ""
    license: str = ""
    dependencies: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class KernelModuleManager:
    """
    Manages kernel modules in /lib/modules.

    Handles module listing, loading/unloading, dependency tracking.
    """

    def __init__(self, lib_path: str = "/lib"):
        self.lib_path = Path(lib_path)
        self.modules_path = self.lib_path / "modules"

    def get_kernel_versions(self) -> List[str]:
        """List available kernel versions."""
        if not self.modules_path.exists():
            return []
        versions = []
        for item in self.modules_path.iterdir():
            if item.is_dir():
                versions.append(item.name)
        return sorted(versions)

    def get_modules_for_version(self, kernel_version: str) -> List[KernelModule]:
        """List all modules for a specific kernel version."""
        version_dir = self.modules_path / kernel_version
        if not version_dir.exists():
            return []
        modules = []
        for item in version_dir.rglob("*.ko"):
            mod = KernelModule(
                name=item.stem,
                path=str(item),
                size=item.stat().st_size,
            )
            modules.append(mod)
        return modules

    def find_module(self, name: str, kernel_version: Optional[str] = None) -> Optional[KernelModule]:
        """Find a module by name."""
        versions = [kernel_version] if kernel_version else self.get_kernel_versions()
        for ver in versions:
            for mod in self.get_modules_for_version(ver):
                if mod.name == name or mod.name.endswith(name):
                    return mod
        return None

    def get_module_dependencies(self, name: str) -> List[str]:
        """Get dependencies for a module (from modules.dep)."""
        # Check all kernel versions
        for ver in self.get_kernel_versions():
            dep_file = self.modules_path / ver / "modules.dep"
            if dep_file.exists():
                for line in dep_file.read_text(encoding="utf-8").splitlines():
                    if ":" in line:
                        mod, deps = line.split(":", 1)
                        if Path(mod).stem == name:
                            return [Path(d).stem for d in deps.split() if d]
        return []

    def list_loaded_modules(self) -> List[str]:
        """List currently loaded modules from /proc/modules."""
        proc_modules = Path("/proc/modules")
        if not proc_modules.exists():
            return []
        loaded = []
        for line in proc_modules.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if parts:
                loaded.append(parts[0])
        return loaded

    def is_module_loaded(self, name: str) -> bool:
        """Check if a module is currently loaded."""
        return name in self.list_loaded_modules()

    def get_module_info(self, name: str) -> Dict:
        """Get detailed information about a module."""
        mod = self.find_module(name)
        if mod is None:
            return {"error": f"Module not found: {name}"}
        return {
            "name": mod.name,
            "path": mod.path,
            "size": mod.size,
            "version": mod.version,
            "dependencies": self.get_module_dependencies(name),
        }

    def get_summary(self, kernel_version: Optional[str] = None) -> Dict:
        """Get summary of kernel modules."""
        versions = [kernel_version] if kernel_version else self.get_kernel_versions()
        total_modules = 0
        total_size = 0
        for ver in versions:
            mods = self.get_modules_for_version(ver)
            total_modules += len(mods)
            total_size += sum(m.size for m in mods)
        return {
            "kernel_versions": self.get_kernel_versions(),
            "total_modules": total_modules,
            "total_size_bytes": total_size,
            "loaded_modules": self.list_loaded_modules(),
        }
