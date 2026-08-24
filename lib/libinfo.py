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
Umer OS /lib quick summary
==========================
A one-shot summary of the entire ``/lib`` state, in the spirit of
``pydoc`` or ``system-info`` - small enough to drop into a kernel
boot log or a CI report.

The summary aggregates information from the other modules in the
``lib`` package so callers do not have to spin up a full
``LibHierarchyManager`` to get the headline numbers:

* count of essential libraries (libc, ld, libm, libpthread, ...)
* count of modules and which kernel versions are present
* count of iptables / kbd / oss / security / firmware subsystems
* state of ``/lib/cpp`` (TLDP: must be a symlink or a reference)
* ld.so.cache existence + age
* presence of ``/lib<qual>`` (32/64/x32) variants
* ``kernel/build`` symlink health

Usage::

    from lib.libinfo import lib_summary
    info = lib_summary(lib_path="/lib")
    print(info.render_table())

The module is dependency-free on the rest of the package at import
time; the underlying managers are only loaded when :func:`lib_summary`
is called.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Lib.Info")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class LibSummary:
    """A flat summary of the /lib hierarchy.

    Every field is a string, number or small list so the result is
    JSON-serialisable out of the box.
    """

    lib_path: str
    exists: bool
    total_files: int = 0
    total_dirs: int = 0
    total_symlinks: int = 0
    total_bytes: int = 0
    essential_libraries: int = 0
    essential_required_present: int = 0
    essential_required_total: int = 0
    kernel_versions: List[str] = field(default_factory=list)
    module_files: int = 0
    isapnpmap_present: bool = False
    pcimap_present: bool = False
    usbmap_present: bool = False
    kernel_build_link_ok: bool = False
    iptables_dir: bool = False
    kbd_dir: bool = False
    oss_dir: bool = False
    security_dir: bool = False
    firmware_dir: bool = False
    cpp_reference_ok: bool = False
    cpp_target: str = ""
    ld_so_conf_exists: bool = False
    ld_so_cache_exists: bool = False
    ld_so_cache_age_seconds: float = -1.0
    alternate_qualifiers: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    # -- rendering -------------------------------------------------------

    def render_table(self) -> str:
        """Return a human-readable, single-section summary table."""
        lines: List[str] = []
        lines.append(f"Umer OS /lib summary   ({self.lib_path})")
        lines.append("=" * 60)
        if not self.exists:
            lines.append(f"  ! directory missing: {self.lib_path}")
            for issue in self.issues:
                lines.append(f"  - {issue}")
            return "\n".join(lines) + "\n"
        lines.append(f"  files:           {self.total_files}")
        lines.append(f"  directories:     {self.total_dirs}")
        lines.append(f"  symlinks:        {self.total_symlinks}")
        lines.append(f"  total bytes:     {self.total_bytes}")
        lines.append("")
        lines.append(
            f"  essential libs:  {self.essential_libraries} "
            f"(required present: {self.essential_required_present} / "
            f"{self.essential_required_total})"
        )
        lines.append(
            f"  kernel modules:  {len(self.kernel_versions)} kernel(s), "
            f"{self.module_files} module files"
        )
        for ver in self.kernel_versions:
            extras = []
            if self.isapnpmap_present: extras.append("isapnp")
            if self.pcimap_present:    extras.append("pci")
            if self.usbmap_present:    extras.append("usb")
            build = "build-link-ok" if self.kernel_build_link_ok else "build-link-BROKEN"
            lines.append(f"    - {ver}  [{', '.join(extras)}]  ({build})")
        lines.append("")
        lines.append(f"  /lib/cpp ref:    {'OK' if self.cpp_reference_ok else 'MISSING'}"
                     + (f"  -> {self.cpp_target}" if self.cpp_target else ""))
        lines.append(f"  /etc/ld.so.conf: {'present' if self.ld_so_conf_exists else 'MISSING'}")
        if self.ld_so_cache_exists:
            age = self.ld_so_cache_age_seconds
            lines.append(f"  /etc/ld.so.cache: present (age {age:.1f}s)")
        else:
            lines.append("  /etc/ld.so.cache: MISSING  (run ldconfig)")
        lines.append("")
        subs = []
        if self.iptables_dir: subs.append("iptables")
        if self.kbd_dir:      subs.append("kbd")
        if self.oss_dir:      subs.append("oss")
        if self.security_dir: subs.append("security")
        if self.firmware_dir: subs.append("firmware")
        lines.append(f"  subsystems:      {', '.join(subs) or '(none)'}")
        if self.alternate_qualifiers:
            lines.append(f"  alternate qual:  {', '.join(self.alternate_qualifiers)}")
        else:
            lines.append("  alternate qual:  (none - no /lib32, /lib64 etc.)")
        if self.issues:
            lines.append("")
            lines.append("  issues:")
            for issue in self.issues:
                lines.append(f"    - {issue}")
        return "\n".join(lines) + "\n"

    def as_dict(self) -> dict:
        return {
            "lib_path": self.lib_path,
            "exists": self.exists,
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "total_symlinks": self.total_symlinks,
            "total_bytes": self.total_bytes,
            "essential_libraries": self.essential_libraries,
            "essential_required_present": self.essential_required_present,
            "essential_required_total": self.essential_required_total,
            "kernel_versions": list(self.kernel_versions),
            "module_files": self.module_files,
            "isapnpmap_present": self.isapnpmap_present,
            "pcimap_present": self.pcimap_present,
            "usbmap_present": self.usbmap_present,
            "kernel_build_link_ok": self.kernel_build_link_ok,
            "iptables_dir": self.iptables_dir,
            "kbd_dir": self.kbd_dir,
            "oss_dir": self.oss_dir,
            "security_dir": self.security_dir,
            "firmware_dir": self.firmware_dir,
            "cpp_reference_ok": self.cpp_reference_ok,
            "cpp_target": self.cpp_target,
            "ld_so_conf_exists": self.ld_so_conf_exists,
            "ld_so_cache_exists": self.ld_so_cache_exists,
            "ld_so_cache_age_seconds": self.ld_so_cache_age_seconds,
            "alternate_qualifiers": list(self.alternate_qualifiers),
            "issues": list(self.issues),
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Helper - safe stat
# ---------------------------------------------------------------------------

def _safe_stat(path: Path):
    try:
        return path.stat()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def lib_summary(lib_path: str = "/lib",
                kernel_source_root: str = "/usr/src",
                ld_so_conf: str = "/etc/ld.so.conf",
                ld_so_cache: str = "/etc/ld.so.cache") -> LibSummary:
    """Build a :class:`LibSummary` for ``lib_path``.

    All paths are configurable so the function works in tests against
    a temporary directory as well as against a real /lib on the host.
    """
    summary = LibSummary(lib_path=str(lib_path), exists=False)
    root = Path(lib_path)
    if not root.is_dir():
        summary.issues.append(f"{lib_path} is not a directory or does not exist")
        return summary
    summary.exists = True

    # 1. Walk the directory (one level deep) for headline counts.
    files = 0
    dirs = 0
    symlinks = 0
    total_bytes = 0
    for entry in root.iterdir():
        st = _safe_stat(entry)
        if st is None:
            continue
        if entry.is_symlink():
            symlinks += 1
        elif entry.is_dir():
            dirs += 1
        elif entry.is_file():
            files += 1
            total_bytes += st.st_size
    summary.total_files = files
    summary.total_dirs = dirs
    summary.total_symlinks = symlinks
    summary.total_bytes = total_bytes

    # 2. Essential libraries (libc.so.*, ld*, libm.so.*, ...).
    try:
        from lib.essential_libs import EssentialLibraryManager
        mgr = EssentialLibraryManager()
        libs = mgr.list_libraries()
        summary.essential_libraries = len(libs)
        required = mgr.get_required_libs()
        summary.essential_required_total = len(required)
        summary.essential_required_present = sum(
            1 for lib in required if (root / lib.name).exists() or
            (root / lib.path.lstrip("/")).exists()
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("essential_libs: %s", exc)
        summary.issues.append("essential_libs: %s" % exc)

    # 3. Kernel modules.
    modules_dir = root / "modules"
    if modules_dir.is_dir():
        for kv in sorted(modules_dir.iterdir()):
            if not kv.is_dir():
                continue
            summary.kernel_versions.append(kv.name)
            # Count *.ko and *.ko.* module files.
            summary.module_files += sum(
                1 for f in kv.rglob("*.ko*") if f.is_file() or f.is_symlink()
            )
            summary.isapnpmap_present = (kv / "isapnpmap.dep").exists()
            summary.pcimap_present    = (kv / "pcimap").exists()
            summary.usbmap_present    = (kv / "usbmap").exists()
            build_link = kv / "build"
            if build_link.is_symlink():
                target = os.readlink(build_link)
                if not os.path.isabs(target):
                    target = os.path.normpath(os.path.join(str(kv), target))
                summary.kernel_build_link_ok = os.path.isdir(target)
            else:
                summary.kernel_build_link_ok = False
            # Only the most recent kernel is summarised; older ones
            # contribute to the file count.
            break
        # If the loop didn't break, summarise the *last* kernel dir.
        if summary.kernel_versions and not summary.module_files:
            kv = root / "modules" / summary.kernel_versions[-1]
            summary.module_files = sum(
                1 for f in kv.rglob("*.ko*") if f.is_file() or f.is_symlink()
            )

    # 4. Subsystem directories.
    summary.iptables_dir = (root / "iptables").is_dir()
    summary.kbd_dir      = (root / "kbd").is_dir()
    summary.oss_dir      = (root / "oss").is_dir()
    summary.security_dir = (root / "security").is_dir()
    summary.firmware_dir = (root / "firmware").is_dir()

    # 5. /lib/cpp.
    cpp = root / "cpp"
    if cpp.is_symlink():
        summary.cpp_reference_ok = True
        summary.cpp_target = str(os.readlink(cpp))
    elif cpp.is_file():
        # A reference file containing the path is also acceptable.
        text = cpp.read_text(encoding="utf-8", errors="replace").strip()
        if text.startswith("/"):
            summary.cpp_reference_ok = True
            summary.cpp_target = text
        else:
            summary.issues.append("/lib/cpp is a regular file but does not contain a path")
    else:
        summary.issues.append("/lib/cpp is missing (FHS requires a reference to the C preprocessor)")

    # 6. ld.so.conf + ld.so.cache.
    conf = Path(ld_so_conf)
    summary.ld_so_conf_exists = conf.is_file()
    if not summary.ld_so_conf_exists:
        summary.issues.append(f"{ld_so_conf} is missing")
    cache = Path(ld_so_cache)
    if cache.is_file():
        summary.ld_so_cache_exists = True
        st = cache.stat()
        summary.ld_so_cache_age_seconds = time.time() - st.st_mtime
    else:
        summary.issues.append(f"{ld_so_cache} is missing (run ldconfig)")

    # 7. Alternate qualifiers (/lib32, /lib64, /libx32, /libsframe).
    for qual in ("32", "64", "x32", "sframe"):
        if (root.parent / f"lib{qual}").is_dir():
            summary.alternate_qualifiers.append(qual)

    return summary


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "lib"
        root.mkdir()
        # Create the FHS-mandated minimum: libc + ld + cpp reference.
        (root / "libc.so.6").write_bytes(b"stub")
        (root / "ld-linux-x86-64.so.2").write_bytes(b"stub")
        (root / "cpp").write_text("/usr/bin/cpp\n")
        # A kernel-version subdir.
        kv = root / "modules" / "6.6.0-umeros"
        kv.mkdir(parents=True)
        (kv / "modules.dep").write_text("# stub")
        info = lib_summary(lib_path=str(root))
        if not info.exists:
            return False
        if info.essential_required_present < 2:
            return False
        if "6.6.0-umeros" not in info.kernel_versions:
            return False
        # Render the table - just make sure it doesn't crash.
        text = info.render_table()
        if "Umer OS /lib summary" not in text:
            return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(lib_summary().render_table())
    print("libinfo selftest:", "OK" if _selftest() else "FAIL")
