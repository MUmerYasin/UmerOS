"""
Umer OS Initrd Manager
======================
Manages initrd/initramfs images for early userspace boot.

FHS 3.0 /boot requirements for initrd:
- initrd.img-* : Initial ramdisk images
- initramfs-* : Initial ram filesystem images
- Used for mounting root filesystem before kernel can access it directly

The initrd provides:
- Device drivers needed to access root filesystem
- LVM, RAID, or encrypted filesystem support
- Early userspace utilities

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import gzip
import hashlib
import logging
import os
import shutil
import tarfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Boot.Initrd")


# ── Enums ─────────────────────────────────────────────────────────────────

class InitrdFormat(Enum):
    """Initrd image formats."""
    CPIO_GZ = "cpio.gz"          # Compressed cpio archive
    CPIO_XZ = "cpio.xz"          # XZ compressed cpio
    CPIO_LZ4 = "cpio.lz4"        # LZ4 compressed cpio
    TAR_GZ = "tar.gz"            # Compressed tar archive
    TAR_XZ = "tar.xz"            # XZ compressed tar
    SQUASHFS = "squashfs"        # Squashfs filesystem
    ERofs = "erofs"              # Enhanced Read-Only File System


class InitrdStatus(Enum):
    """Initrd image status."""
    VALID = "valid"
    CORRUPTED = "corrupted"
    MISSING = "missing"
    STALE = "stale"
    UNVERIFIED = "unverified"


class InitrdPurpose(Enum):
    """Purpose of the initrd."""
    BOOT = "boot"                # Normal boot
    RECOVERY = "recovery"        # Recovery mode
    LIVE = "live"                # Live system
    RESCUE = "rescue"            # Rescue mode
    TEST = "test"                # Testing/debugging


# ── Data Classes ──────────────────────────────────────────────────────────

@dataclass
class InitrdImage:
    """Represents an initrd/initramfs image."""
    name: str
    path: str
    format: InitrdFormat
    purpose: InitrdPurpose = InitrdPurpose.BOOT
    status: InitrdStatus = InitrdStatus.UNVERIFIED
    kernel_version: Optional[str] = None
    size_bytes: int = 0
    hash_sha256: Optional[str] = None
    timestamp: float = 0.0
    modules: List[str] = field(default_factory=list)
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize derived fields."""
        if os.path.isfile(self.path):
            self.size_bytes = os.path.getsize(self.path)
            self.timestamp = os.path.getmtime(self.path)


@dataclass
class InitrdModule:
    """Represents a kernel module in the initrd."""
    name: str
    path: str
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    size_bytes: int = 0

    def __post_init__(self):
        """Initialize size if file exists."""
        if os.path.isfile(self.path):
            self.size_bytes = os.path.getsize(self.path)


@dataclass
class InitrdConfig:
    """Configuration for initrd generation."""
    kernel_version: str
    format: InitrdFormat = InitrdFormat.CPIO_GZ
    compression: str = "gzip"
    modules: List[str] = field(default_factory=list)
    include_files: List[str] = field(default_factory=list)
    exclude_files: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    busybox: bool = True
    udev: bool = True
    lvm: bool = False
    raid: bool = False
    cryptsetup: bool = False


# ── Initrd Manager ────────────────────────────────────────────────────────

class InitrdManager:
    """
    Manager for initrd/initramfs images.

    Responsibilities:
    - Track initrd images in /boot
    - Verify initrd integrity
    - Generate initrd images (simplified)
    - Manage initrd modules
    - FHS compliance checking
    """

    # Common initrd patterns
    INITRD_PATTERNS = [
        "initrd.img-*",
        "initramfs-*",
        "initrd-*",
        "initrd.img",
        "initramfs.img",
        "initrd",
    ]

    def __init__(self, boot_path: str = "/boot"):
        """
        Initialize initrd manager.

        Args:
            boot_path: Path to /boot directory
        """
        self.boot_path = Path(boot_path)
        self.images: Dict[str, InitrdImage] = {}
        self.modules: Dict[str, InitrdModule] = {}
        self._initialized = False

        log.info("InitrdManager initialized for path: %s", boot_path)

    def initialize(self) -> bool:
        """
        Initialize the manager and scan for existing initrd images.

        Returns:
            True if initialization successful
        """
        try:
            # Ensure boot directory exists
            self.boot_path.mkdir(parents=True, exist_ok=True)

            # Scan for existing initrd images
            self._scan_initrd_images()

            self._initialized = True
            log.info("InitrdManager initialization complete. Found %d images.", len(self.images))
            return True

        except Exception as exc:
            log.error("InitrdManager initialization failed: %s", exc)
            return False

    def _scan_initrd_images(self) -> None:
        """Scan /boot for existing initrd images."""
        for pattern in self.INITRD_PATTERNS:
            for initrd_file in self.boot_path.glob(pattern):
                self._register_existing_image(initrd_file)

    def _register_existing_image(self, initrd_path: Path) -> None:
        """Register an existing initrd image."""
        name = initrd_path.name

        # Determine format from extension
        format_type = self._detect_format(name)

        # Extract kernel version from filename
        kernel_version = self._extract_kernel_version(name)

        # Determine purpose from filename
        purpose = self._detect_purpose(name)

        image = InitrdImage(
            name=name,
            path=str(initrd_path),
            format=format_type,
            purpose=purpose,
            kernel_version=kernel_version,
            status=InitrdStatus.VALID,
        )

        self.images[name] = image
        log.debug("Registered initrd image: %s", name)

    def _detect_format(self, filename: str) -> InitrdFormat:
        """Detect initrd format from filename."""
        if filename.endswith(".img.gz") or filename.endswith("-gz"):
            return InitrdFormat.CPIO_GZ
        elif filename.endswith(".img.xz") or filename.endswith("-xz"):
            return InitrdFormat.CPIO_XZ
        elif filename.endswith(".img.lz4") or filename.endswith("-lz4"):
            return InitrdFormat.CPIO_LZ4
        elif filename.endswith(".img.sqfs") or filename.endswith("-squashfs"):
            return InitrdFormat.SQUASHFS
        elif filename.endswith(".img.erofs") or filename.endswith("-erofs"):
            return InitrdFormat.ERofs
        elif filename.endswith(".tar.gz"):
            return InitrdFormat.TAR_GZ
        elif filename.endswith(".tar.xz"):
            return InitrdFormat.TAR_XZ
        else:
            return InitrdFormat.CPIO_GZ  # Default

    def _extract_kernel_version(self, filename: str) -> Optional[str]:
        """Extract kernel version from initrd filename."""
        import re
        # Match patterns like initrd.img-5.15.0-generic
        match = re.search(r"(?:initrd|initramfs)[.-](\d+\.\d+\.\d+[-\w]*)", filename)
        return match.group(1) if match else None

    def _detect_purpose(self, filename: str) -> InitrdPurpose:
        """Detect initrd purpose from filename."""
        if "recovery" in filename.lower():
            return InitrdPurpose.RECOVERY
        elif "live" in filename.lower():
            return InitrdPurpose.LIVE
        elif "rescue" in filename.lower():
            return InitrdPurpose.RESCUE
        elif "test" in filename.lower():
            return InitrdPurpose.TEST
        else:
            return InitrdPurpose.BOOT

    # ── Image Management ──────────────────────────────────────────────────

    def register_image(
        self,
        name: str,
        path: str,
        format_type: InitrdFormat = InitrdFormat.CPIO_GZ,
        purpose: InitrdPurpose = InitrdPurpose.BOOT,
        kernel_version: Optional[str] = None,
        description: str = "",
    ) -> InitrdImage:
        """
        Register an initrd image.

        Args:
            name: Image name
            path: Path to image file
            format_type: Image format
            purpose: Image purpose
            kernel_version: Kernel version this image is for
            description: Human-readable description

        Returns:
            Registered InitrdImage
        """
        image = InitrdImage(
            name=name,
            path=path,
            format=format_type,
            purpose=purpose,
            kernel_version=kernel_version,
            description=description,
        )

        self.images[name] = image
        log.info("Registered initrd image: %s", name)
        return image

    def get_image(self, name: str) -> Optional[InitrdImage]:
        """Get an initrd image by name."""
        return self.images.get(name)

    def list_images(
        self,
        purpose: Optional[InitrdPurpose] = None,
    ) -> List[InitrdImage]:
        """List initrd images, optionally filtered by purpose."""
        images = list(self.images.values())
        if purpose:
            images = [img for img in images if img.purpose == purpose]
        return images

    def remove_image(self, name: str) -> bool:
        """
        Remove an initrd image from tracking.

        Args:
            name: Image name to remove

        Returns:
            True if image was removed
        """
        if name in self.images:
            del self.images[name]
            log.info("Removed initrd image: %s", name)
            return True
        return False

    # ── Integrity Verification ────────────────────────────────────────────

    def verify_image(
        self,
        name: str,
        expected_hash: Optional[str] = None,
    ) -> bool:
        """
        Verify integrity of an initrd image.

        Args:
            name: Image name
            expected_hash: Expected SHA-256 hash (None to skip verification)

        Returns:
            True if verification passes
        """
        image = self.images.get(name)
        if not image:
            log.error("Initrd image not found: %s", name)
            return False

        if not os.path.isfile(image.path):
            image.status = InitrdStatus.MISSING
            log.error("Initrd image file missing: %s", image.path)
            return False

        # Compute hash if expected
        if expected_hash:
            try:
                computed_hash = self._compute_sha256(image.path)
                if computed_hash.lower() != expected_hash.lower():
                    image.status = InitrdStatus.CORRUPTED
                    log.error(
                        "Initrd hash mismatch: %s (expected: %s, got: %s)",
                        name, expected_hash[:16], computed_hash[:16],
                    )
                    return False
            except Exception as exc:
                log.error("Hash computation failed for %s: %s", name, exc)
                return False

        image.status = InitrdStatus.VALID
        log.info("Initrd image verified: %s", name)
        return True

    def _compute_sha256(self, file_path: str) -> str:
        """Compute SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def compute_image_hash(self, name: str) -> Optional[str]:
        """
        Compute SHA-256 hash of an initrd image.

        Args:
            name: Image name

        Returns:
            Hex digest string or None if image not found
        """
        image = self.images.get(name)
        if not image or not os.path.isfile(image.path):
            return None
        return self._compute_sha256(image.path)

    # ── Image Creation (Simplified) ───────────────────────────────────────

    def create_initrd(
        self,
        config: InitrdConfig,
        output_path: Optional[str] = None,
    ) -> bool:
        """
        Create an initrd image.

        When the ``initrd`` package is importable (it lives in
        ``F:\\Pension Person Details\\UmerOS\\initrd\\``) the manager
        delegates to :class:`initrd.builder.InitrdBuilder` so the
        resulting image is a real, bootable cpio archive.  When the
        package is not importable the manager falls back to the
        legacy placeholder stub so older callers keep working.

        Args:
            config: Initrd configuration
            output_path: Output path (None for default)

        Returns:
            True if creation successful
        """
        if output_path is None:
            output_path = str(
                self.boot_path / f"initrd.img-{config.kernel_version}"
            )

        log.info("Creating initrd image: %s", output_path)
        log.info("  Kernel version: %s", config.kernel_version)
        log.info("  Format: %s", config.format.value)

        # Delegate to the new /initrd package when it is available.
        # That package produces a real, bootable cpio archive; the
        # legacy placeholder below only writes a small text header.
        try:
            from initrd.builder import (  # type: ignore
                BuildRequest,
                InitrdBuilder,
                OutputFormat,
            )
            from initrd.scenarios import ScenarioId  # type: ignore
        except ImportError:
            self._legacy_create_initrd(config, output_path)
            return True

        try:
            format_map = {
                "cpio.gz": OutputFormat.CPIO_GZ,
                "cpio.xz": OutputFormat.CPIO_XZ,
                "cpio.lz4": OutputFormat.CPIO_LZ4,
                "tar.gz":  OutputFormat.CPIO_GZ,
                "tar.xz":  OutputFormat.CPIO_XZ,
                "squashfs": OutputFormat.CPIO_GZ,
                "erofs":   OutputFormat.CPIO_GZ,
            }
            request = BuildRequest(
                kernel_version=config.kernel_version,
                scenario=ScenarioId.NORMAL,
                output_format=format_map.get(
                    config.format.value, OutputFormat.CPIO_GZ
                ),
                output_path=output_path,
                modules=list(config.modules),
            )
            result = InitrdBuilder().build(request)
            # Register the new image so verify_image() can find it.
            self.register_image(
                name=os.path.basename(output_path),
                path=output_path,
                format_type=config.format,
                kernel_version=config.kernel_version,
                description=f"Initrd built via initrd.builder ({result.archiver})",
            )
            log.info("Initrd image built via initrd.builder: %s", output_path)
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("initrd.builder delegation failed (%s); falling back", exc)
            self._legacy_create_initrd(config, output_path)
            return True

    def _legacy_create_initrd(self, config: InitrdConfig, output_path: str) -> None:
        """Original placeholder writer, kept as a fallback."""
        log.info("  Modules: %d", len(config.modules))

        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Create a placeholder initrd file
            # In production, this would use mkinitramfs, dracut, etc.
            with open(output_path, "wb") as f:
                # Write a minimal header
                header = b"UmerOS Initrd\n"
                header += f"Version: {config.kernel_version}\n".encode()
                header += f"Format: {config.format.value}\n".encode()
                header += f"Created: {time.time()}\n".encode()
                f.write(header)

            # Register the new image
            self.register_image(
                name=os.path.basename(output_path),
                path=output_path,
                format_type=config.format,
                kernel_version=config.kernel_version,
                description=f"Initrd for kernel {config.kernel_version}",
            )

            log.info("Initrd image created: %s", output_path)
            return True

        except Exception as exc:
            log.error("Failed to create initrd image: %s", exc)
            return False

    # ── Module Management ─────────────────────────────────────────────────

    def add_module(
        self,
        name: str,
        path: str,
        description: str = "",
        dependencies: Optional[List[str]] = None,
    ) -> InitrdModule:
        """
        Add a kernel module to the initrd manager.

        Args:
            name: Module name
            path: Module file path
            description: Module description
            dependencies: Module dependencies

        Returns:
            Registered InitrdModule
        """
        module = InitrdModule(
            name=name,
            path=path,
            description=description,
            dependencies=dependencies or [],
        )

        self.modules[name] = module
        log.info("Added initrd module: %s", name)
        return module

    def list_modules(self) -> List[InitrdModule]:
        """List all registered modules."""
        return list(self.modules.values())

    def get_module(self, name: str) -> Optional[InitrdModule]:
        """Get a module by name."""
        return self.modules.get(name)

    # ── Utilities ─────────────────────────────────────────────────────────

    def get_image_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get status of an initrd image."""
        image = self.images.get(name)
        if not image:
            return None

        return {
            "name": image.name,
            "path": image.path,
            "format": image.format.value,
            "purpose": image.purpose.value,
            "status": image.status.value,
            "kernel_version": image.kernel_version,
            "size_bytes": image.size_bytes,
            "hash_sha256": image.hash_sha256,
            "timestamp": image.timestamp,
            "modules": image.modules,
            "description": image.description,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all initrd images."""
        return {
            "total_images": len(self.images),
            "total_modules": len(self.modules),
            "images_by_purpose": {
                purpose.value: len([
                    img for img in self.images.values()
                    if img.purpose == purpose
                ])
                for purpose in InitrdPurpose
            },
            "images_by_format": {
                fmt.value: len([
                    img for img in self.images.values()
                    if img.format == fmt
                ])
                for fmt in InitrdFormat
            },
        }


# ── Singleton ─────────────────────────────────────────────────────────────

_initrd_manager_instance: Optional[InitrdManager] = None


def get_initrd_manager(boot_path: str = "/boot") -> InitrdManager:
    """
    Get or create the singleton InitrdManager instance.

    Args:
        boot_path: Path to /boot directory

    Returns:
        InitrdManager instance
    """
    global _initrd_manager_instance
    if _initrd_manager_instance is None:
        _initrd_manager_instance = InitrdManager(boot_path)
        _initrd_manager_instance.initialize()
    return _initrd_manager_instance


def reset_initrd_manager() -> None:
    """Reset the singleton InitrdManager instance."""
    global _initrd_manager_instance
    _initrd_manager_instance = None
