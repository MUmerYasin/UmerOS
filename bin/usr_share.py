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
UmerOS /usr/share Hierarchy Commands
======================================
/usr/share: Architecture-independent data.

This includes:
  - Man pages and documentation
  - Info pages
  - Timezone data
  - Locale data
  - Default configuration templates
  - Graphic assets
"""

from __future__ import annotations

import os
import datetime
import logging
from core.command import Command

log = logging.getLogger("UmerOS.usr_share")


# ─── Man Pages / Documentation ──────────────────────────────────────────────


class PAGERCommand(Command):
    """Pager - display text one screen at a time."""

    name = "pager"
    description = "Pager - display text one screen at a time"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        page_size = 24
        text = ""
        if args:
            try:
                with open(args[0], "r") as f:
                    text = f.read()
            except FileNotFoundError:
                return f"pager: {args[0]}: No such file or directory\n"
            except PermissionError:
                return f"pager: {args[0]}: Permission denied\n"
        elif not os.isatty(0):
            text = os.read(0, 65536).decode("utf-8", errors="replace")
        else:
            return "Usage: pager <file>  (or pipe text to stdin)\n"

        lines = text.split("\n")
        total = len(lines)
        page = 0
        output = []
        while page * page_size < total:
            start = page * page_size
            end = min(start + page_size, total)
            output.append(f"--- Page {page + 1} of {(total + page_size - 1) // page_size} ---")
            output.extend(lines[start:end])
            page += 1
        return "\n".join(output) + "\n"


class NROFFCommand(Command):
    """Nroff - text formatter for man pages."""

    name = "nroff"
    description = "Nroff - text formatter for man pages"
    category = "text"
    privileges = ["user"]

    MACROS = {
        ".SH": "\n{}\n{}".format,
        ".TH": "--- {} ---",
        ".B": "\033[1m{}\033[0m",
        ".I": "\033[3m{}\033[0m",
        ".BR": "{} **{}**",
        ".BI": "{} *{}*",
        ".PP": "",
        ".TP": "  ",
        ".IP": "  - ",
        ".nf": "[literal block]",
        ".fi": "[end literal]",
        ".br": "",
        ".sp": "",
    }

    def execute(self, *args):
        text = ""
        if args:
            try:
                with open(args[0], "r") as f:
                    text = f.read()
            except FileNotFoundError:
                return f"nroff: {args[0]}: No such file or directory\n"
        elif not os.isatty(0):
            text = os.read(0, 65536).decode("utf-8", errors="replace")
        else:
            return "Usage: nroff <file>  (or pipe text to stdin)\n"

        output = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("."):
                parts = stripped.split(None, 1)
                macro = parts[0]
                arg = parts[1] if len(parts) > 1 else ""
                if macro in (".SH", ".TH"):
                    output.append("")
                    output.append(f"{'=' * len(arg)}")
                    output.append(arg.upper())
                    output.append(f"{'=' * len(arg)}")
                elif macro == ".B":
                    output.append(f"\033[1m{arg}\033[0m")
                elif macro == ".I":
                    output.append(f"\033[3m{arg}\033[0m")
                elif macro == ".PP":
                    output.append("")
                elif macro == ".TP":
                    output.append(f"  {arg}")
                elif macro == ".IP":
                    output.append(f"  - {arg}")
                elif macro in (".nf", ".fi", ".br", ".sp"):
                    continue
                else:
                    output.append(stripped)
            else:
                output.append(line)
        return "\n".join(output) + "\n"


class TROFFCommand(Command):
    """Troff - typesetting system (subset of nroff)."""

    name = "troff"
    description = "Troff - typesetting system"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        return NROFFCommand().execute(*args)


class GROFFCommand(Command):
    """Groff - GNU roff typesetting system."""

    name = "groff"
    description = "Groff - GNU roff typesetting system"
    category = "text"
    privileges = ["user"]

    FORMATS = {
        "-T utf8": "UTF-8 terminal output",
        "-T ascii": "ASCII terminal output",
        "-T html": "HTML output",
        "-T ps": "PostScript output",
        "-T pdf": "PDF output (requires groff-pdfmark)",
        "-T latex": "LaTeX output",
        "-T png": "PNG output (requires groff-png)",
    }

    def execute(self, *args):
        if not args:
            return "Usage: groff [-T format] [-man | -mandoc] <files...>\n"
        fmt = "-T utf8"
        files = []
        for a in args:
            if a in self.FORMATS:
                fmt = a
            elif a.startswith("-T"):
                fmt = a
            elif not a.startswith("-"):
                files.append(a)
        if not files:
            return f"groff: format={fmt}, no input files\n"
        results = [f"groff: processing with {fmt}:"]
        for f in files:
            try:
                with open(f, "r") as fh:
                    content = fh.read()
                results.append(f"  {f}: {len(content)} bytes processed")
            except FileNotFoundError:
                results.append(f"  {f}: No such file or directory")
        return "\n".join(results) + "\n"


class COLCommand(Command):
    """Col - filter reverse line feeds from input."""

    name = "col"
    description = "Col - filter reverse line feeds from input"
    category = "text"
    privileges = ["user"]

    REVERSE_CHARS = set("\x8e\x8f\x9a\x9b")

    def execute(self, *args):
        text = ""
        if not os.isatty(0):
            text = os.read(0, 65536).decode("utf-8", errors="replace")
        elif args:
            try:
                with open(args[0], "r") as f:
                    text = f.read()
            except FileNotFoundError:
                return f"col: {args[0]}: No such file or directory\n"
        else:
            return "Usage: col [-b] < file  (or pipe text to stdin)\n"

        strip_bold = "-b" in args
        result = []
        for ch in text:
            if ch in self.REVERSE_CHARS:
                continue
            if strip_bold and ch == "\x08":
                continue
            result.append(ch)
        return "".join(result)


class COLRMCommand(Command):
    """Colrm - remove columns from input."""

    name = "colrm"
    description = "Colrm - remove columns from input"
    category = "text"
    privileges = ["user"]

    def execute(self, *args):
        if len(args) < 1:
            return "Usage: colrm [start [stop]]\n"
        try:
            start = int(args[0]) - 1
        except ValueError:
            return "colrm: start must be a number\n"
        stop = int(args[1]) - 1 if len(args) > 1 else None

        text = ""
        if not os.isatty(0):
            text = os.read(0, 65536).decode("utf-8", errors="replace")
        else:
            return "colrm: pipe text to stdin\n"

        output = []
        for line in text.split("\n"):
            if stop is not None:
                output.append(line[:start] + line[stop:])
            else:
                output.append(line[:start])
        return "\n".join(output) + "\n"


# ─── Info Pages ──────────────────────────────────────────────────────────────


class INFCommand(Command):
    """Info page reader."""

    name = "info"
    description = "Info page reader - GNU documentation system"
    category = "system"
    privileges = ["user"]

    INFO_ENTRIES = {
        "coreutils": "Core utilities - file, shell, text, and more.\n"
                     "  Nodes: ls, cp, mv, rm, cat, chmod, chown, df, du, ln, mkdir, touch\n"
                     "  Use 'info <command>' for details on each utility.\n",
        "bash": "Bash - the GNU Bourne Again SHell.\n"
                "  Nodes: invocation, features, shell grammar, variables, builtins\n"
                "  Use 'info bash' for the full manual.\n",
        "grep": "Grep - print lines that match patterns.\n"
                "  Nodes: regexp, syntax, examples, limitations\n"
                "  Use 'info grep' for details.\n",
        "tar": "Tar - archiving utility.\n"
               "  Nodes: operation, options, archive, extraction\n"
               "  Use 'info tar' for the full manual.\n",
        "make": "Make - build targets from rules.\n"
                "  Nodes: overview, makefile, rules, variables, functions\n"
                "  Use 'info make' for details.\n",
    }

    def execute(self, *args):
        if not args:
            lines = ["Info pages available:\n"]
            for entry, desc in sorted(self.INFO_ENTRIES.items()):
                first_line = desc.split("\n")[0]
                lines.append(f"  {entry:15s} - {first_line}")
            lines.append("\nUsage: info <page>")
            return "\n".join(lines) + "\n"
        topic = args[0]
        if topic in self.INFO_ENTRIES:
            return self.INFO_ENTRIES[topic]
        # Fuzzy match
        matches = [k for k in self.INFO_ENTRIES if topic in k]
        if matches:
            return f"info: Did you mean: {', '.join(matches)}?\n"
        return f"info: No info entry for '{topic}'\n"


# ─── Timezone Data ───────────────────────────────────────────────────────────


class TZSELECTCommand(Command):
    """Timezone selector."""

    name = "tzselect"
    description = "Timezone selector - display timezone information"
    category = "system"
    privileges = ["user"]

    ZONES = {
        "UTC": 0, "GMT": 0,
        "US/Eastern": -5, "US/Central": -6, "US/Mountain": -7, "US/Pacific": -8,
        "Europe/London": 0, "Europe/Paris": 1, "Europe/Berlin": 1,
        "Asia/Tokyo": 9, "Asia/Shanghai": 8, "Asia/Kolkata": 5.5,
        "Australia/Sydney": 10, "Pacific/Auckland": 12,
    }

    def execute(self, *args):
        if not args:
            now = datetime.datetime.now(datetime.timezone.utc)
            lines = ["Available timezones:"]
            for zone, offset in sorted(self.ZONES.items()):
                local = now + datetime.timedelta(hours=offset)
                sign = "+" if offset >= 0 else ""
                lines.append(f"  {zone:20s} UTC{sign}{offset}")
            lines.append(f"\nCurrent UTC: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("Usage: tzselect <timezone>")
            return "\n".join(lines) + "\n"
        zone = args[0]
        if zone in self.ZONES:
            offset = self.ZONES[zone]
            now = datetime.datetime.now(datetime.timezone.utc)
            local = now + datetime.timedelta(hours=offset)
            sign = "+" if offset >= 0 else ""
            return (
                f"Timezone: {zone}\n"
                f"  UTC offset: {sign}{offset}\n"
                f"  Local time: {local.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Abbreviation: {zone.split('/')[-1]}\n"
            )
        return f"tzselect: unknown timezone '{zone}'\n"


class ZICCommand(Command):
    """Zic - timezone compiler."""

    name = "zic"
    description = "Zic - compile timezone data"
    category = "system"
    privileges = ["root"]

    def execute(self, *args):
        if not args or args[0] == "--version":
            return "zic: Timezone compiler for UmerOS (version 2024.1)\n"
        if args[0] == "--help":
            return (
                "Usage: zic [-v] [-d directory] [-l localtime] [-p posixrules] <input...>\n"
                "  Compile timezone definition files into binary format.\n"
            )
        results = ["zic: compiling timezone data:"]
        for f in args:
            if f.startswith("-"):
                continue
            try:
                with open(f, "r") as fh:
                    content = fh.read()
                # Simple Zone line parsing
                lines_parsed = 0
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("Zone") or line.startswith("Rule"):
                        lines_parsed += 1
                results.append(f"  {f}: parsed {lines_parsed} definitions")
            except FileNotFoundError:
                results.append(f"  {f}: No such file or directory")
        return "\n".join(results) + "\n"


class ZDUMPCommand(Command):
    """Zdump - display timezone information."""

    name = "zdump"
    description = "Zdump - display timezone information"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        if not args or args[0] == "--version":
            return "zdump: timezone dumper for UmerOS\n"
        zones = args if args else ["UTC"]
        output = []
        now = datetime.datetime.now(datetime.timezone.utc)
        for zone in zones:
            try:
                from zoneinfo import ZoneInfo
                zi = ZoneInfo(zone)
                local = now.astimezone(zi)
                output.append(
                    f"{zone:20s}  {local.strftime('%Y-%m-%d %H:%M:%S %Z')}  "
                    f"UTC{local.strftime('%z')}"
                )
            except (KeyError, ValueError, OSError):  # [FIX H8]
                # Fallback: just show UTC
                output.append(f"{zone:20s}  (unknown timezone)")
        return "\n".join(output) + "\n"


# ─── Locale Data ─────────────────────────────────────────────────────────────


class LOCALEDEFCOMMAND(Command):
    """Localedef - compile locale definition files."""

    name = "localedef"
    description = "Localedef - compile locale definition files"
    category = "system"
    privileges = ["root"]

    def execute(self, *args):
        if not args:
            return "Usage: localedef [-f charset] [-i source] [-o output] <name>\n"
        # Parse flags
        charset = "UTF-8"
        source = None
        output = None
        name = None
        i = 0
        while i < len(args):
            if args[i] == "-f" and i + 1 < len(args):
                charset = args[i + 1]; i += 2
            elif args[i] == "-i" and i + 1 < len(args):
                source = args[i + 1]; i += 2
            elif args[i] == "-o" and i + 1 < len(args):
                output = args[i + 1]; i += 2
            else:
                name = args[i]; i += 1
        if not name:
            return "localedef: no locale name specified\n"
        lines = [f"localedef: compiling locale '{name}'"]
        lines.append(f"  Character set: {charset}")
        if source:
            lines.append(f"  Source file: {source}")
        if output:
            lines.append(f"  Output: {output}")
        # Show what locale categories would be set
        cats = ["LC_CTYPE", "LC_COLLATE", "LC_TIME", "LC_NUMERIC",
                "LC_MONETARY", "LC_MESSAGES", "LC_ALL"]
        for cat in cats:
            lines.append(f"  {cat}={name}.{charset}")
        lines.append(f"  {name}: compiled successfully")
        return "\n".join(lines) + "\n"


# ─── Default Configuration ──────────────────────────────────────────────────


class ETCCONFIGCommand(Command):
    """Display /etc configuration files."""

    name = "etc-config"
    description = "Display /etc configuration files"
    category = "system"
    privileges = ["user"]

    CONFIG_FILES = {
        "passwd": "root:x:0:0:root:/root:/bin/bash\n"
                  "umer:x:1000:1000:UmerOS User:/home/umer:/bin/bash\n",
        "group": "root:x:0:\numer:x:1000:\nsudo:x:27:umer\n",
        "hosts": "127.0.0.1  localhost\n::1        localhost\n127.0.1.1  umeros\n",
        "fstab": "# <device>  <mount>  <type>  <options>  <dump>  <pass>\n"
                 "tmpfs       /tmp     tmpfs   defaults   0       0\n",
        "os-release": "NAME=\"UmerOS\"\nVERSION=\"1.0\"\nID=umeros\n"
                      "PRETTY_NAME=\"UmerOS 1.0\"\n",
    }

    def execute(self, *args):
        if args and args[0] in self.CONFIG_FILES:
            return self.CONFIG_FILES[args[0]]
        lines = ["/etc configuration files:\n"]
        for name, content in self.CONFIG_FILES.items():
            first_line = content.split("\n")[0][:50]
            lines.append(f"  {name:15s} - {first_line}")
        lines.append("\nUsage: etc-config <filename>")
        return "\n".join(lines) + "\n"


# ─── Shell Defaults ─────────────────────────────────────────────────────────


class BASHDEFAULTSCommand(Command):
    """Display bash default configuration."""

    name = "bash-defaults"
    description = "Display bash default configuration"
    category = "system"
    privileges = ["user"]

    DEFAULTS = {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": "/home/umer",
        "SHELL": "/bin/bash",
        "TERM": "xterm-256color",
        "LANG": "en_US.UTF-8",
        "EDITOR": "vim",
        "PS1": "\\u@\\h:\\w\\$ ",
        "HISTSIZE": "1000",
        "HISTFILESIZE": "2000",
    }

    def execute(self, *args):
        if args and args[0] in self.DEFAULTS:
            return f"{args[0]}={self.DEFAULTS[args[0]]}\n"
        lines = ["Bash defaults:\n"]
        for key, val in self.DEFAULTS.items():
            lines.append(f"  {key}={val}")
        lines.append(f"\nUsage: bash-defaults [variable]")
        return "\n".join(lines) + "\n"


# ─── Documentation ───────────────────────────────────────────────────────────


class HOWTOCommand(Command):
    """Display HOWTO documentation."""

    name = "howto"
    description = "Display HOWTO documentation"
    category = "system"
    privileges = ["user"]

    HOWTOS = {
        "networking": (
            "HOWTO: Networking\n"
            "=======================\n"
            "1. Configure interfaces in /etc/network/interfaces\n"
            "2. Use 'ip addr' to view interfaces\n"
            "3. Use 'ip route' to view routing table\n"
            "4. DNS resolution via /etc/resolv.conf\n"
            "5. Firewall: use iptables or nftables\n"
        ),
        "security": (
            "HOWTO: Security\n"
            "=====================\n"
            "1. Keep system updated: apt upgrade / yum update\n"
            "2. Use strong passwords and SSH keys\n"
            "3. Configure firewall (ufw, firewalld)\n"
            "4. Enable SELinux or AppArmor\n"
            "5. Audit with lynis: lynis audit system\n"
        ),
        "compiling": (
            "HOWTO: Compiling Software\n"
            "=========================\n"
            "1. ./configure --prefix=/usr/local\n"
            "2. make\n"
            "3. make install\n"
            "Alternative: check CMakeLists.txt for cmake builds\n"
        ),
        "permissions": (
            "HOWTO: File Permissions\n"
            "=======================\n"
            "rwxrwxrwx = owner, group, other\n"
            "chmod 755 file  -> rwxr-xr-x\n"
            "chmod 644 file  -> rw-r--r--\n"
            "chown user:group file\n"
            "Special: SUID(4), SGID(2), Sticky(1)\n"
        ),
    }

    def execute(self, *args):
        if not args:
            lines = ["Available HOWTOs:\n"]
            for topic in sorted(self.HOWTOS):
                first_line = self.HOWTOS[topic].split("\n")[1]
                lines.append(f"  {topic:15s} - {first_line}")
            lines.append("\nUsage: howto <topic>")
            return "\n".join(lines) + "\n"
        topic = args[0].lower()
        if topic in self.HOWTOS:
            return self.HOWTOS[topic]
        matches = [k for k in self.HOWTOS if topic in k]
        if matches:
            return f"howto: Did you mean: {', '.join(matches)}?\n"
        return f"howto: No HOWTO for '{topic}'. Use 'howto' to list available.\n"


class FAQCommand(Command):
    """Display FAQ documentation."""

    name = "faq"
    description = "Display FAQ documentation"
    category = "system"
    privileges = ["user"]

    FAQS = {
        "disk-full": (
            "Q: My disk is full, what do I do?\n"
            "A: 1. du -sh /* | sort -rh | head -20\n"
            "   2. Find large files: find / -size +100M\n"
            "   3. Clean package cache: apt clean\n"
            "   4. Remove old logs: journalctl --vacuum-time=7d\n"
        ),
        "slow-boot": (
            "Q: System boots slowly\n"
            "A: 1. systemd-analyze blame\n"
            "   2. systemd-analyze critical-chain\n"
            "   3. Disable unused services: systemctl disable <service>\n"
            "   4. Check dmesg for hardware issues\n"
        ),
        "no-internet": (
            "Q: No internet connection\n"
            "A: 1. ip addr show  (check interface is UP)\n"
            "   2. ping 8.8.8.8  (test connectivity)\n"
            "   3. cat /etc/resolv.conf  (check DNS)\n"
            "   4. ip route show  (check default gateway)\n"
            "   5. systemctl restart NetworkManager\n"
        ),
        "permission-denied": (
            "Q: Permission denied errors\n"
            "A: 1. ls -la <file>  (check ownership/permissions)\n"
            "   2. chmod +x <file>  (make executable)\n"
            "   3. sudo <command>  (run as root)\n"
            "   4. usermod -aG sudo <user>  (add to sudo group)\n"
        ),
    }

    def execute(self, *args):
        if not args:
            lines = ["Frequently Asked Questions:\n"]
            for topic in sorted(self.FAQS):
                first_line = self.FAQS[topic].split("\n")[0]
                lines.append(f"  {topic:20s} - {first_line}")
            lines.append("\nUsage: faq <topic>")
            return "\n".join(lines) + "\n"
        topic = args[0].lower().replace(" ", "-")
        if topic in self.FAQS:
            return self.FAQS[topic]
        matches = [k for k in self.FAQS if topic in k]
        if matches:
            return f"faq: Did you mean: {', '.join(matches)}?\n"
        return f"faq: No FAQ for '{topic}'. Use 'faq' to list available.\n"


# ─── Groff Macro Packages (FHS 3.0 §4.11) ────────────────────────────────────


class TMACCommand(Command):
    """Display groff macro packages."""

    name = "tmac"
    description = "Display groff macro package directory"
    category = "text"
    privileges = ["user"]

    MACROS = {
        "tmac.an": "Traditional man page macros\n"
                   "  .SH - section header\n"
                   "  .SS - subsection header\n"
                   "  .TP - tagged paragraph\n"
                   "  .IP - indented paragraph\n"
                   "  .B  - bold text\n"
                   "  .I  - italic text\n"
                   "  .BR - bold-roman-bold\n"
                   "  .PP - paragraph break\n",
        "tmac.mdoc": "BSD mdoc macros for man pages\n"
                     "  .Dd - document date\n"
                     "  .Dt - document title\n"
                     "  .Os - operating system\n"
                     "  .Sh - section\n"
                     "  .Ss - subsection\n"
                     "  .Nm - command name\n"
                     "  .Cd - configuration\n"
                     "  .It - list item\n",
        "tmac.mandoc": "Mandoc-compatible macros\n"
                       "  Compatible with both mdoc and man formats.\n"
                       "  Used by mandoc(1) for man page rendering.\n",
    }

    def execute(self, *args):
        if args and args[0] in self.MACROS:
            return f"{args[0]}:\n{self.MACROS[args[0]]}"
        lines = ["/usr/share/tmac/ - Groff macro packages:\n"]
        for name, desc in self.MACROS.items():
            first_line = desc.split("\n")[0]
            lines.append(f"  {name:20s} - {first_line}")
        lines.append("\nUsage: tmac <package>")
        return "\n".join(lines) + "\n"


class LocaleCommand(Command):
    """Display /usr/share/locale directory structure."""

    name = "usr-share-locale"
    description = "Display /usr/share/locale directory structure"
    category = "system"
    privileges = ["user"]

    def execute(self, *args):
        import locale
        try:
            lang, encoding = locale.getlocale()
        except (ValueError, AttributeError):  # [FIX H8]
            lang, encoding = "C", "ASCII"

        categories = {
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "LC_CTYPE": os.environ.get("LC_CTYPE", lang or "en_US.UTF-8"),
            "LC_NUMERIC": os.environ.get("LC_NUMERIC", lang or "en_US.UTF-8"),
            "LC_TIME": os.environ.get("LC_TIME", lang or "en_US.UTF-8"),
            "LC_COLLATE": os.environ.get("LC_COLLATE", lang or "en_US.UTF-8"),
            "LC_MONETARY": os.environ.get("LC_MONETARY", lang or "en_US.UTF-8"),
            "LC_MESSAGES": os.environ.get("LC_MESSAGES", lang or "en_US.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", ""),
        }

        if args and args[0] in categories:
            return f"{args[0]}={categories[args[0]]}\n"

        lines = ["Locale configuration:\n"]
        for cat, val in categories.items():
            lines.append(f"  {cat}={val}")
        lines.append(f"\n  Detected: {lang}.{encoding}")
        lines.append("  Usage: usr-share-locale [category]")
        return "\n".join(lines) + "\n"
