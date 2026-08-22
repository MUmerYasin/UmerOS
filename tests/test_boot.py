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
Tests for the /boot filesystem modules.

Covers: kernel_image, grub_manager, systemd_boot, efi_system,
boot_params, microcode, boot_splash, crash_kernel, bootloader,
bzimage, efi_stub, cmdline, info, fhs, memtest, boot_log,
kernel_signing.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _load(mod_name: str):
    """Import a module by dotted name."""
    return importlib.import_module(mod_name)


def _has_selftest(mod_name: str) -> bool:
    mod = _load(mod_name)
    return hasattr(mod, "_selftest") and callable(mod._selftest)


# ---------------------------------------------------------------------------
# 1. kernel_image
# ---------------------------------------------------------------------------

class TestKernelImage:
    def test_imports(self):
        mod = _load("boot.kernel_image")
        assert hasattr(mod, "KernelImage")
        assert hasattr(mod, "KernelImageManager")

    def test_selftest(self):
        assert _has_selftest("boot.kernel_image")
        assert _load("boot.kernel_image")._selftest()

    def test_manager_init(self):
        from boot.kernel_image import KernelImageManager
        mgr = KernelImageManager(Path(tempfile.mkdtemp()))
        assert hasattr(mgr, "kernels")


# ---------------------------------------------------------------------------
# 2. grub_manager
# ---------------------------------------------------------------------------

class TestGrubManager:
    def test_imports(self):
        mod = _load("boot.grub_manager")
        assert hasattr(mod, "GrubManager")
        assert hasattr(mod, "GrubConfig")

    def test_selftest(self):
        assert _has_selftest("boot.grub_manager")
        assert _load("boot.grub_manager")._selftest()

    def test_manager_init(self):
        from boot.grub_manager import GrubManager
        mgr = GrubManager(Path(tempfile.mkdtemp()))
        assert hasattr(mgr, "read_grub_cfg")


# ---------------------------------------------------------------------------
# 3. systemd_boot
# ---------------------------------------------------------------------------

class TestSystemdBoot:
    def test_imports(self):
        mod = _load("boot.systemd_boot")
        assert hasattr(mod, "SystemdBootManager")
        assert hasattr(mod, "BootEntry")

    def test_selftest(self):
        assert _has_selftest("boot.systemd_boot")
        assert _load("boot.systemd_boot")._selftest()

    def test_manager_init(self):
        from boot.systemd_boot import SystemdBootManager
        mgr = SystemdBootManager(Path(tempfile.mkdtemp()))
        assert hasattr(mgr, "list_entries")


# ---------------------------------------------------------------------------
# 4. efi_system
# ---------------------------------------------------------------------------

class TestEFISystem:
    def test_imports(self):
        mod = _load("boot.efi_system")
        assert hasattr(mod, "EFISystemPartition")
        assert hasattr(mod, "NVRAMManager")
        assert hasattr(mod, "SecureBootManager")

    def test_selftest(self):
        assert _has_selftest("boot.efi_system")


# ---------------------------------------------------------------------------
# 5. boot_params
# ---------------------------------------------------------------------------

class TestBootParams:
    def test_imports(self):
        mod = _load("boot.boot_params")
        assert hasattr(mod, "KernelCommandLine")
        assert hasattr(mod, "SysctlManager")
        assert hasattr(mod, "BootParamsManager")

    def test_selftest(self):
        assert _has_selftest("boot.boot_params")
        assert _load("boot.boot_params")._selftest()

    def test_cmdline_parse(self):
        from boot.boot_params import KernelCommandLine
        cmd = KernelCommandLine()
        assert hasattr(cmd, "set_param")


# ---------------------------------------------------------------------------
# 6. microcode
# ---------------------------------------------------------------------------

class TestMicrocode:
    def test_imports(self):
        mod = _load("boot.microcode")
        assert hasattr(mod, "MicrocodeManager")
        assert hasattr(mod, "CPUVendor")
        assert hasattr(mod, "MicrocodeParser")

    def test_selftest(self):
        assert _has_selftest("boot.microcode")


# ---------------------------------------------------------------------------
# 7. boot_splash
# ---------------------------------------------------------------------------

class TestBootSplash:
    def test_imports(self):
        mod = _load("boot.boot_splash")
        assert hasattr(mod, "BootSplashManager")
        assert hasattr(mod, "SplashTechnology")
        assert hasattr(mod, "PlymouthManager")

    def test_selftest(self):
        assert _has_selftest("boot.boot_splash")


# ---------------------------------------------------------------------------
# 8. crash_kernel
# ---------------------------------------------------------------------------

class TestCrashKernel:
    def test_imports(self):
        mod = _load("boot.crash_kernel")
        assert hasattr(mod, "CrashKernelManager")
        assert hasattr(mod, "KdumpConfig")

    def test_selftest(self):
        assert _has_selftest("boot.crash_kernel")
        assert _load("boot.crash_kernel")._selftest()

    def test_manager_init(self):
        from boot.crash_kernel import CrashKernelManager
        mgr = CrashKernelManager(Path(tempfile.mkdtemp()))
        assert hasattr(mgr, "get_grub_config")


# ---------------------------------------------------------------------------
# 9. bootloader
# ---------------------------------------------------------------------------

class TestBootloader:
    def test_imports(self):
        mod = _load("boot.bootloader")
        assert callable(getattr(mod, "load_kernel", None))
        assert callable(getattr(mod, "verify_kernel", None))
        assert callable(getattr(mod, "show_banner", None))
        assert callable(getattr(mod, "show_legal_warning", None))
        assert callable(getattr(mod, "system_check", None))

    def test_selftest(self):
        assert _has_selftest("boot.bootloader")


# ---------------------------------------------------------------------------
# 10. bzimage
# ---------------------------------------------------------------------------

class TestBzImage:
    def test_imports(self):
        mod = _load("boot.bzimage")
        assert hasattr(mod, "BzImageHeader")
        assert hasattr(mod, "BzImageInspector")
        assert hasattr(mod, "BzImageType")
        assert hasattr(mod, "HDRS_MAGIC")

    def test_selftest(self):
        assert _has_selftest("boot.bzimage")
        assert _load("boot.bzimage")._selftest()

    def test_magic_constant(self):
        from boot.bzimage import HDRS_MAGIC
        assert isinstance(HDRS_MAGIC, int)


# ---------------------------------------------------------------------------
# 11. efi_stub
# ---------------------------------------------------------------------------

class TestEfiStub:
    def test_imports(self):
        mod = _load("boot.efi_stub")
        assert hasattr(mod, "EfiImage")
        assert hasattr(mod, "EfiImageType")
        assert hasattr(mod, "EfiStubInspector")
        assert hasattr(mod, "UKI_SECTIONS")
        assert hasattr(mod, "parse_efi_image")

    def test_selftest(self):
        assert _has_selftest("boot.efi_stub")
        assert _load("boot.efi_stub")._selftest()

    def test_uki_sections(self):
        from boot.efi_stub import UKI_SECTIONS
        assert isinstance(UKI_SECTIONS, set)
        assert ".linux" in UKI_SECTIONS


# ---------------------------------------------------------------------------
# 12. cmdline
# ---------------------------------------------------------------------------

class TestCmdline:
    def test_imports(self):
        mod = _load("boot.cmdline")
        assert hasattr(mod, "CmdParam")
        assert hasattr(mod, "CmdParamKind")
        assert hasattr(mod, "KNOWN_KEYS")
        assert hasattr(mod, "PRESETS")
        assert hasattr(mod, "parse_cmdline")
        assert hasattr(mod, "build_cmdline")
        assert hasattr(mod, "preset")
        assert hasattr(mod, "validate")

    def test_selftest(self):
        assert _has_selftest("boot.cmdline")
        assert _load("boot.cmdline")._selftest()

    def test_parse(self):
        from boot.cmdline import parse_cmdline
        result = parse_cmdline("root=/dev/sda1 quiet")
        assert hasattr(result, "params")

    def test_build(self):
        from boot.cmdline import build_cmdline, parse_cmdline
        parsed = parse_cmdline("root=/dev/sda1 quiet")
        line = build_cmdline(parsed)
        assert "root=/dev/sda1" in line
        assert "quiet" in line

    def test_preset(self):
        from boot.cmdline import preset, PRESETS
        for name in PRESETS:
            result = preset(name)
            assert isinstance(result, str)

    def test_validate(self):
        from boot.cmdline import validate
        issues = validate("root=/dev/sda1 ro")
        assert isinstance(issues, list)

    def test_known_keys(self):
        from boot.cmdline import KNOWN_KEYS
        assert isinstance(KNOWN_KEYS, set)
        assert "root" in KNOWN_KEYS


# ---------------------------------------------------------------------------
# 13. info
# ---------------------------------------------------------------------------

class TestInfo:
    def test_imports(self):
        mod = _load("boot.info")
        assert hasattr(mod, "BootSummary")
        assert hasattr(mod, "boot_summary")

    def test_selftest(self):
        assert _has_selftest("boot.info")
        assert _load("boot.info")._selftest()

    def test_summary(self):
        from boot.info import boot_summary
        s = boot_summary(boot_path="/boot")
        assert hasattr(s, "render_table")


# ---------------------------------------------------------------------------
# 14. fhs
# ---------------------------------------------------------------------------

class TestFHS:
    def test_imports(self):
        mod = _load("boot.fhs")
        assert hasattr(mod, "FHSBootAuditor")
        assert hasattr(mod, "FHSIssue")
        assert hasattr(mod, "FHSIssueSeverity")
        assert hasattr(mod, "FHSReport")

    def test_selftest(self):
        assert _has_selftest("boot.fhs")
        assert _load("boot.fhs")._selftest()

    def test_audit(self):
        from boot.fhs import FHSBootAuditor
        auditor = FHSBootAuditor(boot_dir="/boot")
        report = auditor.audit()
        assert hasattr(report, "ok")
        assert hasattr(report, "issues")

    def test_render(self):
        from boot.fhs import FHSBootAuditor
        auditor = FHSBootAuditor(boot_dir="/boot")
        report = auditor.audit()
        rendered = report.render()
        assert isinstance(rendered, str)


# ---------------------------------------------------------------------------
# 15. memtest (NEW)
# ---------------------------------------------------------------------------

class TestMemtest:
    def test_imports(self):
        mod = _load("boot.memtest")
        assert hasattr(mod, "MemtestDetector")
        assert hasattr(mod, "MemtestCommandBuilder")
        assert hasattr(mod, "MemtestResultParser")
        assert hasattr(mod, "MemtestManager")
        assert hasattr(mod, "MemtestVersion")
        assert hasattr(mod, "MemtestStatus")
        assert hasattr(mod, "MemtestTestType")
        assert hasattr(mod, "MemoryErrorType")
        assert hasattr(mod, "MemtestConfig")
        assert hasattr(mod, "MemtestResult")
        assert hasattr(mod, "MemoryError")
        assert hasattr(mod, "MemtestBinary")

    def test_selftest(self):
        assert _has_selftest("boot.memtest")
        assert _load("boot.memtest")._selftest()

    def test_detector(self):
        from boot.memtest import MemtestDetector
        d = MemtestDetector()
        assert hasattr(d, "detect")
        binaries = d.detect()
        assert isinstance(binaries, list)

    def test_command_builder_presets(self):
        from boot.memtest import MemtestCommandBuilder
        for preset_name in MemtestCommandBuilder.PRESETS:
            b = MemtestCommandBuilder.from_preset(preset_name)
            cmd = b.build_cmdline()
            assert isinstance(cmd, str)

    def test_result_parser_no_pass(self):
        from boot.memtest import MemtestResultParser
        import tempfile
        p = MemtestResultParser()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("")
            f.flush()
            result = p.parse_log(Path(f.name))
        assert result is not None
        assert hasattr(result, "status")

    def test_manager(self):
        from boot.memtest import MemtestManager
        m = MemtestManager()
        assert hasattr(m, "get_status")
        status = m.get_status()
        assert hasattr(status, "value")

    def test_config(self):
        from boot.memtest import MemtestConfig, MemtestTestType
        c = MemtestConfig(test_type=MemtestTestType.ALL)
        assert c.test_type == MemtestTestType.ALL

    def test_version_enum(self):
        from boot.memtest import MemtestVersion
        assert hasattr(MemtestVersion, "MEMTEST86_6")
        assert hasattr(MemtestVersion, "MEMTEST86_7")

    def test_status_enum(self):
        from boot.memtest import MemtestStatus
        assert hasattr(MemtestStatus, "NOT_CONFIGURED")
        assert hasattr(MemtestStatus, "RUNNING")
        assert hasattr(MemtestStatus, "COMPLETED")


# ---------------------------------------------------------------------------
# 16. boot_log (NEW)
# ---------------------------------------------------------------------------

class TestBootLog:
    def test_imports(self):
        mod = _load("boot.boot_log")
        assert hasattr(mod, "BootLogger")
        assert hasattr(mod, "BootAnalyzer")
        assert hasattr(mod, "BootEvent")
        assert hasattr(mod, "BootSession")
        assert hasattr(mod, "BootStats")
        assert hasattr(mod, "BootLogLevel")
        assert hasattr(mod, "BootPhase")
        assert hasattr(mod, "BootEventType")

    def test_selftest(self):
        assert _has_selftest("boot.boot_log")
        assert _load("boot.boot_log")._selftest()

    def test_logger(self):
        from boot.boot_log import BootLogger
        l = BootLogger()
        assert hasattr(l, "get_stats")
        stats = l.get_stats()
        assert hasattr(stats, "total_boots")

    def test_analyzer(self):
        from boot.boot_log import BootLogger, BootAnalyzer
        l = BootLogger()
        a = BootAnalyzer(l)
        assert hasattr(a, "get_failure_summary")
        summary = a.get_failure_summary()
        assert isinstance(summary, dict)

    def test_event(self):
        from boot.boot_log import BootEvent, BootLogLevel, BootEventType
        e = BootEvent(
            level=BootLogLevel.INFO,
            event_type=BootEventType.BOOT_START,
            message="test event",
        )
        assert e.level == BootLogLevel.INFO
        assert e.event_type == BootEventType.BOOT_START

    def test_session(self):
        from boot.boot_log import BootSession
        s = BootSession()
        assert hasattr(s, "boot_id")
        assert hasattr(s, "success")

    def test_stats(self):
        from boot.boot_log import BootStats
        s = BootStats()
        assert hasattr(s, "total_boots")
        assert hasattr(s, "as_dict")
        d = s.as_dict()
        assert isinstance(d, dict)

    def test_level_enum(self):
        from boot.boot_log import BootLogLevel
        assert hasattr(BootLogLevel, "DEBUG")
        assert hasattr(BootLogLevel, "INFO")
        assert hasattr(BootLogLevel, "WARNING")

    def test_phase_enum(self):
        from boot.boot_log import BootPhase
        assert hasattr(BootPhase, "FIRMWARE")
        assert hasattr(BootPhase, "BOOTLOADER")

    def test_event_type_enum(self):
        from boot.boot_log import BootEventType
        assert hasattr(BootEventType, "BOOT_START")
        assert hasattr(BootEventType, "BOOT_COMPLETE")


# ---------------------------------------------------------------------------
# 17. kernel_signing (NEW)
# ---------------------------------------------------------------------------

class TestKernelSigning:
    def test_imports(self):
        mod = _load("boot.kernel_signing")
        assert hasattr(mod, "SecureBootManager")
        assert hasattr(mod, "PEParser")
        assert hasattr(mod, "SignatureVerifier")
        assert hasattr(mod, "MOKManager")
        assert hasattr(mod, "SigningCommandBuilder")
        assert hasattr(mod, "SignatureStatus")
        assert hasattr(mod, "KeyType")
        assert hasattr(mod, "KeyAlgorithm")
        assert hasattr(mod, "SignatureFormat")
        assert hasattr(mod, "SigningKey")
        assert hasattr(mod, "Signature")
        assert hasattr(mod, "UKISection")
        assert hasattr(mod, "KernelSignatureInfo")
        assert hasattr(mod, "SigningConfig")

    def test_selftest(self):
        assert _has_selftest("boot.kernel_signing")
        assert _load("boot.kernel_signing")._selftest()

    def test_sb_manager(self):
        from boot.kernel_signing import SecureBootManager
        sb = SecureBootManager()
        assert hasattr(sb, "get_db_keys")
        assert hasattr(sb, "get_pk")
        assert hasattr(sb, "get_system_info")
        info = sb.get_system_info()
        assert isinstance(info, dict)

    def test_pe_parser(self):
        from boot.kernel_signing import PEParser
        p = PEParser()
        assert hasattr(p, "is_pe")
        assert hasattr(p, "detect_uki_sections")

    def test_verifier(self):
        from boot.kernel_signing import SignatureVerifier
        v = SignatureVerifier()
        assert hasattr(v, "verify")

    def test_mok_manager(self):
        from boot.kernel_signing import MOKManager
        m = MOKManager()
        assert hasattr(m, "list_keys")
        assert hasattr(m, "get_enrolled_keys")

    def test_command_builder(self):
        from boot.kernel_signing import SigningCommandBuilder
        b = SigningCommandBuilder()
        assert hasattr(b, "build_sign_command")

    def test_key_type_enum(self):
        from boot.kernel_signing import KeyType
        assert hasattr(KeyType, "PK")
        assert hasattr(KeyType, "KEK")
        assert hasattr(KeyType, "DB")

    def test_signature_status_enum(self):
        from boot.kernel_signing import SignatureStatus
        assert hasattr(SignatureStatus, "VALID")
        assert hasattr(SignatureStatus, "INVALID")

    def test_signing_config(self):
        from boot.kernel_signing import SigningConfig
        c = SigningConfig()
        assert hasattr(c, "as_dict")

    def test_signing_key(self):
        from boot.kernel_signing import SigningKey, KeyType, KeyAlgorithm
        k = SigningKey(
            key_type=KeyType.DB,
            algorithm=KeyAlgorithm.RSA_2048,
        )
        assert k.key_type == KeyType.DB

    def test_signature(self):
        from boot.kernel_signing import Signature, SignatureStatus
        s = Signature(status=SignatureStatus.VALID)
        assert s.status == SignatureStatus.VALID


# ---------------------------------------------------------------------------
# 18. Package-level imports
# ---------------------------------------------------------------------------

class TestPackageImports:
    def test_version(self):
        from boot import __version__
        assert __version__ == "2.0.0"

    def test_author(self):
        from boot import __author__
        assert "UmerOS" in __author__

    def test_all_exports(self):
        import boot
        assert "__version__" in boot.__all__
        assert "MemtestManager" in boot.__all__
        assert "BootLogger" in boot.__all__
        assert "SecureBootManager" in boot.__all__ or "KernelSecureBootManager" in boot.__all__
