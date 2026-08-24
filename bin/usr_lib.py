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
UmerOS /usr/lib - Shared Libraries & Modules
=============================================
/usr: Contains program libraries - collections of frequently
used program routines. Also includes modules and architecture-specific libs.
"""

from __future__ import annotations

from core.command import Command


class LibDirCommand(Command):
    """List shared libraries."""

    name = "lib-dir"
    description = "List /usr/lib shared libraries"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/lib/ - Shared libraries and modules\n"
            "  libm.so, libpthread.so, libc.so, ...\n"
            "  x86_64-gnu/ - Architecture-specific libs\n"
            "  modules/ - Kernel modules (legacy)\n"
            "  debug/ - Debug symbols\n"
        )


class LdConfigCommand(Command):
    """Dynamic linker configuration."""

    name = "ldconfig"
    description = "Configure dynamic linker library cache"
    category = "usr"
    privileges = ["root"]

    def execute(self, *args):
        if args and args[0] == "-p":
            return (
                "/usr/lib/ (0 files):\n"
                "  ld-UmerOS-x86-64.so.2 -> ld-2.31.so\n"
                "  libc.so.6 -> libc-2.31.so\n"
                "  libm.so.6 -> libm-2.31.so\n"
                "  libpthread.so.0 -> libpthread-2.31.so\n"
                "  libssl.so.1.1 -> libssl.so.1.1.1k\n"
            )
        return "ldconfig: updating library cache\n"


class LdLinuxCommand(Command):
    """Dynamic linker/loader."""

    name = "ld"
    description = "Dynamic linker/loader (ld-x86-64.so.2)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return "ld: dynamic linker (used internally by ELF loader)\n"


class LdPreloadCommand(Command):
    """LD_PRELOAD shared library override."""

    name = "ld-preload"
    description = "LD_PRELOAD shared library override mechanism"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "LD_PRELOAD - shared library preloading\n"
            "  Allows overriding functions in shared libraries.\n"
            "  Usage: LD_PRELOAD=libfoo.so ./program\n"
        )


class PkgConfigLibCommand(Command):
    """pkg-config library files directory."""

    name = "pkgconfig"
    description = "/usr/lib/pkgconfig - library metadata files"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/lib/pkgconfig/ - .pc files\n"
            "  Contains compile/link flags for pkg-config.\n"
            "  Example: openssl.pc, zlib.pc, ...\n"
        )


class UsrLibModulesCommand(Command):
    """Kernel modules directory."""

    name = "lib-modules"
    description = "/usr/lib/modules - kernel modules"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/lib/modules/ - Kernel modules\n"
            "  Organized by kernel version.\n"
            "  Contains .ko files (kernel objects).\n"
        )
