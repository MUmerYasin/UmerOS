"""
Umer OS Boot Manager
====================
Central registry for /boot hierarchy management.

Manages:
- Kernel images (vmlinuz, vmlinux)
- Boot loader configuration (GRUB, systemd-boot)
- initrd/initramfs images
- System.map files
- Boot parameters and configuration

FHS 3.0 compliance:
- /boot contains kernel files and boot loader data
- No subdirectories required (flat structure preferred)
- Kernel images: vmlinuz, vmlinux
- Boot loaders: GRUB, systemd-boot, LILO
- initrd/initramfs for early userspace

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Boot.Manager")


# ── Enums ─────────────────────────────────────────────────────────────────

class BootComponentType(Enum):
    """Types of boot components."""
    KERNEL = "kernel"
    INITRD = "initrd"
    BOOTLOADER = "bootloader"
    SYSTEM_MAP = "system_map"
    CONFIG = "config"
    MICROCODE = "microcode"


class BootLoaderType(Enum):
    """Supported boot loader types."""
    GRUB = "grub"
    SYSTEMD_BOOT = "systemd-boot"
    LILO = "lilo"
    SYSLINUX = "syslinux"
    EFISTUB = "efistub"
    CUSTOM = "custom"


class BootStatus(Enum):
    """Boot component status."""
    PRESENT = "present"
    MISSING = "missing"
    CORRUPTED = "corrupted"
    VERIFIED = "verified"
    STALE = "stale"


class KernelArch(Enum):
    """Supported kernel architectures."""
    X86_64 = "x86_64"
    AMD64 = "amd64"
    AARCH64 = "aarch64"
    ARM64 = "arm64"
    ARMV7 = "armv7l"
    RISCV64 = "riscv64"


# ── Data Classes ──────────────────────────────────────────────────────────

@dataclass
class BootComponent:
    """Represents a boot component (kernel, initrd, etc.)."""
    name: str
    component_type: BootComponentType
    path: str
    status: BootStatus = BootStatus.PRESENT
    size_bytes: int = 0
    hash_sha256: Optional[str] = None
    version: Optional[str] = None
    arch: Optional[KernelArch] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_modified: float = 0.0

    def __post_init__(self):
        """Initialize derived fields."""
        if os.path.isfile(self.path):
            self.size_bytes = os.path.getsize(self.path)
            self.last_modified = os.path.getmtime(self.path)
            if self.status == BootStatus.PRESENT:
                self.status = BootStatus.VERIFIED


@dataclass
class BootEntry:
    """Represents a boot menu entry."""
    title: str
    kernel: str
    initrd: Optional[str] = None
    options: str = ""
    root: Optional[str] = None
    fallback: bool = False
    saved_entry: bool = False


@dataclass
class BootConfig:
    """Boot loader configuration."""
    loader_type: BootLoaderType
    default_entry: str = "0"
    timeout_seconds: int = 5
    entries: List[BootEntry] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


# ── Boot Manager ──────────────────────────────────────────────────────────

class BootManager:
    """
    Central manager for /boot hierarchy.

    Responsibilities:
    - Track kernel images and initrd files
    - Manage boot loader configuration
    - Verify boot component integrity
    - Provide boot entry management
    - FHS compliance checking
    """

    # FHS 3.0 required files in /boot
    FHS_REQUIRED_FILES = [
        "vmlinuz",      # Compressed Linux kernel
        "vmlinux",      # Uncompressed Linux kernel (optional)
        "System.map",   # Kernel symbol table
    ]

    # Common kernel image patterns
    KERNEL_PATTERNS = [
        "vmlinuz-*",
        "vmlinux-*",
        "vmlinux.*",
        "bzImage-*",
        "bzImage",
        "zImage-*",
    ]

    # Common initrd patterns
    INITRD_PATTERNS = [
        "initrd.img-*",
        "initramfs-*",
        "initrd-*",
        "initramfs.img",
        "initrd.img",
        "initrd",
    ]

    # Boot loader config paths
    BOOTLOADER_CONFIGS = {
        BootLoaderType.GRUB: [
            "grub/grub.cfg",
            "grub2/grub.cfg",
            "boot/grub/grub.cfg",
        ],
        BootLoaderType.SYSTEMD_BOOT: [
            "loader/loader.conf",
            "loader/entries/*.conf",
        ],
    }

    def __init__(self, boot_path: str = "/boot"):
        """
        Initialize boot manager.

        Args:
            boot_path: Path to /boot directory
        """
        self.boot_path = Path(boot_path)
        self.components: Dict[str, BootComponent] = {}
        self.config: Optional[BootConfig] = None
        self._boot_entries: List[BootEntry] = []
        self._initialized = False

        log.info("BootManager initialized for path: %s", boot_path)

    def initialize(self) -> bool:
        """
        Initialize the boot manager and scan /boot directory.

        Returns:
            True if initialization successful
        """
        try:
            # Ensure boot directory exists
            self.boot_path.mkdir(parents=True, exist_ok=True)

            # Scan for existing components
            self._scan_kernel_images()
            self._scan_initrd_images()
            self._scan_system_map()
            self._scan_boot_loader_config()

            self._initialized = True
            log.info("BootManager initialization complete. Found %d components.", len(self.components))
            return True

        except Exception as exc:
            log.error("BootManager initialization failed: %s", exc)
            return False

    def _scan_kernel_images(self) -> None:
        """Scan for kernel images in /boot."""
        for pattern in self.KERNEL_PATTERNS:
            for kernel_file in self.boot_path.glob(pattern):
                self._add_component(
                    name=kernel_file.name,
                    component_type=BootComponentType.KERNEL,
                    path=str(kernel_file),
                )

    def _scan_initrd_images(self) -> None:
        """Scan for initrd/initramfs images in /boot."""
        for pattern in self.INITRD_PATTERNS:
            for initrd_file in self.boot_path.glob(pattern):
                self._add_component(
                    name=initrd_file.name,
                    component_type=BootComponentType.INITRD,
                    path=str(initrd_file),
                )

    def _scan_system_map(self) -> None:
        """Scan for System.map files in /boot."""
        for system_map in self.boot_path.glob("System.map*"):
            self._add_component(
                name=system_map.name,
                component_type=BootComponentType.SYSTEM_MAP,
                path=str(system_map),
            )

    def _scan_boot_loader_config(self) -> None:
        """Scan for boot loader configuration files."""
        for loader_type, config_paths in self.BOOTLOADER_CONFIGS.items():
            for config_path in config_paths:
                config_file = self.boot_path / config_path
                if config_file.exists():
                    self._add_component(
                        name=config_file.name,
                        component_type=BootComponentType.CONFIG,
                        path=str(config_file),
                        metadata={"loader_type": loader_type.value},
                    )

    def _add_component(
        self,
        name: str,
        component_type: BootComponentType,
        path: str,
        **kwargs: Any,
    ) -> BootComponent:
        """Add a boot component to the registry."""
        component = BootComponent(
            name=name,
            component_type=component_type,
            path=path,
            **kwargs,
        )
        self.components[name] = component
        log.debug("Added component: %s (%s)", name, component_type.value)
        return component

    # ── Kernel Management ─────────────────────────────────────────────────

    def register_kernel(
        self,
        name: str,
        path: str,
        version: Optional[str] = None,
        arch: Optional[KernelArch] = None,
        description: str = "",
    ) -> BootComponent:
        """
        Register a kernel image.

        Args:
            name: Kernel name (e.g., "vmlinuz-5.15.0-generic")
            path: Path to kernel image
            version: Kernel version string
            arch: Kernel architecture
            description: Human-readable description

        Returns:
            Registered BootComponent
        """
        component = self._add_component(
            name=name,
            component_type=BootComponentType.KERNEL,
            path=path,
            version=version,
            arch=arch,
            description=description,
        )
        log.info("Registered kernel: %s", name)
        return component

    def get_kernel(self, name: str) -> Optional[BootComponent]:
        """Get a kernel component by name."""
        component = self.components.get(name)
        if component and component.component_type == BootComponentType.KERNEL:
            return component
        return None

    def list_kernels(self) -> List[BootComponent]:
        """List all registered kernel images."""
        return [
            c for c in self.components.values()
            if c.component_type == BootComponentType.KERNEL
        ]

    # ── Initrd Management ─────────────────────────────────────────────────

    def register_initrd(
        self,
        name: str,
        path: str,
        version: Optional[str] = None,
        description: str = "",
    ) -> BootComponent:
        """
        Register an initrd/initramfs image.

        Args:
            name: Initrd name (e.g., "initrd.img-5.15.0-generic")
            path: Path to initrd image
            version: Kernel version this initrd is for
            description: Human-readable description

        Returns:
            Registered BootComponent
        """
        component = self._add_component(
            name=name,
            component_type=BootComponentType.INITRD,
            path=path,
            version=version,
            description=description,
        )
        log.info("Registered initrd: %s", name)
        return component

    def list_initrds(self) -> List[BootComponent]:
        """List all registered initrd images."""
        return [
            c for c in self.components.values()
            if c.component_type == BootComponentType.INITRD
        ]

    # ── Boot Entry Management ─────────────────────────────────────────────

    def add_boot_entry(
        self,
        title: str,
        kernel: str,
        initrd: Optional[str] = None,
        options: str = "",
        root: Optional[str] = None,
        fallback: bool = False,
    ) -> BootEntry:
        """
        Add a boot menu entry.

        Args:
            title: Display title for boot entry
            kernel: Kernel image path/name
            initrd: Initrd image path/name (optional)
            options: Kernel command line options
            root: Root filesystem device/path
            fallback: Whether this is a fallback entry

        Returns:
            Created BootEntry
        """
        entry = BootEntry(
            title=title,
            kernel=kernel,
            initrd=initrd,
            options=options,
            root=root,
            fallback=fallback,
        )
        self._boot_entries.append(entry)
        log.info("Added boot entry: %s", title)
        return entry

    def get_boot_entries(self) -> List[BootEntry]:
        """Get all boot entries."""
        return self._boot_entries.copy()

    def set_default_entry(self, entry_index: int) -> bool:
        """Set the default boot entry."""
        if 0 <= entry_index < len(self._boot_entries):
            if self.config:
                self.config.default_entry = str(entry_index)
            log.info("Set default boot entry to index %d", entry_index)
            return True
        return False

    # ── Integrity Verification ────────────────────────────────────────────

    def verify_component(
        self,
        name: str,
        expected_hash: Optional[str] = None,
    ) -> bool:
        """
        Verify integrity of a boot component.

        Args:
            name: Component name
            expected_hash: Expected SHA-256 hash (None to skip verification)

        Returns:
            True if verification passes
        """
        component = self.components.get(name)
        if not component:
            log.error("Component not found: %s", name)
            return False

        if not os.path.isfile(component.path):
            component.status = BootStatus.MISSING
            log.error("Component file missing: %s", component.path)
            return False

        # Compute hash if expected
        if expected_hash:
            try:
                computed_hash = self._compute_sha256(component.path)
                if computed_hash.lower() != expected_hash.lower():
                    component.status = BootStatus.CORRUPTED
                    log.error(
                        "Component hash mismatch: %s (expected: %s, got: %s)",
                        name, expected_hash[:16], computed_hash[:16],
                    )
                    return False
            except Exception as exc:
                log.error("Hash computation failed for %s: %s", name, exc)
                return False

        component.status = BootStatus.VERIFIED
        log.info("Component verified: %s", name)
        return True

    def _compute_sha256(self, file_path: str) -> str:
        """Compute SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def compute_component_hash(self, name: str) -> Optional[str]:
        """
        Compute SHA-256 hash of a component.

        Args:
            name: Component name

        Returns:
            Hex digest string or None if component not found
        """
        component = self.components.get(name)
        if not component or not os.path.isfile(component.path):
            return None
        return self._compute_sha256(component.path)

    # ── Boot Configuration ────────────────────────────────────────────────

    def load_grub_config(self, config_path: Optional[str] = None) -> bool:
        """
        Load GRUB configuration.

        Args:
            config_path: Path to grub.cfg (None for default)

        Returns:
            True if configuration loaded successfully
        """
        if config_path is None:
            # Try common GRUB config paths
            possible_paths = [
                self.boot_path / "grub" / "grub.cfg",
                self.boot_path / "grub2" / "grub.cfg",
            ]
            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break

        if not config_path or not os.path.isfile(config_path):
            log.warning("GRUB configuration not found at: %s", config_path)
            return False

        try:
            # Parse GRUB configuration (simplified)
            entries = self._parse_grub_config(config_path)
            self.config = BootConfig(
                loader_type=BootLoaderType.GRUB,
                entries=entries,
            )
            log.info("Loaded GRUB configuration with %d entries", len(entries))
            return True
        except Exception as exc:
            log.error("Failed to load GRUB configuration: %s", exc)
            return False

    def _parse_grub_config(self, config_path: str) -> List[BootEntry]:
        """Parse GRUB configuration file (simplified parser)."""
        entries = []
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Simple parsing for menuentry blocks
            import re
            menu_entries = re.findall(
                r"menuentry\s+['\"](.+?)['\"].*?\{(.*?)\}",
                content,
                re.DOTALL,
            )

            for title, block in menu_entries:
                kernel_match = re.search(r"linux\s+(\S+)", block)
                initrd_match = re.search(r"initrd\s+(\S+)", block)

                kernel = kernel_match.group(1) if kernel_match else ""
                initrd = initrd_match.group(1) if initrd_match else None

                entries.append(BootEntry(
                    title=title,
                    kernel=kernel,
                    initrd=initrd,
                ))

        except Exception as exc:
            log.error("Failed to parse GRUB config: %s", exc)

        return entries

    def generate_grub_config(self, output_path: Optional[str] = None) -> str:
        """
        Generate GRUB configuration.

        Args:
            output_path: Path to write grub.cfg (None for stdout)

        Returns:
            Generated GRUB configuration content
        """
        lines = [
            "# Umer OS GRUB Configuration",
            "# Auto-generated by BootManager",
            "",
            "set default=0",
            f"set timeout={self.config.timeout_seconds if self.config else 5}",
            "",
            "menuentry 'Umer OS' {",
            "    linux /boot/vmlinuz root=/dev/sda1 ro quiet splash",
            "    initrd /boot/initrd.img",
            "}",
            "",
            "menuentry 'Umer OS (Recovery Mode)' {",
            "    linux /boot/vmlinuz root=/dev/sda1 ro single",
            "    initrd /boot/initrd.img",
            "}",
        ]

        config_content = "\n".join(lines)

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(config_content)
            log.info("Generated GRUB configuration: %s", output_path)

        return config_content

    # ── Boot Sequence ─────────────────────────────────────────────────────

    def execute_boot_sequence(
        self,
        entry_index: int = 0,
        timeout: float = 10.0,
    ) -> bool:
        """
        Execute the boot sequence for a given entry.

        Args:
            entry_index: Boot entry index to use
            timeout: Timeout for boot sequence in seconds

        Returns:
            True if boot sequence completed successfully
        """
        if entry_index >= len(self._boot_entries):
            log.error("Invalid boot entry index: %d", entry_index)
            return False

        entry = self._boot_entries[entry_index]
        log.info("Starting boot sequence for: %s", entry.title)

        # Phase 1: Verify components
        log.info("Phase 1: Component verification")
        if not self._verify_boot_components(entry):
            log.error("Boot component verification failed")
            return False

        # Phase 2: Load kernel
        log.info("Phase 2: Kernel loading")
        if not self._load_kernel(entry):
            log.error("Kernel loading failed")
            return False

        # Phase 3: Load initrd
        if entry.initrd:
            log.info("Phase 3: Initrd loading")
            if not self._load_initrd(entry):
                log.error("Initrd loading failed")
                return False

        # Phase 4: Boot completion
        log.info("Phase 4: Boot completion")
        log.info("Boot sequence completed successfully for: %s", entry.title)
        return True

    def _verify_boot_components(self, entry: BootEntry) -> bool:
        """Verify all components needed for boot entry."""
        # Check kernel exists
        kernel_component = self.components.get(entry.kernel)
        if kernel_component and kernel_component.status == BootStatus.MISSING:
            log.error("Kernel missing: %s", entry.kernel)
            return False

        # Check initrd exists if specified
        if entry.initrd:
            initrd_component = self.components.get(entry.initrd)
            if initrd_component and initrd_component.status == BootStatus.MISSING:
                log.error("Initrd missing: %s", entry.initrd)
                return False

        return True

    def _load_kernel(self, entry: BootEntry) -> bool:
        """Load kernel for boot entry."""
        # In simulation, just verify kernel is accessible
        kernel_component = self.components.get(entry.kernel)
        if kernel_component and os.path.isfile(kernel_component.path):
            log.info("Kernel loaded: %s", entry.kernel)
            return True
        return False

    def _load_initrd(self, entry: BootEntry) -> bool:
        """Load initrd for boot entry."""
        if not entry.initrd:
            return True

        initrd_component = self.components.get(entry.initrd)
        if initrd_component and os.path.isfile(initrd_component.path):
            log.info("Initrd loaded: %s", entry.initrd)
            return True
        return False

    # ── FHS Compliance ────────────────────────────────────────────────────

    def check_fhs_compliance(self) -> Dict[str, Any]:
        """
        Check FHS 3.0 compliance for /boot directory.

        Returns:
            Dictionary with compliance results
        """
        results = {
            "compliant": True,
            "required_files": {},
            "optional_files": {},
            "issues": [],
        }

        # Check required files
        for required_file in self.FHS_REQUIRED_FILES:
            file_path = self.boot_path / required_file
            exists = file_path.exists()
            results["required_files"][required_file] = exists
            if not exists:
                results["compliant"] = False
                results["issues"].append(f"Missing required file: {required_file}")

        # Check for common kernel images
        kernel_patterns = ["vmlinuz*", "vmlinux*"]
        for pattern in kernel_patterns:
            matches = list(self.boot_path.glob(pattern))
            if matches:
                results["optional_files"][pattern] = [m.name for m in matches]

        return results

    # ── Utilities ─────────────────────────────────────────────────────────

    def get_component_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get status of a boot component."""
        component = self.components.get(name)
        if not component:
            return None

        return {
            "name": component.name,
            "type": component.component_type.value,
            "path": component.path,
            "status": component.status.value,
            "size_bytes": component.size_bytes,
            "version": component.version,
            "arch": component.arch.value if component.arch else None,
            "description": component.description,
        }

    def list_components(
        self,
        component_type: Optional[BootComponentType] = None,
    ) -> List[Dict[str, Any]]:
        """List all boot components, optionally filtered by type."""
        components = []
        for component in self.components.values():
            if component_type and component.component_type != component_type:
                continue
            components.append(self.get_component_status(component.name))
        return components

    def get_boot_summary(self) -> Dict[str, Any]:
        """Get a summary of the boot configuration."""
        return {
            "boot_path": str(self.boot_path),
            "total_components": len(self.components),
            "kernels": len(self.list_kernels()),
            "initrds": len(self.list_initrds()),
            "boot_entries": len(self._boot_entries),
            "fhs_compliant": self.check_fhs_compliance()["compliant"],
        }


# ── Singleton ─────────────────────────────────────────────────────────────

_boot_manager_instance: Optional[BootManager] = None


def get_boot_manager(boot_path: str = "/boot") -> BootManager:
    """
    Get or create the singleton BootManager instance.

    Args:
        boot_path: Path to /boot directory

    Returns:
        BootManager instance
    """
    global _boot_manager_instance
    if _boot_manager_instance is None:
        _boot_manager_instance = BootManager(boot_path)
        _boot_manager_instance.initialize()
    return _boot_manager_instance


def reset_boot_manager() -> None:
    """Reset the singleton BootManager instance."""
    global _boot_manager_instance
    _boot_manager_instance = None
