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

Honored guarantees ([TODAY] — enforced by this module):
  1. The EULA / liability waiver is displayed before ANY action is taken.
  2. The user must type exactly ``I AGREE`` (case-sensitive) to proceed.
  3. All actions are logged with timestamps to INSTALL_LOG.

Partial / [FUTURE] guarantees (NOT fully honored yet — do not over-read):
  4. ``backup_bootloader()`` writes a **metadata-only** JSON snapshot of the
     pre-install state (timestamp, platform, install root). Capturing real
     MBR/GPT bytes and EFI entries is [FUTURE], so the installer does NOT
     currently back up the partition table.
  5. ``rollback()`` removes the files it installed (``rmtree`` of the install
     root) and resets state. It does NOT restore a bootloader or partition
     table; a true pre-install restore is [FUTURE].

The waiver text was softened to match TODAY's behaviour so the
module no longer over-promises a backup/restore contract it does not
implement (compounds H99/H101). Machine-readable status:
``BACKUP_CAPTURES_BOOT_BYTES`` and ``ROLLBACK_RESTORES_BOOT_STATE`` are both
False until the [FUTURE] work lands.

Usage (interactive)::

    python -m installer.installer

Usage (programmatic)::

    from installer.installer import UmerInstaller
    inst = UmerInstaller()
    inst.run()

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import platform
import shutil
import sys
import time
from typing import Any, Dict, List, Optional

# Zero-trust capability gate for privileged install / rollback ops.
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

# Pinned source-tree manifest. When this file is present in the
# install source directory it is treated as the authority for what may be
# copied: every source file's SHA3-512 digest must match the manifest entry,
# or the install refuses to copy (fail-closed). Obtaining the manifest from a
# trusted release channel is the operator's responsibility (the same
# trust model as a signed release artefact); the installer enforces
# hash-consistency against it. Format:
#   {"files": {"<rel/path>": "<sha3-512 hex>", ...}, "tree": "<hex>"}
INSTALL_MANIFEST_NAME = os.environ.get(
    "UMER_INSTALL_MANIFEST", "umer-install-manifest.json"
)

# Honest capability flags. The waiver / docstring must not claim
# more than the shipping code does. TODAY: the pre-install backup is a
# metadata-only JSON snapshot (no MBR/GPT bytes, no EFI entries) and rollback
# only removes the install root. Capturing boot bytes and performing a true
# boot/partition restore are [FUTURE]. These flags are the single source of
# truth the docs and tests reference.
BACKUP_CAPTURES_BOOT_BYTES = False   # [FUTURE] real MBR/GPT/EFI byte backup
ROLLBACK_RESTORES_BOOT_STATE = False  # [FUTURE] true boot/partition restore

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
# Path-safety helpers for privileged install operations
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


def _sha3_512_file(path: str) -> str:
    """Return the SHA3-512 hex digest of ``path`` (streamed).

    SHA3-512 is the UmerOS design-mandate hash (H97); streaming
    keeps memory bounded for large artefacts.
    """
    h = hashlib.sha3_512()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_digest(pairs: "List[tuple[str, str]]") -> str:
    """Deterministic aggregate digest over ``(rel_path, sha3_512)`` pairs.

    Sorted by path so the digest is order-independent; mirrors the
    payload-hash construction used by ``packages.umer_pkg``.
    """
    h = hashlib.sha3_512()
    for rel, digest in sorted(pairs, key=lambda x: x[0]):
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(digest.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


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

    # The liability waiver is fail-closed: a non-interactive caller gets
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
        """Save a **metadata-only** snapshot of the current boot configuration.

        TODAY: writes a JSON file documenting the pre-install state
        (timestamp, platform, install root). It does **not** capture MBR/GPT
        bytes or EFI entries, so it cannot be used to restore a bootloader or
        partition table — that is [FUTURE] (see ``BACKUP_CAPTURES_BOOT_BYTES``).
        The waiver text has been softened accordingly.

        Args:
            dest: Override backup destination directory.

        Returns:
            Path to the backup file.
        """
        gate.require(CAP_FS_ADMIN)  #  privileged bootloader backup write
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

    # ── Source integrity (H108) ───────────────────────────────────────────

    def _iter_source_files(self, src: str):
        """Yield ``(rel_path, abs_path)`` for every copyable source file.

        Mirrors the filtering used by :meth:`copy_os_files` (skip hidden
        dirs/files) so verification and copy see the same file set.
        """
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if fname.startswith("."):
                    continue
                abs_path = os.path.join(root, fname)
                yield os.path.relpath(abs_path, src), abs_path

    def verify_source_integrity(
        self,
        source: Optional[str] = None,
        require_manifest: Optional[bool] = None,
    ):
        """Verify the source tree against a pinned manifest.

        The installer previously copied whatever was at ``source_dir`` with no
        integrity check, so a swapped/tampered source tree was installed
        unverified. This method enforces hash-consistency against
        ``INSTALL_MANIFEST_NAME`` (a pinned ``{rel_path: sha3_512}`` manifest)
        BEFORE anything is copied.

        Args:
            source: Override source directory (defaults to ``self._source``).
            require_manifest: Force the no-manifest policy. ``None`` follows
                the capability gate's strict mode (``gate.strict`` /
                ``UMEROS_STRICT_GATE``); ``True`` always fails closed when no
                manifest is present; ``False`` always permits-with-warning.

        Returns:
            ``(ok, tree_digest)``. ``ok`` is True when the tree may be copied
            (verified, or permitted-with-warning). ``tree_digest`` is the
            verified aggregate SHA3-512, or ``None`` when unverified.
        """
        src = os.path.abspath(source or self._source)
        if require_manifest is None:
            require_manifest = bool(getattr(gate, "strict", False))

        manifest_path = os.path.join(src, INSTALL_MANIFEST_NAME)
        if not os.path.isfile(manifest_path):
            msg = (
                f"No pinned source manifest ('{INSTALL_MANIFEST_NAME}') found in "
                f"'{src}' — source integrity is UNVERIFIABLE."
            )
            if require_manifest:
                log.error(msg + " Refusing to copy (strict).")
                self._logger.record(msg + " Refusing to copy (fail-closed).")
                return False, None
            log.warning(msg + " Proceeding without verification.")
            self._logger.record(msg + " Proceeding (non-strict).")
            return True, None

        # A manifest is present: it is authoritative. Any parse error, missing
        # entry, or digest mismatch is a hard failure (fail-closed).
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError) as exc:
            log.error("Could not read source manifest '%s': %s", manifest_path, exc)
            self._logger.record(f"Source manifest unreadable — refusing to copy: {exc}")
            return False, None

        if isinstance(raw, dict) and isinstance(raw.get("files"), dict):
            expected: Dict[str, str] = raw["files"]
        elif isinstance(raw, dict):
            expected = raw
        else:
            log.error("Malformed source manifest (not a mapping): %s", manifest_path)
            self._logger.record("Malformed source manifest — refusing to copy.")
            return False, None

        expected_norm = {
            str(k).replace(os.sep, "/"): str(v).strip().lower()
            for k, v in expected.items()
        }

        pairs: "List[tuple[str, str]]" = []
        mismatches: List[str] = []
        seen = set()
        for rel, abs_path in self._iter_source_files(src):
            if rel == INSTALL_MANIFEST_NAME:
                continue  # the manifest does not attest itself
            rel_norm = rel.replace(os.sep, "/")
            seen.add(rel_norm)
            try:
                actual = _sha3_512_file(abs_path)
            except OSError as exc:
                mismatches.append(f"{rel_norm}: unreadable ({exc})")
                continue
            want = expected_norm.get(rel_norm)
            if want is None:
                mismatches.append(f"{rel_norm}: not listed in manifest")
            elif want != actual:
                mismatches.append(f"{rel_norm}: digest mismatch")
            else:
                pairs.append((rel_norm, actual))

        # Files the manifest attests but which are absent on disk.
        missing = sorted(set(expected_norm) - seen)
        for rel_norm in missing:
            mismatches.append(f"{rel_norm}: present in manifest but missing on disk")

        if mismatches:
            detail = "; ".join(mismatches[:10])
            log.error("Source integrity FAILED (%d issue(s)): %s",
                      len(mismatches), detail)
            self._logger.record(
                f"Source integrity FAILED ({len(mismatches)} issue(s)) — "
                f"refusing to copy: {detail}"
            )
            return False, None

        digest = _tree_digest(pairs)
        log.info("Source integrity OK: %d file(s), tree SHA3-512=%s", len(pairs), digest)
        self._logger.record(
            f"Source integrity OK: {len(pairs)} file(s) verified against "
            f"'{INSTALL_MANIFEST_NAME}'; tree SHA3-512={digest}"
        )
        return True, digest

    # ── File copy ─────────────────────────────────────────────────────────

    def copy_os_files(
        self,
        source: Optional[str] = None,
        dest:   Optional[str] = None,
    ) -> int:
        """Copy Umer OS source files to the installation directory.

        The source tree is integrity-verified against the pinned
        manifest BEFORE anything is copied; a failed verification copies
        nothing and returns 0. The verified aggregate digest is recorded in
        the install log.

        Args:
            source: Override source directory.
            dest:   Override destination directory.

        Returns:
            Number of files copied (0 if verification refused the copy).
        """
        src  = source or self._source
        dst  = dest   or self._install_root
        count = 0

        # Verify authenticity before touching the destination.
        verified, digest = self.verify_source_integrity(src)
        if not verified:
            log.error("Aborting copy: source integrity verification failed.")
            self._logger.record("Copy aborted — source integrity verification failed.")
            return 0
        if digest:
            self._logger.record(f"Verified source tree digest: {digest}")

        #  Privileged copy requires a capability (fail-closed when wired).
        gate.require(CAP_FS_ADMIN)
        os.makedirs(dst, exist_ok=True)
        self._logger.record(f"Copying files from '{src}' to '{dst}'.")

        for root, dirs, files in os.walk(src):
            # Skip hidden dirs like .git (H103: also skip hidden files).
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if fname.startswith("."):  #  never copy dotfiles
                    continue
                src_path = os.path.join(root, fname)
                rel_path = os.path.relpath(src_path, src)
                #  Reject copy destinations that escape the install root.
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
        gate.require(CAP_FS_ADMIN)  #  privileged bootloader write
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
        gate.require(CAP_FS_ADMIN)  # privileged first-boot config write
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
        """Remove the files this installer created and mark the state rolled back.

        This is a **best-effort cleanup**, not a full restore: it
        ``rmtree``s the install root and resets state. It does **not** restore
        a bootloader or partition table (the metadata backup is not sufficient
        for that) — a true pre-install restore is [FUTURE] (see
        ``ROLLBACK_RESTORES_BOOT_STATE``).

        Returns:
            True if rollback completed, False if nothing to roll back.
        """
        if not any([
            self._state["files_copied"],
            self._state["bootloader_installed"],
        ]):
            log.warning("Rollback called but nothing was installed.")
            return False

        # Refuse to remove an unsafe install root (data-loss guard).
        if not _is_safe_install_root(self._install_root):
            log.error("Rollback refused: install root %r is not a safe path.", self._install_root)
            self._logger.record(f"Rollback refused: unsafe install root '{self._install_root}'.")
            self._logger.flush()
            return False
        # Privileged destructive op requires a capability.
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
        # Accurate wording — only the installed files were removed;
        # no bootloader/partition state was restored.
        log.info("Rollback complete. Installed files removed; install root cleaned up.")
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

        # The whole privileged install pipeline requires a capability.
        gate.require(CAP_FS_ADMIN)
        # A programmatic EULA bypass is itself a privileged action.
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
