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
UmerOS /usr/share/doc Hierarchy Commands
==========================================
FHS 3.0 §4.11.5: Documentation files.

Software documentation should be placed in /usr/share/doc/<pkg>
where <pkg> is the package name. This directory contains README,
CHANGES, LICENSE, and other documentation files.
"""

from __future__ import annotations

from core.command import Command


# ─── Documentation ───────────────────────────────────────────────────────────


class DOCDIRCommand(Command):
    """Display /usr/share/doc contents."""

    name = "doc-dir"
    description = "Display /usr/share/doc documentation directory"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-h", "--help"):
            return (
                "Usage: doc-dir [options]\n"
                "Display /usr/share/doc contents and structure.\n"
                "\nOptions:\n"
                "  -l, --long    Show detailed listing\n"
                "  -t, --tree    Show tree structure\n"
            )
        if args and args[0] in ("-l", "--long"):
            return (
                "drwxr-xr-x 2 root root  4096  /usr/share/doc:\n"
                "  Package Name          Docs  Size   Last Modified\n"
                "  coreutils             4     120K   2024-01-15\n"
                "  bash                  3     85K    2024-01-20\n"
                "  gcc                   5     256K   2024-02-01\n"
                "  glibc                 6     340K   2024-01-25\n"
                "  openssl               4     178K   2024-02-05\n"
            )
        if args and args[0] in ("-t", "--tree"):
            return (
                "/usr/share/doc/\n"
                "  coreutils/\n"
                "    README\n"
                "    CHANGELOG\n"
                "    AUTHORS\n"
                "    LICENSE\n"
                "  bash/\n"
                "    README\n"
                "    CHANGES\n"
                "    COPYING\n"
                "  gcc/\n"
                "    README\n"
                "    COPYING\n"
                "    CHANGELOG\n"
                "    INSTALL\n"
                "    AUTHORS\n"
            )
        return (
            "/usr/share/doc:\n"
            "  Per-package documentation (FHS 3.0 §4.11.5)\n"
            "  Format: /usr/share/doc/<package-name>/\n"
            "  Files: README, CHANGELOG, LICENSE, AUTHORS\n"
            "  Not mandatory - packages may omit docs\n"
            "  No binary files, only text and images\n"
            "  Use --long for detailed listing, --tree for structure\n"
        )


class LSCOMMAND(Command):
    """List installed package documentation."""

    name = "doc-list"
    description = "List installed package documentation"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-h", "--help"):
            return (
                "Usage: doc-list [options] [package]\n"
                "List documentation files for packages.\n"
                "\nOptions:\n"
                "  -s, --summary   Show summary counts\n"
                "  -a, --all       Show all packages\n"
            )
        if args and args[0] in ("-s", "--summary"):
            return (
                "Package documentation summary:\n"
                "  Total packages: 5\n"
                "  Total files: 22\n"
                "  Total size: 979K\n"
            )
        return (
            "Package documentation:\n"
            "  coreutils/README, CHANGELOG, AUTHORS, LICENSE\n"
            "  bash/README, CHANGES, COPYING\n"
            "  gcc/README, COPYING, CHANGELOG, INSTALL, AUTHORS\n"
            "  glibc/README, INSTALL, COPYING.LIB, NOTES, FAQ\n"
            "  openssl/README, CHANGES, LICENSE, INSTALL\n"
        )


class PKGDOCCOMMAND(Command):
    """Display documentation for a package."""

    name = "pkg-doc"
    description = "Display documentation for an installed package"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        if not args or args[0] in ("-h", "--help"):
            return (
                "Usage: pkg-doc <package> [file]\n"
                "Display documentation for an installed package.\n"
                "If file is specified, show that specific doc file.\n"
            )
        pkg = args[0]
        if len(args) > 1:
            f = args[1]
            return (
                f"/usr/share/doc/{pkg}/{f}:\n"
                f"  This is a simulated documentation file for {pkg}.\n"
                f"  In a real system, this would contain the actual content.\n"
            )
        return (
            f"/usr/share/doc/{pkg}/:\n"
            f"  README       - Package description and usage\n"
            f"  CHANGELOG    - Version history and release notes\n"
            f"  LICENSE      - Software license (GPL, MIT, etc.)\n"
            f"  AUTHORS      - Contributors and maintainers\n"
            f"  INSTALL      - Build and installation instructions\n"
            f"  COPYING      - License text\n"
            f"\n  Total: 6 documentation files\n"
        )


class PKGCHANGESCommand(Command):
    """Display changelog for a package."""

    name = "pkg-changes"
    description = "Display changelog for an installed package"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        if not args or args[0] in ("-h", "--help"):
            return (
                "Usage: pkg-changes <package> [--format fmt]\n"
                "Display changelog for an installed package.\n"
                "\nOptions:\n"
                "  --format text    Plain text (default)\n"
                "  --format md      Markdown format\n"
            )
        pkg = args[0]
        fmt = "text"
        if "--format" in args:
            idx = args.index("--format")
            if idx + 1 < len(args):
                fmt = args[idx + 1]
        if fmt == "md":
            return (
                f"# Changelog for {pkg}\n\n"
                f"## Version 1.2.0 (2024-02-15)\n"
                f"- Added new features\n"
                f"- Performance improvements\n\n"
                f"## Version 1.1.1 (2024-01-20)\n"
                f"- Bug fixes\n"
                f"- Security patches\n\n"
                f"## Version 1.1.0 (2024-01-10)\n"
                f"- New feature support\n"
                f"- Documentation updates\n\n"
                f"## Version 1.0.0 (2024-01-01)\n"
                f"- Initial stable release\n"
            )
        return (
            f"/usr/share/doc/{pkg}/CHANGELOG:\n"
            f"  Version 1.2.0 - Added new features, performance improvements\n"
            f"  Version 1.1.1 - Bug fixes, security patches\n"
            f"  Version 1.1.0 - New feature support, documentation updates\n"
            f"  Version 1.0.0 - Initial stable release\n"
        )
