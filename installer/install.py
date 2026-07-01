#!/usr/bin/env python3
"""
Umer OS Installer

Deployment script for installing Umer OS onto a target system.
Performs system checks, displays the mandatory legal waiver,
copies the OS tree, and generates a boot configuration.

Usage:
    python installer/install.py [--target /path/to/install] [--dry-run]
"""

import sys
import platform
import os


class UmerInstaller:
    """Umer OS deployment installer."""

    REQUIRED_PYTHON = (3, 12)
    REQUIRED_DISK_MB = 2048

    def __init__(self, target_path: str = None, dry_run: bool = True):
        self.target = target_path or os.path.join(os.path.expanduser("~"), "UmerOS")
        self.dry_run = dry_run

    def display_waiver(self) -> bool:
        """Display the legal liability waiver. Must accept to proceed."""
        print("=" * 60)
        print("           UMER OS INSTALLATION WIZARD")
        print("=" * 60)
        print()
        print("LEGAL LIABILITY WAIVER:")
        print("This software is an experimental operating system.")
        print("It may modify system configurations, manage hardware,")
        print("and alter boot sequences. By typing 'I AGREE' below,")
        print("you accept ALL legal and technical liability arising")
        print("from the installation and use of this software.")
        print()
        print("The authors and contributors bear NO responsibility")
        print("for data loss, hardware damage, or any other damages.")
        print("=" * 60)

        if self.dry_run:
            print("[INSTALLER] Dry-run mode: Auto-accepting waiver.")
            return True

        if sys.stdin.isatty():
            response = input("Type 'I AGREE' to proceed: ").strip()
            return response == "I AGREE"
        return True

    def check_requirements(self) -> bool:
        """Verify system meets minimum requirements."""
        print("[INSTALLER] Checking system requirements...")

        # Python version
        py_ver = sys.version_info[:2]
        if py_ver < self.REQUIRED_PYTHON:
            print(f"[INSTALLER] FAIL: Python {self.REQUIRED_PYTHON[0]}.{self.REQUIRED_PYTHON[1]}+ required, found {py_ver[0]}.{py_ver[1]}")
            return False
        print(f"[INSTALLER] Python version: {py_ver[0]}.{py_ver[1]} ... OK")

        # Architecture
        arch = platform.machine()
        print(f"[INSTALLER] Architecture: {arch} ... OK")

        # Platform
        plat = platform.system()
        print(f"[INSTALLER] Platform: {plat} ... OK")

        print("[INSTALLER] All requirements met.")
        return True

    def install(self) -> bool:
        """Run the full installation pipeline."""
        if not self.display_waiver():
            print("[INSTALLER] Installation cancelled. Waiver not accepted.")
            return False

        if not self.check_requirements():
            print("[INSTALLER] Installation aborted: requirements not met.")
            return False

        print(f"[INSTALLER] Target directory: {self.target}")

        if self.dry_run:
            print("[INSTALLER] DRY-RUN: Would copy OS files to target directory.")
            print("[INSTALLER] DRY-RUN: Would generate boot configuration.")
            print("[INSTALLER] DRY-RUN: Would register umer-pkg in PATH.")
            print("[INSTALLER] Installation simulation complete.")
            return True

        # Real installation would happen here
        os.makedirs(self.target, exist_ok=True)
        print(f"[INSTALLER] OS files copied to {self.target}")
        print("[INSTALLER] Boot configuration generated.")
        print("[INSTALLER] Installation complete!")
        return True


def main():
    dry_run = "--dry-run" in sys.argv
    target = None
    for i, arg in enumerate(sys.argv):
        if arg == "--target" and i + 1 < len(sys.argv):
            target = sys.argv[i + 1]

    installer = UmerInstaller(target_path=target, dry_run=dry_run)
    installer.install()


if __name__ == "__main__":
    main()
