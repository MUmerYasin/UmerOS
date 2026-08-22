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
UmerOS /usr/include - C/C++ Header Files
=========================================
TLDP /usr: The directory for header files, needed for compiling
user space source code. Package-specific headers go in /usr/include/<pkg>.
"""

from __future__ import annotations

from core.command import Command


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
            "    /          -  kernel headers\n"
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
            "/usr/include/x86_64-gnu/ - x86_64 headers\n"
            "  Architecture-specific system headers.\n"
        )


class LinuxAsmCommand(Command):
    """Asm/ headers - architecture-specific kernel interfaces."""

    name = "asm"
    description = "asm/ headers - architecture-specific kernel interfaces"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/include/asm/ - Architecture-specific kernel headers\n"
            "  FHS 3.0 §6.1.8: /usr/include/asm/ is a symlink to\n"
            "  asm-generic/ or arch-specific asm/ directory\n"
            "  Subdirectories:\n"
            "    asm/       - Symlink to asm-generic/ or arch-specific\n"
            "    asm-generic/ - Generic ASM definitions\n"
            "    drm/       - Direct Rendering Manager headers\n"
            "    linux/     - kernel headers\n"
            "    misc/      - Miscellaneous kernel headers\n"
            "    mtd/       - Memory Technology Device headers\n"
            "    rdma/      - RDMA subsystem headers\n"
            "    sound/     - ALSA sound system headers\n"
            "    video/     - Video device headers\n"
        )


class DrmHeadersCommand(Command):
    """DRM (Direct Rendering Manager) headers."""

    name = "drm-headers"
    description = "DRM (Direct Rendering Manager) header files"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/include/drm/ - Direct Rendering Manager headers\n"
            "  FHS 3.0 §6.1.8: specific\n"
            "  drm.h, drm_mode.h, drm_sarea.h, ...\n"
            "  Used by: Graphics drivers, Mesa, libdrm\n"
            "  Provides: GPU/rendering device interface definitions\n"
        )


class MtdHeadersCommand(Command):
    """MTD (Memory Technology Device) headers."""

    name = "mtd-headers"
    description = "MTD (Memory Technology Device) header files"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/include/mtd/ - Memory Technology Device headers\n"
            "  FHS 3.0 UmerOS-specific\n"
            "  mtd-user.h, mtd-abi.h, ...\n"
            "  Used by: Flash memory drivers, MTD subsystem\n"
            "  Provides: NAND/NOR flash interface definitions\n"
        )


class RdmaHeadersCommand(Command):
    """RDMA subsystem headers."""

    name = "rdma-headers"
    description = "RDMA subsystem header files"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/include/rdma/ - RDMA subsystem headers\n"
            "  FHS 3.0 UmerOS-specific\n"
            "  rdma_user_cm.h, ib_userverbs.h, ...\n"
            "  Used by: InfiniBand, RoCE, iWARP drivers\n"
            "  Provides: Remote Direct Memory Access definitions\n"
        )


class SoundHeadersCommand(Command):
    """ALSA sound system headers."""

    name = "sound-headers"
    description = "ALSA sound system header files"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/include/sound/ - ALSA sound system headers\n"
            "  FHS 3.0 §6.1.8: Linux-specific\n"
            "  soundcard.h, asound.h, ...\n"
            "  Used by: ALSA drivers, audio applications\n"
            "  Provides: Sound card interface definitions\n"
        )


class VideoHeadersCommand(Command):
    """Video device headers."""

    name = "video-headers"
    description = "Video device header files"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/include/video/ - Video device headers\n"
            "  FHS 3.0 §6.1.8: \n"
            "  video_decoder.h, video_encoder.h, ...\n"
            "  Used by: Video drivers, capture apps\n"
            "  Provides: Video device interface definitions\n"
        )
