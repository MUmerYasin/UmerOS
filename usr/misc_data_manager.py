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
Misc Data Manager — Miscellaneous Architecture-Independent Data (/usr/share/misc)

FHS 3.0 Section 4.11.7: Miscellaneous architecture-independent files.

Manages:
- ASCII character set table
- Terminal capability database (termcap, termcap.db)
- File type identification magic numbers (/usr/share/file/magic)
- All 30+ spec-listed misc files (airport, birthtoken, eqnchar, etc.)
"""

import os
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path

# [FIX H296] Gate privileged /usr/share/misc filesystem mutation behind the
# zero-trust capability bridge. Writing system data files and creating the magic
# symlink are privileged operations that must require the `fs.admin` capability
# when a CapabilityManager is wired (fail-closed); when no manager is wired the
# gate stays permissive (warning) so existing flows keep working.
try:
    from core.capability_gate import gate, CAP_FS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    import sys
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_FS_ADMIN


class MiscFileType(Enum):
    """Types of miscellaneous data files."""
    ASCII = "ascii"
    TERMCAP = "termcap"
    TERMCAP_DB = "termcap.db"
    AIRPORT = "airport"
    BIRTHTOKEN = "birthtoken"
    EQNCHAR = "eqnchar"
    GETOPT = "getopt"
    GPROF_CALLG = "gprof.callg"
    GPROF_FLAT = "gprof.flat"
    INTER_PHONE = "inter.phone"
    IPFW_SAMP_FILTERS = "ipfw.samp.filters"
    IPFW_SAMP_SCRIPTS = "ipfw.samp.scripts"
    KEYCAP_PCVT = "keycap.pcvt"
    MAIL_HELP = "mail.help"
    MAIL_TILDEHELP = "mail.tildehelp"
    MAN_TEMPLATE = "man.template"
    MAP3270 = "map3270"
    MDOC_TEMPLATE = "mdoc.template"
    MORE_HELP = "more.help"
    NA_PHONE = "na.phone"
    NSLOOKUP_HELP = "nslookup.help"
    OPERATOR = "operator"
    SCSI_MODES = "scsi_modes"
    SENDMAIL_HF = "sendmail.hf"
    STYLE = "style"
    UNITS_LIB = "units.lib"
    VGRINDEFS = "vgrindefs"
    VGRINDEFS_DB = "vgrindefs.db"
    ZIPCODES = "zipcodes"
    MAGIC = "magic"
    CUSTOM = "custom"


class MiscDataStatus(IntEnum):
    """Status of misc data files."""
    MISSING = 0
    PRESENT = 1
    SYMLINK = 2
    CORRUPTED = 3


@dataclass
class MiscDataEntry:
    """Represents a miscellaneous data file."""
    name: str
    path: Path
    file_type: MiscFileType = MiscFileType.CUSTOM
    status: MiscDataStatus = MiscDataStatus.MISSING
    file_size: int = 0
    is_symlink: bool = False
    symlink_target: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "file_type": self.file_type.value,
            "status": self.status.value,
            "file_size": self.file_size,
            "is_symlink": self.is_symlink,
            "symlink_target": self.symlink_target,
            "description": self.description
        }


# FHS 3.0 descriptions for all spec-listed misc files
MISC_FILE_DESCRIPTIONS: Dict[MiscFileType, str] = {
    MiscFileType.ASCII: "ASCII character set table",
    MiscFileType.TERMCAP: "Terminal capability database (text format)",
    MiscFileType.TERMCAP_DB: "Compiled terminal capability database (db format)",
    MiscFileType.AIRPORT: "Airport IATA codes and names",
    MiscFileType.BIRTHTOKEN: "Birthday token data for fortune-like programs",
    MiscFileType.EQNCHAR: "Additional equation characters for eqn/roff",
    MiscFileType.GETOPT: "Option parsing template for getopt(1)",
    MiscFileType.GPROF_CALLG: "Call graph data for gprof profiling",
    MiscFileType.GPROF_FLAT: "Flat profile data for gprof profiling",
    MiscFileType.INTER_PHONE: "International telephone area codes",
    MiscFileType.IPFW_SAMP_FILTERS: "IP firewall sample filter rules",
    MiscFileType.IPFW_SAMP_SCRIPTS: "IP firewall sample scripts",
    MiscFileType.KEYCAP_PCVT: "PC VT terminal keycap definitions",
    MiscFileType.MAIL_HELP: "Help text for mail(1) user agent",
    MiscFileType.MAIL_TILDEHELP: "Tilde escape help for mail(1)",
    MiscFileType.MAN_TEMPLATE: "Template for generating man pages",
    MiscFileType.MAP3270: "3270 terminal keymap",
    MiscFileType.MDOC_TEMPLATE: "Template for mdoc(7) man pages",
    MiscFileType.MORE_HELP: "Help text for more(1) pager",
    MiscFileType.NA_PHONE: "North American telephone area codes",
    MiscFileType.NSLOOKUP_HELP: "Help text for nslookup(8)",
    MiscFileType.OPERATOR: "Keyboard operator character definitions",
    MiscFileType.SCSI_MODES: "SCSI device mode page definitions",
    MiscFileType.SENDMAIL_HF: "Help file for sendmail(8)",
    MiscFileType.STYLE: "Writing style guide reference",
    MiscFileType.UNITS_LIB: "Units conversion definitions for units(1)",
    MiscFileType.VGRINDEFS: "Language definitions for vgrind(1)",
    MiscFileType.VGRINDEFS_DB: "Compiled vgrind language definitions (db format)",
    MiscFileType.ZIPCODES: "ZIP/postal code database",
    MiscFileType.MAGIC: "File type identification magic numbers (symlink to /usr/share/file/magic)",
}

# Canonical file content generators for each misc file type
_CONTENT_GENERATORS: Dict[MiscFileType, Any] = {}


def _register_generator(ft: MiscFileType):
    """Decorator to register a content generator for a MiscFileType."""
    def wrapper(fn):
        _CONTENT_GENERATORS[ft] = fn
        return fn
    return wrapper


@_register_generator(MiscFileType.ASCII)
def _gen_ascii() -> str:
    lines = ["# ASCII character set table", "# Value  Oct   Dec   Hex   Char"]
    for i in range(128):
        c = chr(i) if 32 <= i < 127 else " "
        lines.append(f"# {i:3d}  {i:04o}  {i:3d}  0x{i:02X}  {c}")
    return "\n".join(lines) + "\n"


@_register_generator(MiscFileType.AIRPORT)
def _gen_airport() -> str:
    return (
        "# Airport IATA codes\n"
        "# Code  City/Location\n"
        "ATL  Atlanta\n"
        "BOS  Boston\n"
        "CHI  Chicago\n"
        "DFW  Dallas/Fort Worth\n"
        "JFK  New York (John F. Kennedy)\n"
        "LAX  Los Angeles\n"
        "LHR  London (Heathrow)\n"
        "NRT  Tokyo (Narita)\n"
        "ORD  Chicago (O'Hare)\n"
        "SFO  San Francisco\n"
    )


@_register_generator(MiscFileType.NA_PHONE)
def _gen_na_phone() -> str:
    return (
        "# North American telephone area codes\n"
        "# AreaCode  Location\n"
        "201  New Jersey\n"
        "202  Washington, DC\n"
        "203  Connecticut\n"
        "206  Washington (Seattle)\n"
        "207  Maine\n"
        "208  Idaho\n"
        "209  California (Stockton)\n"
        "210  Texas (San Antonio)\n"
        "212  New York (Manhattan)\n"
        "213  California (Los Angeles)\n"
    )


@_register_generator(MiscFileType.INTER_PHONE)
def _gen_inter_phone() -> str:
    return (
        "# International telephone codes\n"
        "# CountryCode  Country\n"
        "1  United States / Canada\n"
        "44  United Kingdom\n"
        "49  Germany\n"
        "33  France\n"
        "81  Japan\n"
        "86  China\n"
        "91  India\n"
        "7  Russia\n"
        "55  Brazil\n"
        "52  Mexico\n"
    )


@_register_generator(MiscFileType.GETOPT)
def _gen_getopt() -> str:
    return (
        "# getopt(1) option parsing template\n"
        "# Usage: getopt optstring parameters\n"
        "# Example:\n"
        "#   getopt \"ab:c\" -- -a -b foo -c\n"
        "# Outputs: -a -b foo -c --\n"
    )


@_register_generator(MiscFileType.EQNCHAR)
def _gen_eqnchar() -> str:
    return (
        "# Additional equation characters for eqn/roff\n"
        "# These are defined as special characters for mathematical typesetting\n"
        "alpha  \\(*a\n"
        "beta   \\(*b\n"
        "gamma  \\(*g\n"
        "delta  \\(*d\n"
        "epsilon \\(*e\n"
        "zeta   \\(*z\n"
        "eta    \\(*h\n"
        "theta  \\(*q\n"
        "iota   \\(*i\n"
        "kappa  \\(*k\n"
        "lambda \\(*l\n"
        "mu     \\(*m\n"
    )


@_register_generator(MiscFileType.OPERATOR)
def _gen_operator() -> str:
    return (
        "# Keyboard operator character definitions\n"
        "# These define the visual representation of keyboard operators\n"
        "logical_and  &\n"
        "logical_or   |\n"
        "logical_not  !\n"
        "logical_xor  ^\n"
        "bitwise_and  &\n"
        "bitwise_or   |\n"
        "bitwise_not  ~\n"
        "bitwise_xor  ^\n"
        "left_shift   <<\n"
        "right_shift  >>\n"
    )


@_register_generator(MiscFileType.STYLE)
def _gen_style() -> str:
    return (
        "# Writing style guide reference\n"
        "# This file contains writing conventions for documentation\n"
        "# Use simple, direct language\n"
        "# Prefer active voice over passive voice\n"
        "# Keep sentences short and clear\n"
        "# Use consistent terminology throughout\n"
    )


@_register_generator(MiscFileType.MAIL_HELP)
def _gen_mail_help() -> str:
    return (
        "UmerOS Mail Help\n"
        "================\n"
        "Type 'h' for help.\n"
        "Type 'q' to quit.\n"
        "Type 'd' to delete a message.\n"
        "Type 's' to save a message.\n"
        "Type 'r' to reply to a message.\n"
    )


@_register_generator(MiscFileType.MAIL_TILDEHELP)
def _gen_mail_tildehelp() -> str:
    return (
        "Mail Tilde Escapes\n"
        "==================\n"
        "~.       End of message\n"
        "~q       Quit without sending\n"
        "~r file  Read file into message\n"
        "~w file  Write message to file\n"
        "~h       Edit headers\n"
        "~?       Help on tilde escapes\n"
    )


@_register_generator(MiscFileType.MORE_HELP)
def _gen_more_help() -> str:
    return (
        "More Help\n"
        "=========\n"
        "SPACE     Next page\n"
        "ENTER     Next line\n"
        "b         Previous page\n"
        "/pattern  Search for pattern\n"
        "n         Next match\n"
        "q         Quit\n"
        "h         Help\n"
    )


@_register_generator(MiscFileType.NSLOOKUP_HELP)
def _gen_nslookup_help() -> str:
    return (
        "Nslookup Help\n"
        "=============\n"
        "nslookup - query DNS servers interactively\n"
        "Usage: nslookup [host] [server]\n"
        "Commands:\n"
        "  exit          Exit nslookup\n"
        "  help          Show help\n"
        "  server addr   Set default server\n"
        "  set option    Set query options\n"
    )


@_register_generator(MiscFileType.SENDMAIL_HF)
def _gen_sendmail_hf() -> str:
    return (
        "Sendmail Help\n"
        "=============\n"
        "sendmail - send mail over the internet\n"
        "Usage: sendmail [flags] [recipients]\n"
        "Common flags:\n"
        "  -bm     Read message from stdin\n"
        "  -bs     Use SMTP protocol on stdin\n"
        "  -f addr Set sender address\n"
        "  -v      Verbose mode\n"
    )


@_register_generator(MiscFileType.GPROF_CALLG)
def _gen_gprof_callg() -> str:
    return (
        "# gprof call graph output\n"
        "# Call graph\n"
        "#index  subroutine\n"
        "#[1]    main\n"
        "#        called: [2] _start\n"
        "#        calls: [3] func_a\n"
        "#                 [4] func_b\n"
    )


@_register_generator(MiscFileType.GPROF_FLAT)
def _gen_gprof_flat() -> str:
    return (
        "# gprof flat profile output\n"
        "# Flat profile\n"
        "index  %time  cumulative  self  self+desc  calls  name\n"
        "[1]    45.0   0.100       0.100  0.100      100    main\n"
        "[2]    30.0   0.167       0.067  0.067      500    func_a\n"
        "[3]    25.0   0.222       0.056  0.056      500    func_b\n"
    )


@_register_generator(MiscFileType.KEYCAP_PCVT)
def _gen_keycap_pcvt() -> str:
    return (
        "# PC VT terminal keycap definitions\n"
        "# Key capabilities for VT100/VT220 compatible terminals\n"
        "kcuu1=\\EOA:  cursor up\n"
        "kcud1=\\EOB:  cursor down\n"
        "kcuf1=\\EOC:  cursor forward\n"
        "kcub1=\\EOD:  cursor backward\n"
        "khome=\\EOH:  home\n"
        "kend=\\EOM:   end\n"
        "kich1=\\E[2~: insert\n"
        "kdch1=\\E[3~: delete\n"
    )


@_register_generator(MiscFileType.MAP3270)
def _gen_map3270() -> str:
    return (
        "# 3270 terminal keymap\n"
        "# Maps local keys to 3270 terminal functions\n"
        "PF1=\\nOP\n"
        "PF2=\\nOQ\n"
        "PF3=\\nOR\n"
        "PF4=\\nOS\n"
        "PA1=\\n[15~\n"
        "PA2=\\n[17~\n"
        "PA3=\\n[18~\n"
        "Clear=\\n[29~\n"
    )


@_register_generator(MiscFileType.SCSI_MODES)
def _gen_scsi_modes() -> str:
    return (
        "# SCSI device mode page definitions\n"
        "# Mode page  Supported  Description\n"
        "0x01  y  Read-Write Error Recovery\n"
        "0x02  y  Disconnect-Reconnect\n"
        "0x03  y  Format Device\n"
        "0x04  n  Rigid Disk Geometry\n"
        "0x05  y  Flexible Disk Geometry\n"
        "0x08  y  Caching\n"
        "0x0A  y  Control Mode\n"
        "0x19  n  CD-ROM Capabilities\n"
        "0x2A  n  CD-ROM Audio Control\n"
    )


@_register_generator(MiscFileType.UNITS_LIB)
def _gen_units_lib() -> str:
    return (
        "# Units conversion definitions for units(1)\n"
        "# Unit    Description\n"
        "meter      length\n"
        "kilogram   mass\n"
        "second     time\n"
        "ampere     electric current\n"
        "kelvin     temperature\n"
        "mole       amount of substance\n"
        "luminous_intensity  luminous intensity\n"
    )


@_register_generator(MiscFileType.VGRINDEFS)
def _gen_vgrindefs() -> str:
    return (
        "# Language definitions for vgrind(1)\n"
        "# language  keywords  stringchars  comment  padding\n"
        "c  \"\"  \\\\  \\\\/\\\\/  0\n"
        "pascal  \"\"  {}  {\\*}  0\n"
        "fortran  \"\"  {}  c  0\n"
        "lisp  \"\"  ()  ;;  0\n"
    )


@_register_generator(MiscFileType.MAN_TEMPLATE)
def _gen_man_template() -> str:
    return (
        '.TH "PROGRAM_NAME" 1 "YYYY-MM-DD" "Version 1.0" "User Commands"\n'
        '.SH NAME\n'
        'program_name \\- brief description\n'
        '.SH SYNOPSIS\n'
        '.B program_name\n'
        '.IR option .\|..\n'
        '.SH DESCRIPTION\n'
        '.B program_name\n'
        'does something useful.\n'
        '.SH OPTIONS\n'
        '.TP\n'
        '.B \\-h, \\-\\-help\n'
        'Show help.\n'
        '.SH SEE ALSO\n'
        '.BR ls (1),\n'
        '.BR cat (1)\n'
    )


@_register_generator(MiscFileType.MDOC_TEMPLATE)
def _gen_mdoc_template() -> str:
    return (
        '.Dd YYYY-MM-DD\n'
        '.Dt PROGRAM_NAME 1\n'
        '.Os UmerOS 1.0\n'
        '.Sh NAME\n'
        '.Nm program_name\n'
        '.Nd brief description\n'
        '.Sh SYNOPSIS\n'
        '.Nm\n'
        '.Op Ar options\n'
        '.Op Ar file .\|..\n'
        '.Sh DESCRIPTION\n'
        '.Nm\n'
        'does something useful.\n'
        '.Sh OPTIONS\n'
        '.It Fl h, \\-help\n'
        'Show help.\n'
        '.Sh SEE ALSO\n'
        '.Xr ls 1 ,\n'
        '.Xr cat 1\n'
    )


@_register_generator(MiscFileType.BIRTHTOKEN)
def _gen_birthtoken() -> str:
    return (
        "# Birthday token data\n"
        "# Token  Month  Day  Meaning\n"
        "TODAY  0  0  Today's date token\n"
    )


@_register_generator(MiscFileType.ZIPCODES)
def _gen_zipcodes() -> str:
    return (
        "# ZIP/postal codes\n"
        "# ZIPCode  City  State\n"
        "00501  Holtsville  NY\n"
        "00544  Holtsville  NY\n"
        "02134  Boston  MA\n"
        "90210  Beverly Hills  CA\n"
        "10001  New York  NY\n"
    )


@_register_generator(MiscFileType.TERMCAP)
def _gen_termcap() -> str:
    return (
        "# Terminal capability database (text format)\n"
        "# Terminal name  |  capabilities  :  tc=base_terminal\n"
        "vt100|DEC VT100:\
:do=\\E[B:\
:co#80:\
:li#24:\
:cl=\\E[2J\\E[H:\
:cm=\\E[%i%d;%dH:\n"
    )


@_register_generator(MiscFileType.IPFW_SAMP_FILTERS)
def _gen_ipfw_samp_filters() -> str:
    return (
        "# IP firewall sample filter rules\n"
        "# Allow all outgoing traffic\n"
        "allow ip from any to any\n"
        "# Block incoming SSH from specific IP\n"
        "deny tcp from 192.168.1.100 to any dst-port 22\n"
    )


@_register_generator(MiscFileType.IPFW_SAMP_SCRIPTS)
def _gen_ipfw_samp_scripts() -> str:
    return (
        "# IP firewall sample scripts\n"
        "#!/bin/sh\n"
        "# Flush existing rules\n"
        "ipfw -f flush\n"
        "# Allow all outgoing\n"
        "ipfw add allow ip from any to any out\n"
        "# Deny incoming SSH\n"
        "ipfw add deny tcp from any to any dst-port 22 in\n"
    )


class MiscDataManager:
    """Manages /usr/share/misc data per FHS 3.0."""

    BASE_DIR = Path("/usr/share/misc")
    MAGIC_SYMLINK = Path("/usr/share/misc/magic")
    MAGIC_REAL = Path("/usr/share/file/magic")

    # Known misc file types
    FILE_TYPE_MAP = {
        "ascii": MiscFileType.ASCII,
        "termcap": MiscFileType.TERMCAP,
        "termcap.db": MiscFileType.TERMCAP_DB,
        "airport": MiscFileType.AIRPORT,
        "birthtoken": MiscFileType.BIRTHTOKEN,
        "eqnchar": MiscFileType.EQNCHAR,
        "getopt": MiscFileType.GETOPT,
        "gprof.callg": MiscFileType.GPROF_CALLG,
        "gprof.flat": MiscFileType.GPROF_FLAT,
        "inter.phone": MiscFileType.INTER_PHONE,
        "ipfw.samp.filters": MiscFileType.IPFW_SAMP_FILTERS,
        "ipfw.samp.scripts": MiscFileType.IPFW_SAMP_SCRIPTS,
        "keycap.pcvt": MiscFileType.KEYCAP_PCVT,
        "mail.help": MiscFileType.MAIL_HELP,
        "mail.tildehelp": MiscFileType.MAIL_TILDEHELP,
        "man.template": MiscFileType.MAN_TEMPLATE,
        "map3270": MiscFileType.MAP3270,
        "mdoc.template": MiscFileType.MDOC_TEMPLATE,
        "more.help": MiscFileType.MORE_HELP,
        "na.phone": MiscFileType.NA_PHONE,
        "nslookup.help": MiscFileType.NSLOOKUP_HELP,
        "operator": MiscFileType.OPERATOR,
        "scsi_modes": MiscFileType.SCSI_MODES,
        "sendmail.hf": MiscFileType.SENDMAIL_HF,
        "style": MiscFileType.STYLE,
        "units.lib": MiscFileType.UNITS_LIB,
        "vgrindefs": MiscFileType.VGRINDEFS,
        "vgrindefs.db": MiscFileType.VGRINDEFS_DB,
        "zipcodes": MiscFileType.ZIPCODES,
        "magic": MiscFileType.MAGIC,
    }

    def __init__(self):
        self._entries: Dict[str, MiscDataEntry] = {}
        self._types: Dict[str, List[str]] = {}
        self._refresh()

    def _refresh(self):
        """Refresh misc data cache."""
        self._entries.clear()
        self._types.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        for entry_path in sorted(self.BASE_DIR.iterdir()):
            if entry_path.is_file() or entry_path.is_symlink():
                entry = self._create_entry(entry_path)
                self._entries[entry.name] = entry
                ft = entry.file_type.value
                if ft not in self._types:
                    self._types[ft] = []
                self._types[ft].append(entry.name)

    def _create_entry(self, path: Path) -> MiscDataEntry:
        """Create a MiscDataEntry for a path."""
        name = path.name
        file_type = self.FILE_TYPE_MAP.get(name, MiscFileType.CUSTOM)

        status = MiscDataStatus.MISSING
        file_size = 0
        is_symlink = path.is_symlink()
        symlink_target = None

        if is_symlink:
            status = MiscDataStatus.SYMLINK
            symlink_target = str(path.resolve())
        elif path.exists():
            file_size = path.stat().st_size
            if file_size >= 0:
                status = MiscDataStatus.PRESENT

        description = MISC_FILE_DESCRIPTIONS.get(file_type, "")

        return MiscDataEntry(
            name=name,
            path=path,
            file_type=file_type,
            status=status,
            file_size=file_size,
            is_symlink=is_symlink,
            symlink_target=symlink_target,
            description=description
        )

    def list_entries(self) -> List[MiscDataEntry]:
        """List all misc data entries."""
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[MiscDataEntry]:
        """Get a specific misc data entry."""
        return self._entries.get(name)

    def has_entry(self, name: str) -> bool:
        """Check if a misc data entry exists."""
        return name in self._entries

    def get_types(self) -> List[str]:
        """Get all file types."""
        return sorted(self._types.keys())

    def get_entries_by_type(self, file_type: MiscFileType) -> List[MiscDataEntry]:
        """Get all entries of a specific type."""
        names = self._types.get(file_type.value, [])
        return [self._entries[n] for n in names if n in self._entries]

    def create_misc_file(self, name: str, file_type: Optional[MiscFileType] = None) -> Optional[MiscDataEntry]:
        """Create a misc data file with real functional content.

        Args:
            name: Filename (e.g., "ascii", "airport")
            file_type: Optional type override; auto-detected from name if None

        Returns:
            MiscDataEntry if created, None on failure
        """
        # [FIX H296] privileged write into /usr/share/misc -> requires fs.admin.
        gate.require(CAP_FS_ADMIN)
        if file_type is None:
            file_type = self.FILE_TYPE_MAP.get(name, MiscFileType.CUSTOM)

        generator = _CONTENT_GENERATORS.get(file_type)
        if generator is None:
            return None

        try:
            path = self.BASE_DIR / name
            content = generator()
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self._refresh()
            return self._entries.get(name)
        except Exception:
            return None

    def create_magic_symlink(self) -> bool:
        """Create /usr/share/misc/magic → /usr/share/file/magic symlink.

        Per FHS 3.0, the magic(5) file may live in /usr/share/file/magic
        with a compatibility symlink at /usr/share/misc/magic.
        """
        # [FIX H296] privileged symlink + file writes -> requires fs.admin.
        gate.require(CAP_FS_ADMIN)
        try:
            self.MAGIC_REAL.parent.mkdir(parents=True, exist_ok=True)

            if not self.MAGIC_REAL.exists():
                content = (
                    "# UmerOS magic file type database\n"
                    "# This file is used by file(1) to identify file types\n"
                    "\n"
                    "# Archive formats\n"
                    ":0[0:4]    \\x1f\\x8b  gzip compressed data\n"
                    ":0[0:4]    \\x50\\x4b\\x03\\x04  Zip archive data\n"
                    ":0[0:3]    BZh  bzip2 compressed data\n"
                    ":0[0:6]    \\xfd7zXZ\\x00  XZ compressed data\n"
                    "\n"
                    "# Executables\n"
                    ":0[0:4]    \\x7fELF  ELF executable\n"
                    ":0[0:2]    MZ  MS-DOS executable\n"
                    ":0[0:4]    \\xca\\xfe\\xba\\xbe  Mach-O binary (Fat)\n"
                    "\n"
                    "# Documents\n"
                    ":0[0:5]    %PDF-  PDF document\n"
                    ":0[0:4]    \\xd0\\xcf\\x11\\xe0  OLE2 compound document\n"
                    "\n"
                    "# Images\n"
                    ":0[0:3]    \\xff\\xd8\\xff  JPEG image data\n"
                    ":0[0:4]    \\x89PNG  PNG image data\n"
                    ":0[0:4]    GIF8  GIF image data\n"
                    ":0[0:4]    RIFF  RIFF (e.g. WebP, WAV)\n"
                    "\n"
                    "# Audio\n"
                    ":0[0:4]    fLaC  FLAC audio\n"
                    ":0[0:4]    ID3  MP3 audio (ID3v2)\n"
                    "\n"
                    "# Video\n"
                    ":0[0:3]    \\x1a\\x45\\xdf\\xa3  Matroska/WebM video\n"
                    ":0[0:4]    \\x00\\x00\\x00\\x1c\\x66\\x74\\x79\\x70  MP4 video\n"
                    "\n"
                    "# Text\n"
                    ":0[0:4]    \\xef\\xbb\\xbf  UTF-8 Unicode text (BOM)\n"
                    ":0[0:2]    \\xff\\xfe  UTF-16LE text (BOM)\n"
                    ":0[0:2]    \\xfe\\xff  UTF-16BE text (BOM)\n"
                )
                with open(self.MAGIC_REAL, 'w', encoding='utf-8') as f:
                    f.write(content)

            if self.MAGIC_SYMLINK.exists() or self.MAGIC_SYMLINK.is_symlink():
                if self.MAGIC_SYMLINK.is_symlink():
                    target = os.readlink(str(self.MAGIC_SYMLINK))
                    if target == str(self.MAGIC_REAL):
                        return True
                    self.MAGIC_SYMLINK.unlink()
                elif self.MAGIC_SYMLINK.is_file():
                    self.MAGIC_SYMLINK.unlink()

            os.symlink(str(self.MAGIC_REAL), str(self.MAGIC_SYMLINK))
            self._refresh()
            return self.MAGIC_SYMLINK.is_symlink()
        except Exception:
            return False

    def read_misc_file(self, name: str) -> Optional[str]:
        """Read the contents of a misc data file.

        Args:
            name: Filename to read

        Returns:
            File content as string, or None if not found/readable
        """
        entry = self.get_entry(name)
        if entry is None:
            return None
        try:
            if entry.path.is_symlink():
                target = Path(entry.path.resolve())
                if target.exists() and target.is_file():
                    return target.read_text(encoding='utf-8')
                return None
            if entry.path.exists():
                return entry.path.read_text(encoding='utf-8')
            return None
        except Exception:
            return None

    def delete_misc_file(self, name: str) -> bool:
        """Delete a misc data file.

        Args:
            name: Filename to delete

        Returns:
            True if deleted successfully
        """
        # [FIX H296] privileged unlink -> requires fs.admin.
        gate.require(CAP_FS_ADMIN)
        try:
            entry = self.get_entry(name)
            if entry is None:
                return False
            if entry.path.exists() or entry.path.is_symlink():
                entry.path.unlink()
                self._refresh()
                return True
            return False
        except Exception:
            return False

    def add_entry(self, name: str, content: str = "") -> bool:
        """Add a new misc data file with raw content.

        For files with spec-defined content, use create_misc_file() instead.
        """
        # [FIX H296] privileged write into /usr/share/misc -> requires fs.admin.
        gate.require(CAP_FS_ADMIN)
        try:
            path = self.BASE_DIR / name
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self._refresh()
            return True
        except Exception:
            return False

    def remove_entry(self, name: str) -> bool:
        """Remove a misc data file (alias for delete_misc_file)."""
        return self.delete_misc_file(name)

    def has_magic_symlink(self) -> bool:
        """Check if /usr/share/misc/magic → /usr/share/file/magic exists."""
        return self.MAGIC_SYMLINK.is_symlink()

    def get_magic_target(self) -> Optional[str]:
        """Get the target of the magic symlink."""
        if self.MAGIC_SYMLINK.is_symlink():
            return str(self.MAGIC_SYMLINK.resolve())
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get misc data manager status."""
        symlinks = sum(1 for e in self._entries.values()
                       if e.status == MiscDataStatus.SYMLINK)
        total_size = sum(e.file_size for e in self._entries.values())

        return {
            "base_dir": str(self.BASE_DIR),
            "exists": self.BASE_DIR.exists(),
            "total_entries": len(self._entries),
            "symlinks": symlinks,
            "total_size": total_size,
            "types": self.get_types()
        }


# Singleton instance
misc_data_manager = MiscDataManager()
