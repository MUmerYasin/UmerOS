"""
UmerOS /usr/src - Source Code Hierarchy
========================================
TLDP /usr: Contains Linux kernel sources, header files, and documentation.
"""

from __future__ import annotations

from ..core.command import Command


class SrcDirCommand(Command):
    """Source code directory listing."""

    name = "src-dir"
    description = "List /usr/src source code directories"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/ - Source code\n"
            "  linux/         - Linux kernel source\n"
            "  linux-headers/ - Kernel headers for compilation\n"
            "  packages/      - Source packages\n"
        )


class SrcLinuxCommand(Command):
    """Linux kernel source directory."""

    name = "src-linux"
    description = "/usr/src/linux - Linux kernel source tree"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/linux/ - Linux kernel source\n"
            "  .config        - Kernel configuration\n"
            "  Makefile        - Build system\n"
            "  README          - Kernel release notes\n"
            "  CREDITS         - Contributors\n"
            "  MAINTAINERS     - Subsystem maintainers\n"
            "  COPYING         - GNU GPL license\n"
            "  arch/           - Architecture-specific code\n"
            "  drivers/        - Device drivers\n"
            "  fs/             - Filesystems\n"
            "  net/            - Networking\n"
            "  mm/             - Memory management\n"
            "  kernel/         - Core kernel\n"
            "  Documentation/  - Kernel docs\n"
        )


class SrcKernelHeadersCommand(Command):
    """Kernel headers directory."""

    name = "src-kernel-headers"
    description = "/usr/src/linux-headers - kernel headers for building modules"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/linux-headers-$(uname -r)/\n"
            "  Kconfig, Makefile, Module.symvers\n"
            "  include/  - Kernel headers\n"
            "  scripts/  - Build scripts\n"
            "  arch/     - Architecture headers\n"
        )


class SrcRPMBuildCommand(Command):
    """RPM build directory."""

    name = "src-rpm-build"
    description = "/usr/src/RPM/BUILD - RPM build area"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/RPM/\n"
            "  BUILD/      - Temporary build files\n"
            "  RPMS/       - Built RPM packages\n"
            "  SOURCES/    - Source tarballs, patches\n"
            "  SPECS/      - RPM spec files\n"
            "  SRPMS/      - Source RPMs\n"
        )
