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
        if args and args[0] in ("-h", "--help"):
            return (
                "Usage: x11r6-lib-modules [options]\n"
                "Display X11R6 modules directory contents.\n"
                "\nOptions:\n"
                "  -l, --long    Show detailed module info\n"
                "  -c, --categories  Group by module category\n"
            )
        if args and args[0] in ("-l", "--long"):
            return (
                "/usr/X11R6/lib/modules: 8 module categories\n"
                "  video4/          12 modules  Video capture devices\n"
                "  drivers/         24 modules  GPU drivers (nvidia, ati, intel)\n"
                "  extensions/      18 modules  X extension modules\n"
                "  input/           15 modules  Input device drivers\n"
                "  libglx.so         2.4M  GLX extension module\n"
                "  libdri.so         840K  DRI extension module\n"
                "  libglx_nvidia.so  4.2M  NVIDIA GLX module\n"
                "  libglx_mesa.so    1.8M  Mesa GLX module\n"
            )
        if args and args[0] in ("-c", "--categories"):
            return (
                "Module categories:\n"
                "  video4/          Video capture (v4l, radio, tv)\n"
                "  drivers/         GPU drivers (nvidia, ati, intel, nouveau)\n"
                "  extensions/      X extensions (glx, dri, randr, composite)\n"
                "  input/           Input drivers (keyboard, mouse, synaptics)\n"
                "  libglx.so        GLX module (main)\n"
                "  libdri.so        DRI module (main)\n"
            )
        return (
            "/usr/X11R6/lib/modules/ - X11 loadable modules\n"
            "  video4, DRI, GLX extensions, input device drivers\n"
            "  Use --long for detailed listing, --categories for grouping\n"
        )


class X11R6FontsCommand(Command):
    """X11R6 fonts directory."""

    name = "x11r6-fonts"
    description = "X11R6 fonts directory (X Font Server fonts)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-h", "--help"):
            return (
                "Usage: x11r6-fonts [options]\n"
                "Display X11R6 fonts directory contents.\n"
                "\nOptions:\n"
                "  -l, --long       Show detailed font info\n"
                "  -f, --families   List font families\n"
                "  --stats          Show font statistics\n"
            )
        if args and args[0] in ("-l", "--long"):
            return (
                "/usr/X11R6/lib/X11/fonts: 6 font directories\n"
                "  Type1/           845 fonts   PostScript Type 1 fonts\n"
                "  TrueType/       1230 fonts   TrueType fonts\n"
                "  Misc/            312 fonts   Miscellaneous bitmap fonts\n"
                "  75dpi/           286 fonts   75 DPI bitmap fonts\n"
                "  100dpi/          286 fonts   100 DPI bitmap fonts\n"
                "  CID/             145 fonts   CID-keyed fonts\n"
                "\n"
                "  Total:          3104 fonts\n"
                "  Encoding:       UTF-8\n"
                "  Server:         xfs (X Font Server)\n"
            )
        if args and args[0] in ("-f", "--families"):
            return (
                "Font families:\n"
                "  Type1:         Courier, Helvetica, Times-Roman, Symbol,\n"
                "                 ZapfDingbats, Palatino, Bookman, Century\n"
                "  TrueType:      DejaVu Sans, DejaVu Serif, Liberation Sans,\n"
                "                 Liberation Serif, Liberation Mono, Noto Sans\n"
                "  Misc:          cursor, fixed, term, lucidatypewriter\n"
                "  75dpi/100dpi:  various bitmap sizes\n"
            )
        if args and args[0] in ("--stats",):
            return (
                "Font statistics:\n"
                "  Total fonts:    3104\n"
                "  Type1:          845 (27%)\n"
                "  TrueType:      1230 (40%)\n"
                "  Bitmap:         1029 (33%)\n"
                "  Families:        48\n"
                "  Total size:    124.5 MB\n"
            )
        return (
            "/usr/X11R6/lib/X11/fonts/ - X11 fonts\n"
            "  Type1/, TrueType/, Misc/, 75dpi/, 100dpi/\n"
            "  Managed by xfs (X Font Server)\n"
            "  Use --long for details, --families for list, --stats for info\n"
        )


class X11R6DocCommand(Command):
    """X11R6 documentation directory."""

    name = "x11r6-doc"
    description = "X11R6 documentation directory"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-h", "--help"):
            return (
                "Usage: x11r6-doc [options]\n"
                "Display X11R6 documentation directory contents.\n"
                "\nOptions:\n"
                "  -l, --long       Show detailed doc info\n"
                "  --topics         List documentation topics\n"
                "  --search TERM    Search docs by keyword\n"
            )
        if args and args[0] in ("-l", "--long"):
            return (
                "/usr/X11R6/lib/X11/doc: 42 documentation files\n"
                "  PROTOCOL/          X protocol specifications\n"
                "    PROTOCOL         Core X11 protocol (187 pages)\n"
                "    RandR            RandR extension protocol\n"
                "    GLX              GLX extension protocol\n"
                "  LIB/               Library documentation\n"
                "    libX11           Xlib programming manual\n"
                "    libXt            Xt toolkit reference\n"
                "  FONTS/             Font documentation\n"
                "    fonts.txt        Font naming conventions\n"
                "  HOWTOs/            Configuration guides\n"
                "    xorg.conf        X server config guide\n"
                "  Total size:        4.2 MB\n"
            )
        if args and args[0] in ("--topics",):
            return (
                "Documentation topics:\n"
                "  PROTOCOL          X11 protocol specs (core + extensions)\n"
                "  LIB               Library APIs (Xlib, Xt, Xmu, Xft)\n"
                "  FONTS             Font handling and configuration\n"
                "  HOWTOs            Setup and configuration guides\n"
                "  FAQ               Frequently asked questions\n"
                "  CONTRIBUTING      Developer guidelines\n"
            )
        if args and args[0] in ("--search",) and len(args) > 1:
            term = args[1]
            return (
                f"Searching docs for '{term}'...\n"
                f"Found 3 matches:\n"
                f"  PROTOCOL/PROTOCOL - line 45: {term}\n"
                f"  LIB/libX11.txt - line 12: {term}\n"
                f"  HOWTOs/xorg.conf - line 8: {term}\n"
            )
        return (
            "/usr/X11R6/lib/X11/doc/ - X11 documentation\n"
            "  Protocol specs, library docs, font docs\n"
            "  Use --long for details, --topics for index, --search TERM\n"
        )


class XorgCommand(Command):
    """X.Org X server."""

    name = "xorg"
    description = "X.Org X Window System server"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-h", "--help"):
            return (
                "Usage: xorg [options]\n"
                "X.Org X Window System server.\n"
                "\nOptions:\n"
                "  --version       Show X server version\n"
                "  --config FILE   Use specified config file\n"
                "  -configure       Generate xorg.conf\n"
                "  -listvideo       List available video drivers\n"
                "  -query           Query connected displays\n"
            )
        if args and args[0] == "--version":
            return (
                "X.Org X Server 1.21.1.8\n"
                "Release Date: 2022-10-15\n"
                "X Protocol Version 11, Revision 0\n"
                "Build Operating System: UmerOS x86_64\n"
                "Current OS: UmerOS 1.0 (Unix-like)\n"
            )
        if args and args[0] in ("-configure",):
            return (
                "Generating xorg.conf...\n"
                "Section \"Device\"\n"
                "    Identifier  \"Default Device\"\n"
                "    Driver      \"modesetting\"\n"
                "EndSection\n"
                "Section \"Monitor\"\n"
                "    Identifier  \"Default Monitor\"\n"
                "    HorizSync    28.0-160.0\n"
                "    VertRefresh  48.0-75.0\n"
                "EndSection\n"
                "Section \"Screen\"\n"
                "    Identifier  \"Default Screen\"\n"
                "    Device      \"Default Device\"\n"
                "    Monitor     \"Default Monitor\"\n"
                "    DefaultDepth 24\n"
                "EndSection\n"
                "Configuration saved to /etc/X11/xorg.conf\n"
            )
        if args and args[0] in ("--config",) and len(args) > 1:
            return f"xorg: using config file '{args[1]}'\n"
        if args and args[0] in ("-listvideo",):
            return (
                "Available video drivers:\n"
                "  modesetting    - Kernel mode setting (default)\n"
                "  intel          - Intel integrated graphics\n"
                "  amdgpu         - AMD GPU (GCN/RDNA)\n"
                "  radeon         - AMD legacy (RADEON/R100-R700)\n"
                "  nouveau        - NVIDIA (open source)\n"
                "  nvidia         - NVIDIA (proprietary)\n"
                "  fbdev          - Framebuffer device\n"
                "  vesa           - VESA BIOS Emulation\n"
            )
        if args and args[0] in ("-query",):
            return (
                "Connected displays:\n"
                "  DP-1:          connected (1920x1080@60Hz)\n"
                "  HDMI-1:        disconnected\n"
                "  DP-2:          disconnected\n"
            )
        return (
            "xorg: X server not available in headless UmerOS\n"
            "  Use --version to check version\n"
            "  Use -configure to generate xorg.conf\n"
            "  Use -listvideo to list video drivers\n"
        )
