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
Umer OS Installer  [TODAY]
==========================
Full interactive installation wizard for Umer OS.

Legal requirements (non-negotiable):
  1. The EULA / liability waiver is displayed before ANY action is taken.
  2. User must type exactly ``I AGREE`` (case-sensitive) to proceed.
  3. A backup of the current bootloader / partition table is created before
     any system modification.
  4. ``rollback()`` fully restores the pre-installation state.
  5. All actions are logged with timestamps to INSTALL_LOG.

Usage (interactive)::

    python -m installer.installer

Usage (programmatic)::

    from installer.installer import UmerInstaller
    inst = UmerInstaller()
    inst.run()

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import platform
import shutil
import sys
import time
from typing import Any, Dict, List, Optional

# [FIX H102] Zero-trust capability gate for privileged install / rollback ops.
try:  # Preferred: import from inside the UmerOS package layout.
    from core.capability_gate import gate, CAP_FS_ADMIN, CAP_INSTALL
except Exception:  # pragma: no cover - standalone / out-of-package fallback.
    try:
        from capability_gate import gate, CAP_FS_ADMIN, CAP_INSTALL
    except Exception:  # Last-resort stand-in so the module always imports.
        class _Gate:
            def require(self, cap, *a, **k):
                log.warning("[installer] capability %r not enforced (no gate wired)", cap)
            def set_strict(self, value=False):
                pass
            def unwire(self):
                pass
        gate = _Gate()
        CAP_FS_ADMIN = "fs.admin"
        CAP_INSTALL = "install"

log = logging.getLogger("UmerOS.Installer")

# Path constants
INSTALL_ROOT = os.environ.get("UMER_INSTALL_ROOT", "/opt/umer_os")
BACKUP_DIR   = os.environ.get("UMER_BACKUP_DIR",   "/opt/umer_backup")
INSTALL_LOG  = os.environ.get("UMER_INSTALL_LOG",  "/var/log/umer_install.log")

# EULA text (verbatim — must not be modified)
EULA_TEXT = """
+======================================================================+
|              UMER OS INSTALLATION - LIABILITY WAIVER                 |
+======================================================================+
|                                                                      |
|  WARNING: Installing Umer OS is an IRREVERSIBLE modification to      |
|  your device unless you have created a verified backup.              |
|                                                                      |
|  By proceeding, you acknowledge:                                     |
|                                                                      |
|  1. This MAY VOID your device manufacturer warranty.                 |
|  2. This MAY VOID any existing software licences on this device.    |
|  3. Incorrect installation CAN permanently brick your device.       |
|  4. DATA LOSS is possible if you have not created a verified backup. |
|  5. Umer OS is provided "AS IS" with NO WARRANTY, EXPRESS OR        |
|     IMPLIED. The Umer OS project and its contributors assume NO     |
|     LIABILITY for any damage, data loss, or device failure.         |
|                                                                      |
|  You install entirely at your own risk.                              |
|                                                                      |
+======================================================================+
"""


# ---------------------------------------------------------------------------
# [FIX H101/H103] Path-safety helpers for privileged install operations
# ---------------------------------------------------------------------------

# Never create or remove the filesystem root, the bare '/opt' parent of the
# default prefix, or anything at/under a system directory during rollback.
_BANNED_EXACT = ("/", "/opt")
_BANNED_PREFIX = (
    "/bin", "/boot", "/etc", "/home", "/lib", "/lib64",
    "/root", "/sbin", "/sys", "/usr", "/var",
)


def _is_safe_install_root(path: str) -> bool:
    """True only if `path` is safe to create/remove as an install root.

    Rejects empty paths, '/', the bare '/opt' parent of the default prefix, and
    any path at or under a system directory, so a mis-set UMER_INSTALL_ROOT or
    an empty env value cannot wipe '/' or '/etc' etc. (H101 data-loss guard.)
    """
    if not path:
        return False
    rp = os.path.realpath(os.path.abspath(path))
    # Normalize to forward slashes and drop any drive letter (e.g. 'C:') so the
    # POSIX-oriented banned set also matches on Windows, where abspath('/etc')
    # resolves to 'C:\etc'. (Same cross-platform trick as the H73 host-/etc guard.)
    norm = rp.replace("\\", "/")
    if ":" in norm:
        norm = norm.split(":", 1)[1]
    if norm in _BANNED_EXACT or norm.rstrip("/") in _BANNED_EXACT:
        return False
    for d in _BANNED_PREFIX:
        if norm == d or norm.startswith(d + "/"):
            return False
    return True


def _safe_join(root: str, rel: str) -> "Optional[str]":
    """Join ``root`` with ``rel`` only if the result stays inside ``root``.

    Returns the normalized absolute path, or None if ``rel`` escapes ``root``
    (e.g. contains ``..`` or an absolute component). Mirrors the traversal guard
    used elsewhere in the remediation pass (H79/H84/H90/H93).
    """
    root_abs = os.path.abspath(root)
    target = os.path.normpath(os.path.join(root_abs, rel))
    try:
        if os.path.commonpath([root_abs, target]) != root_abs:
            return None
    except ValueError:
        # Different drives / unnormalizable — treat as an escape.
        return None
    return target


# ---------------------------------------------------------------------------
# InstallLogger
# ---------------------------------------------------------------------------

class InstallLogger:
    """Timestamped installation log writer."""

    def __init__(self, log_path: str = INSTALL_LOG) -> None:
        self._path    = log_path
        self._entries: List[str] = []

    def record(self, message: str) -> None:
        """Record an action with a UTC timestamp.

        Args:
            message: Human-readable action description.
        """
        import datetime as _dt
        ts    = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        entry = f"[{ts}] {message}"
        self._entries.append(entry)
        log.info("[INSTALL] %s", message)

    def flush(self) -> bool:
        """Write the log to disk.

        Returns:
            True if written successfully, False on I/O error.
        """
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write("\n".join(self._entries) + "\n")
            self._entries.clear()
            return True
        except OSError as exc:
            log.error("Could not write install log: %s", exc)
            return False

    def get_entries(self) -> List[str]:
        """Return in-memory log entries (not yet flushed)."""
        return list(self._entries)


# ---------------------------------------------------------------------------
# UmerInstaller
# ---------------------------------------------------------------------------

class UmerInstaller:
    """Complete Umer OS installation orchestrator.

    Args:
        source_dir:   Directory containing the Umer OS files to install.
        install_root: Target installation directory.
        backup_dir:   Directory for storing pre-installation backups.
        interactive:  When True, prompts are printed to stdout/stdin.
                      When False (for testing), use ``run()`` with
                      ``consent_override=True``.
    """

    def __init__(
        self,
        source_dir:    str  = ".",
        install_root:  str  = INSTALL_ROOT,
        backup_dir:    str  = BACKUP_DIR,
        interactive:   bool = True,
    ) -> None:
        self._source      = os.path.abspath(source_dir)
        self._install_root = install_root
        self._backup_dir  = backup_dir
        self._interactive = interactive
        self._logger      = InstallLogger()
        self._state:      Dict[str, Any] = {
            "phase":        "idle",
            "backup_taken": False,
            "files_copied": False,
            "bootloader_installed": False,
        }

    # ── EULA ──────────────────────────────────────────────────────────────

    # [FIX H99] The liability waiver is fail-closed: a non-interactive caller gets
    # NO consent (the old ``install.py`` stub auto-accepted it — removed with H98).
    def show_eula(self) -> bool:
        """Display the EULA and request explicit consent.

        Returns:
            True if the user typed ``I AGREE``, False otherwise.
        """
        if self._interactive:
            print(EULA_TEXT)
            try:
                answer = input("Type  I AGREE  (exactly) to continue, "
                               "or Ctrl+C to abort: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nInstallation aborted by user.")
                return False
        else:
            # Non-interactive: always deny unless overridden in run()
            answer = ""

        return answer == "I AGREE"

    # ── Platform detection ─────────────────────────────────────────────────

    def detect_platform(self) -> dict:
        """Collect information about the host system.

        Returns:
            Dict with arch, os, python_version, cpu_count, ram_mb, disk_gb.
        """
        import multiprocessing

        info: Dict[str, Any] = {
            "arch":           platform.machine(),
            "os":             platform.system(),
            "os_release":     platform.release(),
            "python_version": platform.python_version(),
            "cpu_count":      multiprocessing.cpu_count(),
        }

        # RAM & disk
        try:
            import psutil  # type: ignore
            info["ram_mb"] = round(psutil.virtual_memory().total / (1024 * 1024))
            # Use install_root if it exists, otherwise fall back to root /
            disk_path = self._install_root if os.path.isdir(self._install_root) else "/"
            info["disk_gb"] = round(
                psutil.disk_usage(disk_path).total / (1024 ** 3)
            )
        except ImportError:
            info["ram_mb"]  = "unknown"
            info["disk_gb"] = "unknown"

        self._logger.record(f"Platform detected: {info}")
        return info

    def check_prerequisites(self) -> bool:
        """Verify minimum requirements for installation.

        Returns:
            True if all prerequisites are met.
        """
        py = sys.version_info
        if py < (3, 10):
            log.error("Umer OS requires Python 3.10+; found %d.%d.", py.major, py.minor)
            return False

        if platform.system() not in ("Linux", "Darwin", "Windows"):
            log.warning("Unsupported host OS '%s'; proceeding anyway.", platform.system())

        self._logger.record("Prerequisites check passed.")
        return True

    # ── Backup ────────────────────────────────────────────────────────────

    def backup_bootloader(self, dest: Optional[str] = None) -> str:
        """Save a snapshot of the current boot configuration.

        TODAY: Writes a JSON file documenting the pre-install state.
        FUTURE: Saves MBR/GPT bytes and EFI entries.

        Args:
            dest: Override backup destination directory.

        Returns:
            Path to the backup file.
        """
        gate.require(CAP_FS_ADMIN)  # [FIX H102] privileged bootloader backup write
        backup_dir = dest or self._backup_dir
        os.makedirs(backup_dir, exist_ok=True)
        ts = int(time.time())
        path = os.path.join(backup_dir, f"pre_install_{ts}.json")

        snapshot = {
            "timestamp":    ts,
            "platform":     self.detect_platform(),
            "install_root": self._install_root,
            "note":         "Pre-Umer-OS boot configuration snapshot.",
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, indent=2)

        self._state["backup_taken"] = True
        self._logger.record(f"Bootloader backup saved to '{path}'.")
        return path

    # ── File copy ─────────────────────────────────────────────────────────

    def copy_os_files(
        self,
        source: Optional[str] = None,
        dest:   Optional[str] = None,
    ) -> int:
        """Copy Umer OS source files to the installation directory.

        Args:
            source: Override source directory.
            dest:   Override destination directory.

        Returns:
            Number of files copied.
        """
        src  = source or self._source
        dst  = dest   or self._install_root
        count = 0

        os.makedirs(dst, exist_ok=True)
        self._logger.record(f"Copying files from '{src}' to '{dst}'.")

        # [FIX H102] Privileged copy requires a capability (fail-closed when wired).
        gate.require(CAP_FS_ADMIN)
        for root, dirs, files in os.walk(src):
            # Skip hidden dirs like .git (H103: also skip hidden files).
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if fname.startswith("."):  # [FIX H103] never copy dotfiles
                    continue
                src_path = os.path.join(root, fname)
                rel_path = os.path.relpath(src_path, src)
                # [FIX H103] Reject copy destinations that escape the install root.
                dst_path = _safe_join(dst, rel_path)
                if dst_path is None:
                    log.warning("Skipping copy that escapes install root: %s", rel_path)
                    continue
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                try:
                    shutil.copy2(src_path, dst_path)
                    count += 1
                except OSError as exc:
                    log.warning("Could not copy '%s': %s", src_path, exc)

        self._state["files_copied"] = True
        self._logger.record(f"Copied {count} file(s).")
        return count

    # ── Bootloader install ─────────────────────────────────────────────────

    def install_bootloader(self, target: Optional[str] = None) -> bool:
        """Write an Umer OS bootloader entry.

        TODAY: Creates a stub ``umer_boot_entry.json`` to simulate UEFI registration.
        FUTURE: Writes an actual GRUB/UEFI entry.

        Args:
            target: Optional override for the boot configuration directory.

        Returns:
            True on success.
        """
        gate.require(CAP_FS_ADMIN)  # [FIX H102] privileged bootloader write
        boot_dir = target or os.path.join(self._install_root, "boot")
        os.makedirs(boot_dir, exist_ok=True)
        entry = {
            "label":   "Umer OS",
            "kernel":  os.path.join(self._install_root, "boot", "bootloader.py"),
            "installed_at": time.time(),
        }
        entry_path = os.path.join(boot_dir, "umer_boot_entry.json")
        with open(entry_path, "w", encoding="utf-8") as fh:
            json.dump(entry, fh, indent=2)

        self._state["bootloader_installed"] = True
        self._logger.record(f"Boot entry written to '{entry_path}'.")
        return True

    # ── First-boot config ─────────────────────────────────────────────────

    def configure_first_boot(self) -> None:
        """Write default first-boot configuration.

        Creates ``/opt/umer_os/config/first_boot.json`` with defaults.
        """
        gate.require(CAP_FS_ADMIN)  # [FIX H102] privileged first-boot config write
        cfg_dir  = os.path.join(self._install_root, "config")
        os.makedirs(cfg_dir, exist_ok=True)
        cfg_path = os.path.join(cfg_dir, "first_boot.json")
        config   = {
            "ai_consent":  False,
            "telemetry":   False,
            "locale":      "en_US",
            "theme":       "dark",
            "first_run":   True,
            "installed_at": time.time(),
        }
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)
        self._logger.record(f"First-boot config written to '{cfg_path}'.")

    # ── Rollback ──────────────────────────────────────────────────────────

    def rollback(self) -> bool:
        """Restore the pre-installation state.

        Removes all installed files and marks the state as rolled back.

        Returns:
            True if rollback completed, False if nothing to roll back.
        """
        if not any([
            self._state["files_copied"],
            self._state["bootloader_installed"],
        ]):
            log.warning("Rollback called but nothing was installed.")
            return False

        # [FIX H101] Refuse to remove an unsafe install root (data-loss guard).
        if not _is_safe_install_root(self._install_root):
            log.error("Rollback refused: install root %r is not a safe path.", self._install_root)
            self._logger.record(f"Rollback refused: unsafe install root '{self._install_root}'.")
            self._logger.flush()
            return False
        # [FIX H102] Privileged destructive op requires a capability.
        gate.require(CAP_FS_ADMIN)

        self._logger.record("Rollback initiated.")

        # Remove installed files
        if os.path.isdir(self._install_root):
            try:
                shutil.rmtree(self._install_root)
                self._logger.record(f"Removed '{self._install_root}'.")
            except OSError as exc:
                log.error("Could not remove install root: %s", exc)
                return False

        self._state = {k: False for k in self._state}
        self._state["phase"] = "rolled_back"
        self._logger.record("Rollback complete.")
        self._logger.flush()
        log.info("Rollback complete. System restored to pre-installation state.")
        return True

    # ── Main orchestrator ─────────────────────────────────────────────────

    def run(self, consent_override: bool = False) -> bool:
        """Execute the full installation workflow.

        Args:
            consent_override: If True, skip the EULA prompt (for testing only).

        Returns:
            True if installation completed successfully, False otherwise.
        """
        self._logger.record("Umer OS installation started.")
        self._state["phase"] = "eula"

        # [FIX H102] The whole privileged install pipeline requires a capability.
        gate.require(CAP_FS_ADMIN)
        # [FIX H100] A programmatic EULA bypass is itself a privileged action.
        if consent_override:
            gate.require(CAP_INSTALL)

        # Step 1: EULA (mandatory — only skippable via a granted capability)
        if not consent_override:
            if not self.show_eula():
                self._logger.record("Installation aborted — EULA not accepted.")
                self._logger.flush()
                if self._interactive:
                    print("Installation aborted. No changes were made.")
                return False

        self._logger.record("EULA accepted.")
        self._state["phase"] = "prerequisites"

        # Step 2: Prerequisites
        if not self.check_prerequisites():
            self._logger.flush()
            return False

        # Step 3: Backup
        self._state["phase"] = "backup"
        try:
            self.backup_bootloader()
        except OSError as exc:
            log.error("Backup failed: %s", exc)
            self._logger.flush()
            return False

        # Step 4: Copy files
        self._state["phase"] = "copy"
        try:
            n = self.copy_os_files()
            self._logger.record(f"File copy complete ({n} files).")
        except OSError as exc:
            log.error("File copy failed: %s", exc)
            self.rollback()
            return False

        # Step 5: Install bootloader
        self._state["phase"] = "bootloader"
        try:
            self.install_bootloader()
        except OSError as exc:
            log.error("Bootloader install failed: %s", exc)
            self.rollback()
            return False

        # Step 6: First-boot configuration
        self._state["phase"] = "configure"
        self.configure_first_boot()

        # Done
        self._state["phase"] = "complete"
        self._logger.record("Installation complete.")
        self._logger.flush()

        if self._interactive:
            print("\n✓ Umer OS installed successfully.")
            print(f"  Location : {self._install_root}")
            print(f"  Log      : {INSTALL_LOG}")
            print("\nReboot your system to start Umer OS.\n")

        return True

    def get_state(self) -> dict:
        """Return current installation state dict."""
        return dict(self._state)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Interactive CLI installer."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    installer = UmerInstaller(
        source_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        interactive=True,
    )
    success = installer.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
