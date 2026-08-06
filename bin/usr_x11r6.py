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
        if args and args[0] in ("-h", "--help"):
            return (
                "Usage: x11r6-bin [options]\n"
                "Display X11R6 binary directory contents.\n"
                "\nOptions:\n"
                "  -l, --long    Show detailed listing with permissions\n"
                "  -p, --paths   Show full paths for each binary\n"
            )
        if args and args[0] in ("-l", "--long"):
            return (
                "/usr/X11R6/bin: 12 executables\n"
                "  xterm    -rwxr-xr-x  256K  X11 terminal emulator\n"
                "  xclock   -rwxr-xr-x   48K  X11 clock display\n"
                "  xeyes    -rwxr-xr-x   32K  X11 eye cursor follower\n"
                "  xinit    -rwxr-xr-x   16K  X window system initializer\n"
                "  startx   -rwxr-xr-x    8K  Start X server\n"
                "  xrandr   -rwxr-xr-x   64K  X resize and rotate\n"
                "  xrdb     -rwxr-xr-x   40K  X resource database manager\n"
                "  xsetroot -rwxr-xr-x   24K  X root window manipulation\n"
                "  xwininfo -rwxr-xr-x   32K  X window info\n"
                "  xdpyinfo -rwxr-xr-x   48K  X display info\n"
                "  xhost    -rwxr-xr-x   16K  X server access control\n"
                "  xauth    -rwxr-xr-x   32K  X authorization manager\n"
            )
        if args and args[0] in ("-p", "--paths"):
            return (
                "/usr/X11R6/bin/xterm\n"
                "/usr/X11R6/bin/xclock\n"
                "/usr/X11R6/bin/xeyes\n"
                "/usr/X11R6/bin/xinit\n"
                "/usr/X11R6/bin/startx\n"
                "/usr/X11R6/bin/xrandr\n"
                "/usr/X11R6/bin/xrdb\n"
                "/usr/X11R6/bin/xsetroot\n"
                "/usr/X11R6/bin/xwininfo\n"
                "/usr/X11R6/bin/xdpyinfo\n"
                "/usr/X11R6/bin/xhost\n"
                "/usr/X11R6/bin/xauth\n"
            )
        return (
            "/usr/X11R6/bin/ - X11 programs\n"
            "  X, Xorg, xauth, xmodmap, xterm, xeyes, xclock, ...\n"
            "  Symlink: /usr/bin/X11 -> /usr/X11R6/bin\n"
            "  Use --long for detailed listing, --paths for full paths\n"
        )


class X11R6LibCommand(Command):
    """X11R6 library directory."""

    name = "x11r6-lib"
    description = "X11R6 library directory (X11 shared libraries)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-h", "--help"):
            return (
                "Usage: x11r6-lib [options]\n"
                "Display X11R6 library directory contents.\n"
                "\nOptions:\n"
                "  -l, --long    Show detailed library info\n"
                "  -s, --sonames Show shared object names\n"
            )
        if args and args[0] in ("-l", "--long"):
            return (
                "/usr/X11R6/lib: 15 shared libraries\n"
                "  libX11.so    1.7.5   1.2M  Core X11 protocol\n"
                "  libXt.so     1.2.1   340K  X toolkit intrinsics\n"
                "  libXmu.so    1.1.4   180K  X miscellaneous utilities\n"
                "  libXext.so   1.3.5   240K  X11 extensions\n"
                "  libXrender.so 1.5.5  110K  X Render extension\n"
                "  libXrandr.so 1.5.3   120K  X Resize and Rotate\n"
                "  libXinerama.so 1.1.4  80K  Xinerama extension\n"
                "  libXi.so     1.8.1   280K  X input extension\n"
                "  libXfixes.so 5.0.3    60K  X fixes extension\n"
                "  libXcomposite.so 1.4.5  40K  X composite\n"
                "  libXdamage.so 1.1.6   48K  X damage\n"
                "  libXcursor.so 1.2.1   72K  X cursor management\n"
                "  libXft.so    2.3.4   140K  X FreeType\n"
                "  libXfont2.so 2.0.6   160K  X font handling\n"
                "  libXxf86vm.so 1.1.4   56K  X video mode\n"
            )
        if args and args[0] in ("-s", "--sonames"):
            return (
                "libX11.so.6\n"
                "libXt.so.6\n"
                "libXmu.so.6\n"
                "libXext.so.6\n"
                "libXrender.so.1\n"
                "libXrandr.so.2\n"
                "libXinerama.so.1\n"
                "libXi.so.6\n"
                "libXfixes.so.3\n"
                "libXcomposite.so.1\n"
                "libXdamage.so.1\n"
                "libXcursor.so.1\n"
                "libXft.so.2\n"
                "libXfont2.so.2\n"
                "libXxf86vm.so.1\n"
            )
        return (
            "/usr/X11R6/lib/ - X11 shared libraries\n"
            "  libX11.so, libXext.so, libXt.so, ...\n"
            "  Symlink: /usr/lib/X11 -> /usr/X11R6/lib/X11\n"
            "  Use --long for detailed listing, --sonames for .so names\n"
        )


class X11R6IncludeCommand(Command):
    """X11R6 header files directory."""

    name = "x11r6-include"
    description = "X11R6 header files (X11 development headers)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-h", "--help"):
            return (
                "Usage: x11r6-include [options]\n"
                "Display X11R6 include header directory contents.\n"
                "\nOptions:\n"
                "  -t, --tree    Show directory tree structure\n"
                "  -c, --count   Show header counts by subdirectory\n"
            )
        if args and args[0] in ("-t", "--tree"):
            return (
                "/usr/X11R6/include/\n"
                "  X11/\n"
                "    Xlib.h            - Core Xlib header\n"
                "    Xutil.h           - X utility functions\n"
                "    Xatom.h           - Predefined atoms\n"
                "    Xresource.h       - X resource manager\n"
                "    keysym.h          - Key symbol definitions\n"
                "    Xft/              - X FreeType interface\n"
                "      Xft.h\n"
                "      XftConfig.h\n"
                "    Xrandr/           - X RandR extension\n"
                "      Xrandr.h\n"
                "      Xrandrproto.h\n"
                "  Xt/                 - X toolkit headers\n"
                "    Intrinsic.h\n"
                "    Core.h\n"
                "  Xmu/                - X misc utilities headers\n"
                "    Xmu.h\n"
                "  Xext/               - X extension headers\n"
                "    Xext.h\n"
            )
        if args and args[0] in ("-c", "--count"):
            return (
                "X11 header counts:\n"
                "  X11/:        245 headers\n"
                "  X11/Xft/:     18 headers\n"
                "  X11/Xrandr/:  12 headers\n"
                "  Xt/:          34 headers\n"
                "  Xmu/:         22 headers\n"
                "  Xext/:        15 headers\n"
                "  Total:       346 headers\n"
            )
        return (
            "/usr/X11R6/include/ - X11 development headers\n"
            "  X11/, Xm/, Xt/, Xaw/, ...\n"
            "  Symlink: /usr/include/X11 -> /usr/X11R6/include/X11\n"
            "  Use --tree for directory structure, --count for totals\n"
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
