"""
UmerOS /usr/include - C/C++ Header Files
=========================================
TLDP /usr: The directory for header files, needed for compiling
user space source code. Package-specific headers go in /usr/include/<pkg>.
"""

from __future__ import annotations

from ..core.command import Command


class IncludeDirCommand(Command):
    """List C/C++ header files."""

    name = "include-dir"
    description = "List /usr/include header file directories"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/include/ - C/C++ header files\n"
            "  stdio.h, stdlib.h, string.h, math.h, ...\n"
            "  Subdirectories by package:\n"
            "    linux/     - Linux kernel headers\n"
            "    sys/       - System headers\n"
            "    netinet/   - Network headers\n"
            "    X11/       - X11 headers (symlink)\n"
        )


class PkgConfigCommand(Command):
    """pkg-config - compile/link flag finder."""

    name = "pkg-config"
    description = "pkg-config - compile and link flag finder"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: pkg-config [options] [packages]\n"
        pkg = args[0]
        return (
            f"Package: {pkg}\n"
            f"Version: 1.0.0\n"
            f"Cflags: -I/usr/include/{pkg}\n"
            f"Libs: -L/usr/lib -l{pkg}\n"
        )


class PkgConfigLibCommand(Command):
    """pkg-config library directory."""

    name = "pkg-config-lib"
    description = "pkg-config .pc file directory"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/lib/pkgconfig/ - .pc files for pkg-config\n"
            "  Contains compile/link metadata for installed libraries.\n"
        )


class GnuStubsCommand(Command):
    """GNU stubs header files."""

    name = "gnu-stubs"
    description = "GNU stubs header files"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/include/gnu/ - GNU-specific stubs\n"
            "  stubs.h, versions.h\n"
        )


class CpuConfigCommand(Command):
    """CPU-specific header configuration."""

    name = "cpu-config"
    description = "CPU-specific header configuration"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/include/x86_64-linux-gnu/ - x86_64 headers\n"
            "  Architecture-specific system headers.\n"
        )
