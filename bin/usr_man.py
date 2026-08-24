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
UmerOS /usr/man - Manual Pages Hierarchy
=========================================
/usr/man: Manual pages organized in 8 sections.
Now located at /usr/share/man, symlinked from /usr/man.
"""

from __future__ import annotations

from core.command import Command


class ManCmdCommand(Command):
    """Display manual page for a command."""

    name = "man-cmd"
    description = "Display manual page for a command"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: man [section] command\n"
        cmd = args[-1]
        return (
            f"Manual page for {cmd}:\n"
            f"NAME\n    {cmd} - {cmd} command\n"
            f"SYNOPSIS\n    {cmd} [options] [arguments]\n"
            f"DESCRIPTION\n    Execute {cmd} command in UmerOS.\n"
            f"SEE ALSO\n    info, help\n"
        )


class ManDirCommand(Command):
    """Manual page directory listing."""

    name = "man-dir"
    description = "List /usr/share/man directory structure"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/man/ - Manual pages by section:\n"
            "  man1/ - User programs (ls, cat, echo, ...)\n"
            "  man2/ - System calls (open, read, write, ...)\n"
            "  man3/ - Library functions (printf, malloc, ...)\n"
            "  man4/ - Special files (sd, tty, ...)\n"
            "  man5/ - File formats (/etc/passwd, ...)\n"
            "  man6/ - Games (fortune, cowsay, ...)\n"
            "  man7/ - Miscellaneous (signal, regex, ...)\n"
            "  man8/ - System admin (mount, fsck, ...)\n"
        )


class ManPathCommand(Command):
    """Show manual page search path."""

    name = "manpath"
    description = "Show manual page search path"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "MANPATH=/usr/local/man:/usr/share/man:/usr/man\n"
            "Sections searched in order: 1 8 3 2 4 5 6 7 9 0 l n\n"
        )


class UsrAproposCommand(Command):
    """Search manual pages by keyword."""

    name = "usr-apropos"
    description = "Search manual page names and descriptions"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: apropos keyword\n"
        keyword = args[0]
        return (
            f"apropos: no manual entries for '{keyword}'\n"
            f"Try 'man -k {keyword}' or 'apropos {keyword}'.\n"
        )


class UsrWhatisCommand(Command):
    """Display manual page description."""

    name = "usr-whatis"
    description = "Display manual page description for a command"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if not args:
            return "Usage: whatis command\n"
        return f"{args[0]} - {args[0]} command in UmerOS\n"


# ─── Man Page Configuration ─────────────────────────────────────────────────


class ManConfCommand(Command):
    """Display /etc/man_db.conf or /etc/man.conf configuration."""

    name = "man-conf"
    description = "Display man page database configuration"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/etc/man_db.conf - Manual page configuration\n"
            "  MANDB_MAP /usr/local/man /usr/local/share/man\n"
            "  MANDB_MAP /usr/share/man /usr/share/man\n"
            "  MANDB_MAP /usr/man /usr/share/man\n"
            "  MANDB_MAP /usr/local/lib/*/man /usr/local/share/man\n"
            "  MANDB_MAP /opt/*/man /opt/*/share/man\n"
            "\n"
            "Section directories: man1 man2 man3 man4 man5 man6 man7 man8 man9 man0\n"
            "Gzip compression: .gz files supported\n"
            "Cat pages: cached preformatted pages in cat1/...cat8/\n"
        )


class ManGlobCommand(Command):
    """Glob-based manual page path search."""

    name = "man-glob"
    description = "Show manual page glob patterns for section lookup"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "Man page glob patterns:\n"
            "  /usr/share/man/man{1..8}/{cmd}.{1..8}.gz\n"
            "  /usr/share/man/cat{1..8}/{cmd}.{1..8}.gz\n"
            "  /usr/local/man/man{1..8}/{cmd}.{1..8}.gz\n"
            "  /usr/man/man{1..8}/{cmd}.{1..8}.gz\n"
            "\n"
            "Search order: /usr/local/man > /usr/share/man > /usr/man\n"
            "Sections: 1 8 3 2 4 5 6 7 9 0 l n\n"
        )


class ManLocalCommand(Command):
    """Local man page extensions (/etc/man.local)."""

    name = "man-local"
    description = "Local man page configuration overrides"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/etc/man.local - Local man page configuration\n"
            "  Defines site-specific manual page sections and paths.\n"
            "  Example entries:\n"
            "    MANDB_MAP /opt/custom/man /opt/custom/share/man\n"
            "    MANDB_MAP /usr/local/lib/*/man /usr/local/share/man\n"
            "\n"
            "  Used by mandb(8) to rebuild the manual page database.\n"
            "  Local administrator creates this file to add custom\n"
            "  man page search paths not provided by packages.\n"
        )


class ManNlsCommand(Command):
    """NLS (National Language Support) manual pages."""

    name = "man-nls"
    description = "Manual page NLS (National Language Support) directories"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/man/NLS/ - Localized manual pages\n"
            "  NLS man pages organized by locale:\n"
            "    en/   - English (default)\n"
            "    de/   - German\n"
            "    fr/   - French\n"
            "    es/   - Spanish\n"
            "    ja/   - Japanese\n"
            "    zh_CN/ - Simplified Chinese\n"
            "\n"
            "  Path pattern: /usr/share/man/<locale>/man<N>/<page>.<N>.gz\n"
            "  Controlled by MANDB_MAP in /etc/man_db.conf\n"
        )


class ManGroffTmacCommand(Command):
    """Groff macro packages for man page formatting."""

    name = "man-groff-tmac"
    description = "Groff macro packages used by man page system"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/share/groff/<ver>/tmac/ - Groff macro packages\n"
            "  man.tmac        - Man page macros (man(7) interface)\n"
            "  andoc.tmac      - Auto-detect nroff/troff doc type\n"
            "  mdoc.tmac       - BSD mdoc macros (alternative to man.tmac)\n"
            "  mdoc.an.tmac    - mdoc man page macros\n"
            "  www.tmac        - HTML generation macros\n"
            "  pdfroff.tmac    - PDF output macros\n"
            "\n"
            "  man.tmac loads: www.tmac, andoc.tmac\n"
            "  Used by: groff -man, mandoc, nroff -man\n"
        )


class ManGroffCommand(Command):
    """Groff document formatting system."""

    name = "man-groff"
    description = "Groff document formatting system for man pages"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/bin/groff - GNU troff document formatting system\n"
            "  Used to render man pages from source to terminal/PostScript/PDF\n"
            "\n"
            "  Key components:\n"
            "    troff   - Core formatter\n"
            "    nroff   - Terminal-oriented formatter\n"
            "    groff   - Front-end driver (selects troff/nroff)\n"
            "    grohtml - HTML output driver\n"
            "    grops   - PostScript output driver\n"
            "    gropdf  - PDF output driver\n"
            "\n"
            "  Man page rendering pipeline:\n"
            "    man cmd → groff -man -Tutf8 file.1 → pager\n"
        )

