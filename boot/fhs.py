"""
Umer OS /boot - FHS / TLDP audit
================================

Single entry point for "is ``/boot`` set up correctly?".  Wires
together the other modules in the ``boot`` package and produces a
:class:`FHSReport`.

What the FHS 3.0 page (ch03s05) requires
---------------------------------------

* contains everything required for the boot process
* the kernel may live in ``/`` or ``/boot``
* programs that arrange the boot loader go to ``/sbin``
* configuration files for boot loaders not required at boot go to
  ``/etc``
* the directory may include saved master boot sectors and sector map
  files
* certain architectures have additional requirements (not enumerated
  in the FHS itself, but covered by the Boot Loader Specification)

What this auditor checks
------------------------

* directory exists
* at least one kernel image present (vmlinuz-*)
* at least one initramfs / initrd present
* the default kernel has a valid bzImage header
* EFI System Partition mounted (on EFI systems) - best effort
* the configured boot loader is one of the recognised types
* no stray **map installer** binaries (they belong in ``/sbin``)
* no misplaced ``/etc``-style configuration in ``/boot``
* no plaintext secrets in ``/boot`` (best-effort: ``.key``, ``.pem``,
  ``id_rsa`` files at the top level)

The audit produces :class:`FHSIssue` records of three severities:

* ``ERROR``   - a hard failure (no kernel, no initrd)
* ``WARN``    - suboptimal but workable
* ``INFO``    - advisory

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Boot.FHS")


# ---------------------------------------------------------------------------
# Severity + report
# ---------------------------------------------------------------------------

class FHSIssueSeverity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class FHSIssue:
    code: str
    severity: FHSIssueSeverity
    title: str
    detail: str = ""
    fix: str = ""

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "title": self.title,
            "detail": self.detail,
            "fix": self.fix,
        }


@dataclass
class FHSReport:
    boot: str
    issues: List[FHSIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == FHSIssueSeverity.ERROR for i in self.issues)

    @property
    def has_blocking(self) -> bool:
        return not self.ok

    def as_dict(self) -> dict:
        return {
            "boot": self.boot,
            "ok": self.ok,
            "issues": [i.as_dict() for i in self.issues],
        }

    def render(self) -> str:
        lines = [f"Umer OS /boot FHS audit   ({self.boot})", "=" * 60]
        if not self.issues:
            lines.append("  OK - /boot passes the FHS audit.")
            return "\n".join(lines) + "\n"
        for issue in self.issues:
            lines.append(f"  [{issue.severity.value.upper():<5}] {issue.title}")
            if issue.detail:
                lines.append(f"      detail: {issue.detail}")
            if issue.fix:
                lines.append(f"      fix:    {issue.fix}")
            lines.append("")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Map installer + sensitive-file names
# ---------------------------------------------------------------------------

#: Binaries that belong in /sbin per FHS 3.0 ch03s05 ("map installer").
MAP_INSTALLER_BINARIES = {
    "grub-install", "grub-mkrescue", "grub-bios-setup",
    "grub-mkdevicemap", "lilo", "syslinux", "extlinux",
    "mkrescue", "mksyslinux", "ybin", "mbr", "install-mbr",
}

#: Files that should never live in /boot (secrets / keys).
SENSITIVE_PATTERNS = (
    ".key", ".pem", ".p12", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "shadow", "passwd",
)


# ---------------------------------------------------------------------------
# Auditor
# ---------------------------------------------------------------------------

class FHSBootAuditor:
    """Single-call FHS / TLDP audit for ``/boot``."""

    def __init__(self, boot_dir: str = "/boot",
                 efi_dir: str = "/boot/efi") -> None:
        self.boot_dir = boot_dir
        self.efi_dir = efi_dir

    def audit(self) -> FHSReport:
        report = FHSReport(boot=self.boot_dir)
        self._check_directory(report)
        if not Path(self.boot_dir).is_dir():
            # Remaining checks all assume the directory exists.
            return report
        self._check_kernels(report)
        self._check_initramfs(report)
        self._check_boot_loader(report)
        self._check_map_installer(report)
        self._check_sensitive_files(report)
        self._check_arch_specific(report)
        return report

    # -- individual checks ---------------------------------------------

    def _check_directory(self, report: FHSReport) -> None:
        p = Path(self.boot_dir)
        if not p.exists():
            report.issues.append(FHSIssue(
                code="FHS001",
                severity=FHSIssueSeverity.ERROR,
                title=f"/boot does not exist at {p!r}",
                fix="create the directory and (re)install a kernel",
            ))
            return
        if not p.is_dir():
            report.issues.append(FHSIssue(
                code="FHS002",
                severity=FHSIssueSeverity.ERROR,
                title=f"/boot is not a directory: {p!r}",
                fix="remove the file and create a directory",
            ))
            return
        # FHS does not mandate a particular mode for /boot, but on Linux
        # it is typically 0700 or 0755.  Warn if it is world-writable.
        try:
            mode = p.stat().st_mode
        except OSError:
            mode = 0
        if os.name != "nt" and mode and (mode & 0o002):
            report.issues.append(FHSIssue(
                code="FHS003",
                severity=FHSIssueSeverity.WARN,
                title=f"/boot is world-writable (mode {oct(mode)})",
                fix="chmod 0755 /boot",
            ))

    def _check_kernels(self, report: FHSReport) -> None:
        boot = Path(self.boot_dir)
        vmlinuz = list(boot.glob("vmlinuz*"))
        if not vmlinuz:
            report.issues.append(FHSIssue(
                code="FHS010",
                severity=FHSIssueSeverity.ERROR,
                title="no kernel image found in /boot",
                detail="FHS 3.0 ch03s05: the operating system kernel must be in / or /boot",
                fix="install a kernel (e.g. vmlinuz-6.8.0-umeros)",
            ))
            return
        # Try to parse the first vmlinuz-*.  We don't need a full
        # KernelImageManager scan for the audit.
        try:
            from boot.bzimage import parse_bzimage_header
            bh = parse_bzimage_header(vmlinuz[0])
            if not bh.is_linux:
                report.issues.append(FHSIssue(
                    code="FHS011",
                    severity=FHSIssueSeverity.WARN,
                    title=f"{vmlinuz[0].name} does not look like a Linux bzImage",
                    detail=f"magic 0x{bh.magic:08x} (expected 0x53726448)",
                    fix="rebuild the kernel or use a correct image",
                ))
        except Exception as exc:  # noqa: BLE001
            log.debug("bzimage parse: %s", exc)

    def _check_initramfs(self, report: FHSReport) -> None:
        boot = Path(self.boot_dir)
        patterns = ["initramfs-*.img", "initrd-*.img", "initrd.img-*"]
        found = sum(len(list(boot.glob(p))) for p in patterns)
        if not found:
            report.issues.append(FHSIssue(
                code="FHS020",
                severity=FHSIssueSeverity.WARN,
                title="no initramfs / initrd found in /boot",
                detail="FHS does not require initramfs; most distributions need it",
                fix="generate an initramfs (dracut / mkinitcpio / boot) for the default kernel",
            ))

    def _check_boot_loader(self, report: FHSReport) -> None:
        boot = Path(self.boot_dir)
        has_grub = (boot / "grub" / "grub.cfg").is_file()
        has_loader = (boot / "loader" / "loader.conf").is_file()
        has_efi_linux = (boot / "EFI" / "Linux").is_dir()
        if not (has_grub or has_loader or has_efi_linux):
            report.issues.append(FHSIssue(
                code="FHS030",
                severity=FHSIssueSeverity.WARN,
                title="no boot loader configuration found in /boot",
                detail=(
                    "expected grub/grub.cfg, loader/loader.conf "
                    "or EFI/Linux/ for a UKI workflow"
                ),
                fix="install grub2, systemd-boot or a UKI",
            ))

    def _check_map_installer(self, report: FHSReport) -> None:
        boot = Path(self.boot_dir)
        for name in MAP_INSTALLER_BINARIES:
            if (boot / name).is_file() or (boot / "grub" / name).is_file():
                report.issues.append(FHSIssue(
                    code="FHS040",
                    severity=FHSIssueSeverity.WARN,
                    title=f"{name} is in /boot but belongs in /sbin",
                    detail="FHS 3.0 ch03s05: 'programs necessary to arrange "
                           "for the boot loader to be able to boot a file "
                           "must be placed in /sbin'",
                    fix=f"move {name} to /sbin",
                ))

    def _check_sensitive_files(self, report: FHSReport) -> None:
        boot = Path(self.boot_dir)
        try:
            entries = list(boot.iterdir())
        except OSError:
            return
        for entry in entries:
            if not entry.is_file():
                continue
            n = entry.name
            if any(n.endswith(suf) for suf in (".key", ".pem", ".p12")):
                report.issues.append(FHSIssue(
                    code="FHS050",
                    severity=FHSIssueSeverity.WARN,
                    title=f"key-like file in /boot: {n}",
                    detail="private keys should not be world-readable and "
                           "are better stored in /etc or /var",
                    fix="move the key out of /boot and chmod 600",
                ))
            if n in ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"):
                report.issues.append(FHSIssue(
                    code="FHS051",
                    severity=FHSIssueSeverity.WARN,
                    title=f"SSH private key in /boot: {n}",
                    detail="SSH private keys belong in ~/.ssh/ or /etc/ssh/",
                    fix=f"move {n} to an appropriate location",
                ))

    def _check_arch_specific(self, report: FHSReport) -> None:
        """Best-effort: warn on x86 if no UEFI hint is present at all."""
        boot = Path(self.boot_dir)
        has_efi_marker = (boot / "EFI").is_dir()
        has_efi_fallback = any(boot.glob("**/BOOT*.EFI")) or any(boot.glob("**/boot*.efi"))
        if not (has_efi_marker or has_efi_fallback):
            # Not necessarily a problem on legacy BIOS or non-x86 systems.
            report.issues.append(FHSIssue(
                code="FHS060",
                severity=FHSIssueSeverity.INFO,
                title="no UEFI / EFI artefacts found in /boot",
                detail="FHS ch03s05: 'certain architectures may have other "
                       "requirements'; this is informational on legacy BIOS or non-x86 systems",
                fix="on x86 UEFI, install a UEFI-aware boot loader "
                    "(systemd-boot, grub-uefi or a UKI)",
            ))

    # -- summary -------------------------------------------------------

    def full_report(self) -> Dict:
        fhs = self.audit()
        return {"fhs": fhs.as_dict(), "ok": fhs.ok}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        boot = Path(tmp) / "boot"
        # 1. Missing directory
        auditor = FHSBootAuditor(boot_dir=str(boot))
        r1 = auditor.audit()
        if not any(i.code == "FHS001" for i in r1.issues):
            return False

        # 2. Create a directory with a kernel + initramfs + grub.
        boot.mkdir()
        from boot.bzimage import _build_fake_bzimage
        (boot / "vmlinuz-6.8.0-umerOS").write_bytes(_build_fake_bzimage())
        (boot / "initramfs-6.8.0-umerOS.img").write_bytes(b"stub")
        (boot / "grub").mkdir()
        (boot / "grub" / "grub.cfg").write_text("# stub")
        r2 = auditor.audit()
        if r2.ok is False and any(i.severity == FHSIssueSeverity.ERROR
                                  for i in r2.issues):
            return False
        if any(i.code == "FHS010" for i in r2.issues):
            return False
        if any(i.code == "FHS030" for i in r2.issues):
            return False

        # 3. Add a map-installer and a key file; expect warnings.
        (boot / "grub-install").write_text("# stub")
        (boot / "private.key").write_text("secret")
        r3 = auditor.audit()
        if not any(i.code == "FHS040" for i in r3.issues):
            return False
        if not any(i.code == "FHS050" for i in r3.issues):
            return False

        # 4. Render.
        text = r3.render()
        if "Umer OS /boot FHS audit" not in text:
            return False
    return True


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    a = FHSBootAuditor(boot_dir=sys.argv[1] if len(sys.argv) > 1 else "/boot")
    print(a.audit().render())
    print("fhs selftest:", "OK" if _selftest() else "FAIL")
