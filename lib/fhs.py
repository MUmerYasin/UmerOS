"""
UmerOS TLDP/FHS /lib hierarchy manager
======================================

This module provides the top-level glue for the TLDP ``/lib`` rules:

* essential boot shared libraries such as ``libc.so.*`` and ``ld*``
* ``/lib/cpp`` as a reference to the C preprocessor
* ``/lib/modules/<kernel-version>`` plus depmod map files
* TLDP subsystem directories: ``iptables``, ``kbd``, ``oss``, ``security``
* architecture-dependent directories under ``/lib/<machine-architecture>``
* alternate-format directories such as ``/lib32`` and ``/lib64``

The lower-level managers in this package own the individual catalogues.
``LibHierarchyManager`` owns the cross-directory audit and bootstrap flow.
"""

from __future__ import annotations

import fnmatch
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

from .arch import ArchLibraryManager
from .dynamic_linker import LibQualifierManager
from .essential_libs import ESSENTIAL_LIBRARIES, EssentialLibraryManager
from .firmware import FirmwareManager
from .iptables_libs import IptablesLibraryManager
from .kbd import KbdManager
from .kernel_modules import DEFAULT_KERNEL_VERSION, KernelModuleManager
from .multiarch import MultiarchManager
from .oss import OssManager
from .security import PamLibraryManager

log = logging.getLogger("UmerOS.Lib.FHS")


TLDP_LIB_SOURCE = "https://tldp.org/LDP/Linux-Filesystem-Hierarchy/html/lib.html"

TLDP_MODULE_MAPS = (
    "modules.dep",
    "pcimap",
    "usbmap",
    "isapnpmap.dep",
)

TLDP_SUBSYSTEMS = {
    "modules": "Loadable kernel modules",
    "iptables": "iptables shared library files",
    "kbd": "console keymaps, fonts and translation tables",
    "oss": "Open Sound System files",
    "security": "PAM shared library files",
}

MODERN_LIB_SUBSYSTEMS = {
    "firmware": "kernel firmware blobs loaded at runtime",
}

DEFAULT_INSTALLED_SUBSYSTEMS = tuple(TLDP_SUBSYSTEMS.keys()) + tuple(
    MODERN_LIB_SUBSYSTEMS.keys()
)

BOOT_REQUIRED_PATTERNS = ("libc.so.*", "ld*")

# Libraries with these names are normally /usr-only or desktop/session stack
# dependencies.  The audit reports them as warnings because only the local boot
# graph can prove whether a given deployment really needs one in /lib.
USR_ONLY_LIBRARY_PREFIXES = (
    "libX",
    "libgtk",
    "libgdk",
    "libQt",
    "libwayland",
    "libEGL",
    "libGL",
    "libSDL",
    "libpulse",
)


class LibIssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class LibRequirement:
    """A TLDP/FHS requirement or optional directory rule."""

    key: str
    path: str
    description: str
    optional: bool = False
    source: str = TLDP_LIB_SOURCE

    def to_dict(self) -> Dict[str, object]:
        return {
            "key": self.key,
            "path": self.path,
            "description": self.description,
            "optional": self.optional,
            "source": self.source,
        }


@dataclass(frozen=True)
class LibAuditIssue:
    """One audit finding for the /lib hierarchy."""

    requirement: str
    severity: LibIssueSeverity
    message: str
    path: str = ""
    hint: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "requirement": self.requirement,
            "severity": self.severity.value,
            "message": self.message,
            "path": self.path,
            "hint": self.hint,
        }


@dataclass
class LibAuditReport:
    """Structured result returned by :meth:`LibHierarchyManager.audit`."""

    root: str
    lib_path: str
    requirements: List[LibRequirement] = field(default_factory=list)
    issues: List[LibAuditIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[LibAuditIssue]:
        return [i for i in self.issues if i.severity == LibIssueSeverity.ERROR]

    @property
    def warnings(self) -> List[LibAuditIssue]:
        return [i for i in self.issues if i.severity == LibIssueSeverity.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> Dict[str, object]:
        return {
            "root": self.root,
            "lib_path": self.lib_path,
            "ok": self.ok,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "requirements": [r.to_dict() for r in self.requirements],
            "issues": [i.to_dict() for i in self.issues],
        }


class LibHierarchyManager:
    """
    Audit and bootstrap a TLDP/FHS-style ``/lib`` hierarchy.

    ``root`` may point at a staging tree, making this safe to use from tests
    and installers before the real root filesystem exists.
    """

    def __init__(
        self,
        root: str = "/",
        *,
        kernel_version: str = DEFAULT_KERNEL_VERSION,
        cpp_target: str = "/usr/bin/cpp",
        installed_subsystems: Optional[Iterable[str]] = None,
        alternate_qualifiers: Sequence[str] = ("32", "64"),
    ) -> None:
        self.root = Path(root)
        self.lib_path = self.root / "lib"
        self.kernel_version = kernel_version
        self.cpp_target = cpp_target
        if installed_subsystems is None:
            installed_subsystems = DEFAULT_INSTALLED_SUBSYSTEMS
        self.installed_subsystems: Set[str] = set(installed_subsystems)
        self.alternate_qualifiers = tuple(alternate_qualifiers)
        self.essential_libraries = EssentialLibraryManager()
        self.arch_manager = ArchLibraryManager(lib_path=str(self.lib_path))
        self.multiarch_manager = MultiarchManager(root=str(self.root))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def requirements(self) -> List[LibRequirement]:
        """Return the TLDP/FHS rules that this manager audits."""
        reqs = [
            LibRequirement("lib-root", "/lib", "root essential library directory"),
            LibRequirement(
                "essential-libc",
                "/lib/libc.so.*",
                "at least one dynamically linked C library reference",
            ),
            LibRequirement(
                "essential-loader",
                "/lib/ld*",
                "at least one execution-time linker/loader reference",
            ),
            LibRequirement(
                "cpp-reference",
                "/lib/cpp",
                "reference to the installed C preprocessor",
                optional=False,
            ),
            LibRequirement(
                "machine-architecture",
                f"/lib/{self.native_arch_triplet()}",
                "platform-dependent shared library directory",
                optional=True,
            ),
        ]
        for name, description in TLDP_SUBSYSTEMS.items():
            reqs.append(
                LibRequirement(
                    f"subsystem-{name}",
                    f"/lib/{name}",
                    description,
                    optional=name != "modules",
                )
            )
        for name, description in MODERN_LIB_SUBSYSTEMS.items():
            reqs.append(
                LibRequirement(
                    f"subsystem-{name}",
                    f"/lib/{name}",
                    description,
                    optional=True,
                    source="modern /lib convention",
                )
            )
        for qualifier in self.alternate_qualifiers:
            reqs.append(
                LibRequirement(
                    f"lib{qualifier}",
                    f"/lib{qualifier}",
                    "alternate-format essential shared libraries",
                    optional=True,
                )
            )
        return reqs

    def audit(self) -> LibAuditReport:
        """Audit the current tree and return structured findings."""
        report = LibAuditReport(
            root=str(self.root),
            lib_path=str(self.lib_path),
            requirements=self.requirements(),
        )
        if not (self.lib_path.exists() or self.lib_path.is_symlink()):
            report.issues.append(
                LibAuditIssue(
                    "lib-root",
                    LibIssueSeverity.ERROR,
                    "/lib is missing",
                    str(self.lib_path),
                    "Create the root /lib directory before boot userspace starts.",
                )
            )
            return report
        if not (self.lib_path.is_dir() or self.lib_path.is_symlink()):
            report.issues.append(
                LibAuditIssue(
                    "lib-root",
                    LibIssueSeverity.ERROR,
                    "/lib exists but is not a directory or symlink",
                    str(self.lib_path),
                )
            )

        self._audit_required_library_patterns(report, self.lib_path, "native")
        self._audit_cpp_reference(report)
        self._audit_boot_only_policy(report)
        self._audit_subsystems(report)
        self._audit_modules(report)
        self._audit_architecture_dir(report)
        self._audit_alternate_qualifiers(report)
        return report

    def bootstrap(
        self,
        *,
        materialise_stubs: bool = True,
        prefer_symlink: bool = True,
        write_manifest: bool = True,
    ) -> Dict[str, int]:
        """
        Materialize a TLDP/FHS-like /lib hierarchy under ``root``.

        Returns counters for created directories, stubs and metadata files.
        Existing files are preserved.
        """
        stats = {
            "directories": 0,
            "essential_libraries": 0,
            "subsystem_stubs": 0,
            "module_maps": 0,
            "cpp_references": 0,
            "manifests": 0,
        }
        stats["directories"] += self._ensure_dir(self.lib_path)
        stats["directories"] += self._ensure_dir(self.lib_path / self.native_arch_triplet())

        if materialise_stubs:
            stats["essential_libraries"] += self.materialise_essential_library_stubs(
                self.lib_path,
                prefer_symlink=prefer_symlink,
            )

        cpp = self.ensure_cpp_reference(prefer_symlink=prefer_symlink)
        if cpp.exists() or cpp.is_symlink():
            stats["cpp_references"] += 1

        if "modules" in self.installed_subsystems:
            stats["directories"] += self._ensure_dir(
                self.lib_path / "modules" / self.kernel_version / "kernel"
            )
            module_manager = KernelModuleManager(
                lib_path=str(self.lib_path),
                kernel_version=self.kernel_version,
                source_root=str(self.root / "usr" / "src"),
            )
            stats["module_maps"] += len(module_manager.depmod())
            module_manager.ensure_build_symlink()

        if "iptables" in self.installed_subsystems:
            stats["directories"] += self._ensure_dir(self.lib_path / "iptables")
            if materialise_stubs:
                stats["subsystem_stubs"] += IptablesLibraryManager(
                    lib_path=str(self.lib_path),
                    iptables_path=str(self.lib_path / "iptables"),
                ).materialise_stubs(root=str(self.root))

        if "kbd" in self.installed_subsystems:
            stats["directories"] += self._ensure_dir(self.lib_path / "kbd")
            if materialise_stubs:
                stats["subsystem_stubs"] += KbdManager(
                    lib_path=str(self.lib_path),
                    kbd_path=str(self.lib_path / "kbd"),
                ).materialise_stubs(root=str(self.root))

        if "oss" in self.installed_subsystems:
            stats["directories"] += self._ensure_dir(self.lib_path / "oss")
            if materialise_stubs:
                stats["subsystem_stubs"] += OssManager(
                    lib_path=str(self.lib_path),
                    oss_path=str(self.lib_path / "oss"),
                ).materialise_stubs(root=str(self.root))

        if "security" in self.installed_subsystems:
            stats["directories"] += self._ensure_dir(self.lib_path / "security")
            if materialise_stubs:
                stats["subsystem_stubs"] += PamLibraryManager(
                    lib_path=str(self.lib_path),
                    security_path=str(self.lib_path / "security"),
                ).materialise_stubs(root=str(self.root))

        if "firmware" in self.installed_subsystems:
            stats["directories"] += self._ensure_dir(self.lib_path / "firmware")
            if materialise_stubs:
                stats["subsystem_stubs"] += FirmwareManager(
                    lib_path=str(self.lib_path),
                    firmware_path=str(self.lib_path / "firmware"),
                ).materialise_stubs(root=str(self.root))

        for qualifier in self.alternate_qualifiers:
            alt_dir = self.root / f"lib{qualifier}"
            stats["directories"] += self._ensure_dir(alt_dir)
            if materialise_stubs:
                stats["essential_libraries"] += self.materialise_essential_library_stubs(
                    alt_dir,
                    prefer_symlink=prefer_symlink,
                )

        if write_manifest:
            self.write_manifest()
            stats["manifests"] += 1

        return stats

    def materialise_essential_library_stubs(
        self,
        directory: Path,
        *,
        prefer_symlink: bool = True,
    ) -> int:
        """Create small ELF-like files for the boot-essential library set."""
        directory.mkdir(parents=True, exist_ok=True)
        written = 0
        for lib in ESSENTIAL_LIBRARIES:
            target = directory / lib.name
            if target.exists() or target.is_symlink():
                continue
            if lib.symlink_target:
                if prefer_symlink:
                    try:
                        target.symlink_to(lib.symlink_target)
                        written += 1
                        continue
                    except (OSError, NotImplementedError) as e:
                        log.warning("Could not create library symlink %s: %s", target, e)
                target.write_text(
                    f"UmerOS library reference\nName: {lib.name}\nTarget: {lib.symlink_target}\n",
                    encoding="utf-8",
                )
            else:
                target.write_bytes(
                    b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
                    + (
                        f"UmerOS essential library stub\n"
                        f"Name: {lib.name}\n"
                        f"Version: {lib.version}\n"
                        f"Description: {lib.description}\n"
                    ).encode("utf-8")
                )
            written += 1
        return written

    def ensure_cpp_reference(self, *, prefer_symlink: bool = True) -> Path:
        """Ensure the native ``/lib/cpp`` entry references ``cpp_target``."""
        return LibQualifierManager(lib_path=str(self.lib_path)).ensure_cpp_reference(
            self.cpp_target,
            prefer_symlink=prefer_symlink,
        )

    def is_cpp_reference(self) -> bool:
        """Return True if ``/lib/cpp`` references ``cpp_target``."""
        return LibQualifierManager(lib_path=str(self.lib_path)).is_cpp_reference(
            self.cpp_target
        )

    def native_arch_triplet(self) -> str:
        return self.arch_manager.detect_native()

    def write_manifest(self, path: Optional[str] = None) -> Path:
        """Write a compact JSON manifest documenting the current audit state."""
        manifest_path = Path(path) if path else self.lib_path / ".umeros-lib-manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "source": TLDP_LIB_SOURCE,
            "kernel_version": self.kernel_version,
            "cpp_target": self.cpp_target,
            "installed_subsystems": sorted(self.installed_subsystems),
            "audit": self.audit().to_dict(),
        }
        manifest_path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest_path

    def get_summary(self) -> Dict[str, object]:
        report = self.audit()
        return {
            "root": str(self.root),
            "lib_path": str(self.lib_path),
            "ok": report.ok,
            "errors": len(report.errors),
            "warnings": len(report.warnings),
            "native_arch": self.native_arch_triplet(),
            "installed_subsystems": sorted(self.installed_subsystems),
            "alternate_qualifiers": list(self.alternate_qualifiers),
        }

    # ------------------------------------------------------------------
    # Audit helpers
    # ------------------------------------------------------------------

    def _audit_required_library_patterns(
        self,
        report: LibAuditReport,
        directory: Path,
        label: str,
    ) -> None:
        names = self._names_in(directory)
        for pattern in BOOT_REQUIRED_PATTERNS:
            if not any(fnmatch.fnmatchcase(name, pattern) for name in names):
                report.issues.append(
                    LibAuditIssue(
                        f"{label}:{pattern}",
                        LibIssueSeverity.ERROR,
                        f"{directory.name or directory} lacks required {pattern}",
                        str(directory / pattern),
                        "Create an essential shared library file or symlink matching this pattern.",
                    )
                )

    def _audit_cpp_reference(self, report: LibAuditReport) -> None:
        if not self.is_cpp_reference():
            report.issues.append(
                LibAuditIssue(
                    "cpp-reference",
                    LibIssueSeverity.ERROR,
                    "/lib/cpp does not reference the configured C preprocessor",
                    str(self.lib_path / "cpp"),
                    f"Point it at {self.cpp_target}.",
                )
            )

    def _audit_boot_only_policy(self, report: LibAuditReport) -> None:
        for entry in self._top_level_entries(self.lib_path):
            name = entry.name
            if not (".so" in name and (entry.is_file() or entry.is_symlink())):
                continue
            if name.startswith(USR_ONLY_LIBRARY_PREFIXES):
                report.issues.append(
                    LibAuditIssue(
                        "boot-only-shared-libraries",
                        LibIssueSeverity.WARNING,
                        f"{name} looks like a /usr-only library in /lib",
                        str(entry),
                        "Keep only libraries needed by /bin and /sbin in /lib.",
                    )
                )

    def _audit_subsystems(self, report: LibAuditReport) -> None:
        descriptions = {**TLDP_SUBSYSTEMS, **MODERN_LIB_SUBSYSTEMS}
        for subsystem in sorted(self.installed_subsystems):
            if subsystem not in descriptions:
                continue
            path = self.lib_path / subsystem
            if not (path.exists() or path.is_symlink()):
                severity = (
                    LibIssueSeverity.ERROR
                    if subsystem == "modules"
                    else LibIssueSeverity.WARNING
                )
                report.issues.append(
                    LibAuditIssue(
                        f"subsystem-{subsystem}",
                        severity,
                        f"/lib/{subsystem} is missing",
                        str(path),
                        f"Create this directory when the {subsystem} subsystem is installed.",
                    )
                )

    def _audit_modules(self, report: LibAuditReport) -> None:
        if "modules" not in self.installed_subsystems:
            return
        version_dir = self.lib_path / "modules" / self.kernel_version
        if not version_dir.exists():
            report.issues.append(
                LibAuditIssue(
                    "modules-version",
                    LibIssueSeverity.ERROR,
                    f"/lib/modules/{self.kernel_version} is missing",
                    str(version_dir),
                    "Create the kernel-version module directory.",
                )
            )
            return
        for filename in TLDP_MODULE_MAPS:
            path = version_dir / filename
            if not path.exists():
                report.issues.append(
                    LibAuditIssue(
                        f"module-map-{filename}",
                        LibIssueSeverity.ERROR,
                        f"{filename} is missing for {self.kernel_version}",
                        str(path),
                        "Run the UmerOS depmod implementation.",
                    )
                )
        build_ref = version_dir / "kernel" / "build"
        if not self._path_references(build_ref, str(self.root / "usr" / "src" / self.kernel_version)):
            report.issues.append(
                LibAuditIssue(
                    "modules-build-reference",
                    LibIssueSeverity.WARNING,
                    "kernel/build does not reference the kernel source tree",
                    str(build_ref),
                    f"Reference {self.root / 'usr' / 'src' / self.kernel_version}.",
                )
            )

    def _audit_architecture_dir(self, report: LibAuditReport) -> None:
        arch_dir = self.lib_path / self.native_arch_triplet()
        if not arch_dir.exists():
            report.issues.append(
                LibAuditIssue(
                    "machine-architecture",
                    LibIssueSeverity.WARNING,
                    f"{arch_dir.name} architecture directory is missing",
                    str(arch_dir),
                    "Create the native architecture directory for platform-dependent libraries.",
                )
            )

    def _audit_alternate_qualifiers(self, report: LibAuditReport) -> None:
        for qualifier in self.alternate_qualifiers:
            alt_dir = self.root / f"lib{qualifier}"
            if not (alt_dir.exists() or alt_dir.is_symlink()):
                continue
            self._audit_required_library_patterns(report, alt_dir, f"lib{qualifier}")

    # ------------------------------------------------------------------
    # Filesystem helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_dir(path: Path) -> int:
        if path.exists():
            return 0
        path.mkdir(parents=True, exist_ok=True)
        return 1

    @staticmethod
    def _names_in(directory: Path) -> List[str]:
        try:
            return [
                entry.name
                for entry in directory.iterdir()
                if entry.is_file() or entry.is_symlink()
            ]
        except OSError:
            return []

    @staticmethod
    def _top_level_entries(directory: Path) -> List[Path]:
        try:
            return list(directory.iterdir())
        except OSError:
            return []

    @staticmethod
    def _path_references(path: Path, target: str) -> bool:
        if not (path.exists() or path.is_symlink()):
            return False
        if path.is_symlink():
            try:
                return str(path.readlink()) == target
            except OSError:
                return False
        if path.is_file():
            try:
                return target in path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return False
        return False


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = LibHierarchyManager(root=tmpdir)
        summary = mgr.get_summary()
        assert "ok" in summary, "summary should have ok"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
