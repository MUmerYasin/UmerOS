"""
UmerOS /usr/lib<qual> Hierarchy Commands
==========================================
FHS 3.0 §4.2.3: Alternate format libraries.

On a multilib system, this directory contains alternate format
libraries such as /usr/lib64 for 64-bit libraries on a 32-bit host.
These directories are not present on non-multilib systems.
"""

from __future__ import annotations

from core.command import Command


# ─── Lib64 ───────────────────────────────────────────────────────────────────


class LIB64Command(Command):
    """Display /usr/lib64 contents - 64-bit libraries."""

    name = "lib64"
    description = "Display /usr/lib64 - 64-bit libraries"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/lib64:\n"
            "  64-bit shared libraries\n"
            "  Used on multilib systems (x86_64 with 32-bit compat)\n"
            "  ELF format, 64-bit\n"
            "  Symlinks for library versioning\n"
            "  Examples: libc.so.6, libm.so.6, libpthread.so.0\n"
        )


# ─── Lib32 ───────────────────────────────────────────────────────────────────


class LIB32Command(Command):
    """Display /usr/lib32 contents - 32-bit libraries (multilib)."""

    name = "lib32"
    description = "Display /usr/lib32 - 32-bit compatibility libraries"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/lib32:\n"
            "  32-bit compatibility libraries on 64-bit systems\n"
            "  Only present on multilib configurations\n"
            "  ELF format, 32-bit\n"
            "  Used for 32-bit application compatibility\n"
        )


# ─── Libx32 ──────────────────────────────────────────────────────────────────


class LIBX32Command(Command):
    """Display /usr/libx32 contents - x32 ABI libraries."""

    name = "libx32"
    description = "Display /usr/libx32 - x32 ABI libraries"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/libx32:\n"
            "  x32 ABI libraries (ILP32 on x86_64)\n"
            "  Only present on x32 multilib configurations\n"
            "  Smaller code size than 64-bit, pointer space 32-bit\n"
        )
