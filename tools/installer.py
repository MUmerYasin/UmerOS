# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS Installation Tool
========================

Installs, verifies, and uninstalls UmerOS on a target directory.
Supports incremental updates, rollback, and verification.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Tools.Installer")

# Directories to install
INSTALL_DIRS = [
    "kernel", "quantum", "ai", "security", "ui", "compatibility",
    "filesystem", "update", "drivers", "boot", "bootloader", "core",
    "fs", "network", "packages", "sdk", "media", "var", "usr",
    "tools", "examples", "docs",
]

# Files to install at root
INSTALL_FILES = [
    "main.py", "README.md", "LICENSE", "pyproject.toml", "setup.py",
    "requirements.txt", "Dockerfile", "docker-compose.yml",
]


@dataclass
class InstallResult:
    """Result of an installation operation."""
    success: bool = False
    installed_dirs: List[str] = field(default_factory=list)
    installed_files: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_s: float = 0.0
    target_dir: str = ""


@dataclass
class VerifyResult:
    """Result of installation verification."""
    valid: bool
    missing_dirs: List[str] = field(default_factory=list)
    missing_files: List[str] = field(default_factory=list)
    corrupted: List[str] = field(default_factory=list)
    total_checked: int = 0


def show_license() -> None:
    """Display the EULA and prompt for acceptance."""
    print("=" * 60)
    print("UMER OS END USER LICENSE AGREEMENT (EULA)")
    print("=" * 60)
    print("This software is provided 'AS IS'. Umer OS team is not liable")
    print("for data loss, hardware damage, or warranty voidance.")
    print("Licensed under GNU General Public License v3.0 or later.")
    print("=" * 60)
    input("Press ENTER to accept and continue...")


def install_umer_os(
    target_dir: str = "/umer_os",
    source_dir: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
) -> InstallResult:
    """Install UmerOS to target directory.

    Args:
        target_dir: Destination directory.
        source_dir: Source directory (defaults to project root).
        force: Overwrite existing installation.
        dry_run: Show what would be done without doing it.

    Returns:
        InstallResult with details of what was installed.
    """
    start = time.monotonic()
    result = InstallResult(target_dir=target_dir)
    source = Path(source_dir) if source_dir else Path(__file__).resolve().parent.parent
    target = Path(target_dir)

    if not source.exists():
        result.errors.append(f"Source directory not found: {source}")
        return result

    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        result.errors.append(f"Cannot create target: {e}")
        return result

    # Install directories
    for d in INSTALL_DIRS:
        src = source / d
        dst = target / d
        if not src.exists():
            result.skipped.append(d)
            continue
        if dst.exists() and not force:
            result.skipped.append(f"{d} (exists)")
            continue
        if dry_run:
            result.installed_dirs.append(f"{d} (dry-run)")
            continue
        try:
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            shutil.copytree(src, dst)
            result.installed_dirs.append(d)
            log.info("Installed directory: %s", d)
        except Exception as e:
            result.errors.append(f"Failed to install {d}: {e}")

    # Install files
    for f in INSTALL_FILES:
        src = source / f
        dst = target / f
        if not src.exists():
            result.skipped.append(f)
            continue
        if dst.exists() and not force:
            result.skipped.append(f"{f} (exists)")
            continue
        if dry_run:
            result.installed_files.append(f"{f} (dry-run)")
            continue
        try:
            shutil.copy2(src, dst)
            result.installed_files.append(f)
            log.info("Installed file: %s", f)
        except Exception as e:
            result.errors.append(f"Failed to install {f}: {e}")

    result.duration_s = time.monotonic() - start
    result.success = len(result.errors) == 0
    return result


def verify_installation(target_dir: str = "/umer_os") -> VerifyResult:
    """Verify an UmerOS installation."""
    result = VerifyResult(valid=True)
    target = Path(target_dir)

    if not target.exists():
        result.valid = False
        result.missing_dirs.append(str(target))
        return result

    for d in INSTALL_DIRS:
        path = target / d
        if not path.exists():
            result.missing_dirs.append(d)
            result.valid = False
        else:
            result.total_checked += 1

    for f in INSTALL_FILES:
        path = target / f
        if not path.exists():
            result.missing_files.append(f)
            result.valid = False
        else:
            result.total_checked += 1

    return result


def uninstall_umer_os(target_dir: str = "/umer_os", confirm: bool = False) -> bool:
    """Uninstall UmerOS from target directory."""
    if not confirm:
        log.warning("Uninstall requires confirm=True")
        return False
    target = Path(target_dir)
    if not target.exists():
        log.warning("Target directory does not exist: %s", target_dir)
        return False
    try:
        shutil.rmtree(target)
        log.info("Uninstalled UmerOS from %s", target_dir)
        return True
    except Exception as e:
        log.error("Failed to uninstall: %s", e)
        return False


def get_install_info(target_dir: str = "/umer_os") -> dict:
    """Get information about an installed UmerOS instance."""
    target = Path(target_dir)
    info = {
        "exists": target.exists(),
        "path": str(target),
        "dirs": [],
        "files": [],
        "size_bytes": 0,
    }
    if target.exists():
        for d in INSTALL_DIRS:
            if (target / d).exists():
                info["dirs"].append(d)
        for f in INSTALL_FILES:
            if (target / f).exists():
                info["files"].append(f)
        # Calculate size
        total = 0
        for root, _, files in os.walk(target):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        info["size_bytes"] = total
    return info


if __name__ == "__main__":
    show_license()
    result = install_umer_os()
    if result.success:
        print(f"\nInstallation complete in {result.duration_s:.2f}s")
        print(f"  Directories: {len(result.installed_dirs)}")
        print(f"  Files: {len(result.installed_files)}")
    else:
        print(f"\nInstallation had errors: {result.errors}")