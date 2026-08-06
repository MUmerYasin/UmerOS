"""
UmerOS /usr/X11R6 - X Window System Hierarchy
===============================================
TLDP /usr: Contains X11R6 libraries, executables, docs, fonts.
Symbolic links expected:
  /usr/bin/X11 -> /usr/X11R6/bin
  /usr/lib/X11 -> /usr/X11R6/lib/X11
  /usr/include/X11 -> /usr/X11R6/include/X11
"""

from __future__ import annotations

from core.command import Command


class X11R6BinCommand(Command):
    """X11R6 binary directory management."""

    name = "x11r6-bin"
    description = "X11R6 binary directory (X11 programs)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/X11R6/bin/ - X11 programs\n"
            "  X, Xorg, xauth, xmodmap, xterm, xeyes, xclock, ...\n"
            "  Symlink: /usr/bin/X11 -> /usr/X11R6/bin\n"
        )


class X11R6LibCommand(Command):
    """X11R6 library directory."""

    name = "x11r6-lib"
    description = "X11R6 library directory (X11 shared libraries)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/X11R6/lib/ - X11 shared libraries\n"
            "  libX11.so, libXext.so, libXt.so, ...\n"
            "  Symlink: /usr/lib/X11 -> /usr/X11R6/lib/X11\n"
        )


class X11R6IncludeCommand(Command):
    """X11R6 header files directory."""

    name = "x11r6-include"
    description = "X11R6 header files (X11 development headers)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/X11R6/include/ - X11 development headers\n"
            "  X11/, Xm/, Xt/, Xaw/, ...\n"
            "  Symlink: /usr/include/X11 -> /usr/X11R6/include/X11\n"
        )


class X11R6LibModulesCommand(Command):
    """X11R6 modules directory."""

    name = "x11r6-lib-modules"
    description = "X11R6 modules directory (X11 loadable modules)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/X11R6/lib/modules/ - X11 loadable modules\n"
            "  video4linux, DRI, GLX extensions, input device drivers\n"
        )


class X11R6FontsCommand(Command):
    """X11R6 fonts directory."""

    name = "x11r6-fonts"
    description = "X11R6 fonts directory (X Font Server fonts)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/X11R6/lib/X11/fonts/ - X11 fonts\n"
            "  Type1/, TrueType/, Misc/, 75dpi/, 100dpi/\n"
            "  Managed by xfs (X Font Server)\n"
        )


class X11R6DocCommand(Command):
    """X11R6 documentation directory."""

    name = "x11r6-doc"
    description = "X11R6 documentation directory"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/X11R6/lib/X11/doc/ - X11 documentation\n"
            "  Protocol specs, library docs, font docs\n"
        )


class XorgCommand(Command):
    """X.Org X server."""

    name = "xorg"
    description = "X.Org X Window System server"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] == "--version":
            return "X.Org X Server 1.21.1.8\n"
        return "xorg: X server not available in headless UmerOS\n"
