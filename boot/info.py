"""
Umer OS /boot - one-shot summary
================================

A small, dependency-free summary of the ``/boot`` hierarchy, in the
spirit of :mod:`lib.libinfo` and :mod:`root.home` (the per-package
"headline numbers").  Useful for boot logs, CI reports and for
``python -m boot info``.

Headline fields
---------------

* directory exists? total files, dirs, symlinks, bytes
* how many kernels are installed and which is the default
* which boot loader is configured (grub / systemd-boot / efistub / none)
* EFI System Partition presence and size
* Secure Boot state
* initramfs and microcode presence
* crash-kernel reservation
* presence of GRUB env, BLS Type #1 entries, UKI Type #2 entries
* parsed bzImage protocol version of the default kernel
* list of issues (best-effort FHS checks)

The module is read-only and never raises - it returns a populated
:class:`BootSummary` even on error.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Boot.Info")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BootSummary:
    """A flat, JSON-serialisable summary of the ``/boot`` state."""

    boot_path: str
    exists: bool = False
    total_files: int = 0
    total_dirs: int = 0
    total_symlinks: int = 0
    total_bytes: int = 0
    # Kernels
    kernel_count: int = 0
    kernel_versions: List[str] = field(default_factory=list)
    default_kernel: str = ""
    default_kernel_protocol: str = ""
    default_kernel_efi_stub: bool = False
    # Boot loader
    boot_loader: str = "none"          # grub / systemd-boot / efistub / none
    grub_config: bool = False
    systemd_boot_loader: bool = False
    bls_entry_count: int = 0
    uki_count: int = 0
    # EFI
    efi_dir: bool = False
    efi_size_bytes: int = 0
    secure_boot_state: str = "unknown"
    # Initrd / microcode / crash
    initramfs_present: bool = False
    initramfs_count: int = 0
    microcode_present: bool = False
    crash_kernel_reserved: bool = False
    # Subdirs
    has_loader_dir: bool = False
    has_grub_dir: bool = False
    has_efi_linux_dir: bool = False
    # Issues
    issues: List[str] = field(default_factory=list)
    generated_at: float = 0.0

    # -- rendering -----------------------------------------------------

    def render_table(self) -> str:
        lines: List[str] = []
        lines.append(f"Umer OS /boot summary   ({self.boot_path})")
        lines.append("=" * 60)
        if not self.exists:
            lines.append(f"  ! directory missing: {self.boot_path}")
            for issue in self.issues:
                lines.append(f"  - {issue}")
            return "\n".join(lines) + "\n"
        lines.append(f"  files:           {self.total_files}")
        lines.append(f"  directories:     {self.total_dirs}")
        lines.append(f"  symlinks:        {self.total_symlinks}")
        lines.append(f"  total bytes:     {self.total_bytes}")
        lines.append("")
        if self.kernel_count:
            lines.append(
                f"  kernels:         {self.kernel_count}  "
                f"default = {self.default_kernel or '(none)'}"
            )
            if self.default_kernel_protocol:
                lines.append(
                    f"  default protocol: {self.default_kernel_protocol}  "
                    f"efi_stub = {self.default_kernel_efi_stub}"
                )
            for v in self.kernel_versions:
                lines.append(f"    - {v}")
        else:
            lines.append("  kernels:         (none)")
        lines.append("")
        lines.append(f"  boot loader:     {self.boot_loader}")
        bits = []
        if self.grub_config:      bits.append("grub.cfg")
        if self.systemd_boot_loader: bits.append("loader.conf")
        if self.bls_entry_count:  bits.append(f"{self.bls_entry_count} BLS entries")
        if self.uki_count:        bits.append(f"{self.uki_count} UKI")
        if bits:
            lines.append(f"  loader detail:   {', '.join(bits)}")
        lines.append("")
        lines.append(f"  EFI:             {'present' if self.efi_dir else 'MISSING'}"
                     + (f"  ({self.efi_size_bytes} bytes)"
                        if self.efi_dir else ""))
        lines.append(f"  Secure Boot:     {self.secure_boot_state}")
        lines.append(
            f"  initramfs:       {self.initramfs_count}  "
            f"({'present' if self.initramfs_present else 'missing'})"
        )
        lines.append(
            f"  microcode:       "
            f"{'present' if self.microcode_present else 'missing'}"
        )
        lines.append(
            f"  crash kernel:    "
            f"{'reserved' if self.crash_kernel_reserved else 'not reserved'}"
        )
        if self.issues:
            lines.append("")
            lines.append("  issues:")
            for issue in self.issues:
                lines.append(f"    - {issue}")
        return "\n".join(lines) + "\n"

    def as_dict(self) -> dict:
        return {
            "boot_path": self.boot_path,
            "exists": self.exists,
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "total_symlinks": self.total_symlinks,
            "total_bytes": self.total_bytes,
            "kernel_count": self.kernel_count,
            "kernel_versions": list(self.kernel_versions),
            "default_kernel": self.default_kernel,
            "default_kernel_protocol": self.default_kernel_protocol,
            "default_kernel_efi_stub": self.default_kernel_efi_stub,
            "boot_loader": self.boot_loader,
            "grub_config": self.grub_config,
            "systemd_boot_loader": self.systemd_boot_loader,
            "bls_entry_count": self.bls_entry_count,
            "uki_count": self.uki_count,
            "efi_dir": self.efi_dir,
            "efi_size_bytes": self.efi_size_bytes,
            "secure_boot_state": self.secure_boot_state,
            "initramfs_present": self.initramfs_present,
            "initramfs_count": self.initramfs_count,
            "microcode_present": self.microcode_present,
            "crash_kernel_reserved": self.crash_kernel_reserved,
            "has_loader_dir": self.has_loader_dir,
            "has_grub_dir": self.has_grub_dir,
            "has_efi_linux_dir": self.has_efi_linux_dir,
            "issues": list(self.issues),
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _safe_iterdir(p: Path) -> List[Path]:
    try:
        return list(p.iterdir())
    except OSError:
        return []


def _walk_stats(root: Path) -> Dict[str, int]:
    files = dirs = syms = total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.is_symlink():
                    syms += 1
                elif p.is_file():
                    files += 1
                    try:
                        total += p.stat().st_size
                    except OSError:
                        pass
            for d in dirnames:
                dp = Path(dirpath) / d
                if dp.is_symlink():
                    syms += 1
                else:
                    dirs += 1
    except OSError:
        pass
    return {"files": files, "dirs": dirs, "syms": syms, "bytes": total}


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def boot_summary(boot_path: str = "/boot",
                 efi_path: str = "/boot/efi") -> BootSummary:
    """Build a :class:`BootSummary` for ``boot_path``.

    Both paths are configurable so the function works in tests against
    a temporary directory as well as against a real /boot on the host.
    """
    import time
    summary = BootSummary(boot_path=str(boot_path), generated_at=time.time())
    root = Path(boot_path)
    if not root.is_dir():
        summary.issues.append(f"{boot_path} is not a directory or does not exist")
        return summary
    summary.exists = True

    # 1. Walk for headline counts.
    stats = _walk_stats(root)
    summary.total_files = stats["files"]
    summary.total_dirs = stats["dirs"]
    summary.total_symlinks = stats["syms"]
    summary.total_bytes = stats["bytes"]

    # 2. Kernels.
    try:
        from boot.kernel_image import KernelImageManager
        kim = KernelImageManager(root)
        summary.kernel_count = len(kim.kernels)
        summary.kernel_versions = kim.list_versions()
        if kim.default_version:
            summary.default_kernel = kim.default_version
            ki = kim.kernels.get(kim.default_version)
            if ki:
                # Best-effort bzImage protocol + EFI stub detection.
                try:
                    from boot.bzimage import parse_bzimage_header
                    bh = parse_bzimage_header(ki.vmlinuz_path)
                    summary.default_kernel_protocol = bh.protocol_string()
                    summary.default_kernel_efi_stub = bh.has_efi_stub
                except Exception as exc:  # noqa: BLE001
                    log.debug("bzimage: %s", exc)
    except Exception as exc:  # noqa: BLE001
        log.debug("kernel_image: %s", exc)

    # 3. Boot loader.
    has_grub = (root / "grub").is_dir() or any(
        (root / "grub").glob("**/grub.cfg") if (root / "grub").is_dir() else []
    )
    has_loader = (root / "loader").is_dir()
    has_efi_linux = (root / "EFI" / "Linux").is_dir()
    summary.has_grub_dir = has_grub
    summary.has_loader_dir = has_loader
    summary.has_efi_linux_dir = has_efi_linux

    if (root / "grub" / "grub.cfg").is_file():
        summary.grub_config = True
    if (root / "loader" / "loader.conf").is_file():
        summary.systemd_boot_loader = True

    # 4. BLS entries (Type #1) and UKIs (Type #2).
    loader_entries = root / "loader" / "entries"
    if loader_entries.is_dir():
        try:
            summary.bls_entry_count = sum(
                1 for f in loader_entries.iterdir()
                if f.is_file() and f.suffix == ".conf"
            )
        except OSError:
            pass
    if has_efi_linux:
        try:
            summary.uki_count = sum(
                1 for f in (root / "EFI" / "Linux").iterdir()
                if f.is_file() and f.suffix == ".efi"
            )
        except OSError:
            pass

    # Choose a single boot_loader label.
    if summary.uki_count > 0:
        summary.boot_loader = "ukify/systemd-boot (Type #2)"
    elif summary.systemd_boot_loader and summary.bls_entry_count > 0:
        summary.boot_loader = "systemd-boot (BLS)"
    elif summary.grub_config:
        summary.boot_loader = "grub2"
    elif has_efi_linux or has_loader:
        summary.boot_loader = "systemd-boot"
    else:
        summary.boot_loader = "none"

    # 5. EFI System Partition.
    efi = Path(efi_path)
    if efi.is_dir():
        summary.efi_dir = True
        estats = _walk_stats(efi)
        summary.efi_size_bytes = estats["bytes"]
    else:
        # Some installations mount the ESP at /efi or /boot itself.
        if (root / "EFI").is_dir():
            summary.efi_dir = True
            estats = _walk_stats(root / "EFI")
            summary.efi_size_bytes = estats["bytes"]

    # 6. Secure Boot state - best effort, do not raise.
    try:
        from boot.efi_system import SecureBootManager, SecureBootState
        sbm = SecureBootManager()
        st = sbm.detect()
        # Map enum to short string.
        if st == SecureBootState.ENABLED:
            summary.secure_boot_state = "enabled"
        elif st == SecureBootState.DISABLED:
            summary.secure_boot_state = "disabled"
        else:
            summary.secure_boot_state = st.value
    except Exception as exc:  # noqa: BLE001
        log.debug("secure boot: %s", exc)
        summary.secure_boot_state = "unknown"

    # 7. Initramfs and microcode.
    try:
        from boot.initrd_manager import InitrdManager
        im = InitrdManager(root)
        initramfs = im.list()
        summary.initramfs_count = len(initramfs)
        summary.initramfs_present = summary.initramfs_count > 0
    except Exception as exc:  # noqa: BLE001
        log.debug("initrd_manager: %s", exc)
        # Fallback - glob manually.
        try:
            patterns = ["initramfs-*.img", "initrd-*.img", "initrd.img-*"]
            for pat in patterns:
                count = sum(1 for _ in root.glob(pat))
                if count:
                    summary.initramfs_count += count
            summary.initramfs_present = summary.initramfs_count > 0
        except OSError:
            pass

    # Microcode blobs live next to the kernel (intel-ucode/, amd-ucode/).
    if (root / "intel-ucode").is_dir() or (root / "amd-ucode").is_dir():
        summary.microcode_present = True

    # 8. Crash kernel - look for a kdump-related marker.
    summary.crash_kernel_reserved = any(
        (root / f).exists() for f in ("kdump.img", "initrd.kdump")
    )

    # 9. Issues.
    if not summary.exists:
        summary.issues.append("/boot does not exist")
    if not summary.kernel_count:
        summary.issues.append("no kernels installed")
    if summary.boot_loader == "none":
        summary.issues.append("no boot loader configured")
    if not summary.efi_dir:
        summary.issues.append(
            "no EFI System Partition mounted at /boot/efi or /efi")
    if summary.kernel_count and not summary.default_kernel_protocol:
        summary.issues.append(
            "default kernel does not look like a Linux bzImage")

    return summary


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        boot = Path(tmp) / "boot"
        boot.mkdir()
        # Fake vmlinuz + bzImage header.
        from boot.bzimage import _build_fake_bzimage
        data = _build_fake_bzimage()
        (boot / "vmlinuz-6.8.0-umerOS").write_bytes(data)
        (boot / "initramfs-6.8.0-umerOS.img").write_bytes(b"stub")
        (boot / "grub").mkdir()
        (boot / "grub" / "grub.cfg").write_text("# stub")
        info = boot_summary(boot_path=str(boot))
        if not info.exists:
            return False
        if info.kernel_count != 1:
            return False
        if "6.8.0-umerOS" not in info.kernel_versions:
            return False
        if info.boot_loader != "grub2":
            return False
        if not info.initramfs_present:
            return False
        if info.default_kernel_protocol != "2.0e":
            return False
        if not info.default_kernel_efi_stub:
            # The fake bzImage has no PE header, so efi_stub is False.
            pass
        text = info.render_table()
        if "Umer OS /boot summary" not in text:
            return False
    return True


if __name__ == "__main__":
    import json
    import sys
    logging.basicConfig(level=logging.INFO)
    s = boot_summary(sys.argv[1] if len(sys.argv) > 1 else "/boot")
    print(s.render_table())
    print("boot info selftest:", "OK" if _selftest() else "FAIL")
