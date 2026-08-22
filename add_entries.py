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

import re

# Read current bin_manager.py
with open('bin/bin_manager.py', 'r') as f:
    content = f.read()

# New entries to add
new_entries = '''    # usr_cmds.py — 115 new TLDP/usr utilities
    "addr2line": ("usr_cmds", "Addr2lineCommand"),
    "apropos": ("usr_cmds", "AproposCommand"),
    "aptget": ("usr_cmds", "AptGetCommand"),
    "ar": ("usr_cmds", "ArCommand"),
    "as": ("usr_cmds", "AsCommand"),
    "at": ("usr_cmds", "AtCommand"),
    "atq": ("usr_cmds", "AtqCommand"),
    "atrm": ("usr_cmds", "AtrmCommand"),
    "b2sum": ("usr_cmds", "B2sumCommand"),
    "base32": ("usr_cmds", "Base32Command"),
    "base64": ("usr_cmds", "Base64Command"),
    "bison": ("usr_cmds", "BisonCommand"),
    "bzip2": ("usr_cmds", "Bzip2Command"),
    "cksum": ("usr_cmds", "CksumCommand"),
    "clear": ("usr_cmds", "ClearCommand"),
    "column": ("usr_cmds", "ColumnCommand"),
    "comm": ("usr_cmds", "CommCommand"),
    "cpp": ("usr_cmds", "CppCommand"),
    "crontab": ("usr_cmds", "CrontabCommand"),
    "csplit": ("usr_cmds", "CsplitCommand"),
    "ctags": ("usr_cmds", "CtagsCommand"),
    "curl": ("usr_cmds", "CurlCommand"),
    "dig": ("usr_cmds", "DigCommand"),
    "dnf": ("usr_cmds", "DnfCommand"),
    "dpkg": ("usr_cmds", "DpkgCommand"),
    "dpkgdeb": ("usr_cmds", "DpkgDebCommand"),
    "dpkgquery": ("usr_cmds", "DpkgQueryCommand"),
    "emacs": ("usr_cmds", "EmacsCommand"),
    "etags": ("usr_cmds", "EtagsCommand"),
    "expand": ("usr_cmds", "ExpandCommand"),
    "flex": ("usr_cmds", "FlexCommand"),
    "fmt": ("usr_cmds", "FmtCommand"),
    "gcc": ("usr_cmds", "GccCommand"),
    "getconf": ("usr_cmds", "GetconfCommand"),
    "getent": ("usr_cmds", "GetentCommand"),
    "gprof": ("usr_cmds", "GprofCommand"),
    "hexdump": ("usr_cmds", "HexdumpCommand"),
    "host": ("usr_cmds", "HostCommand"),
    "hostid": ("usr_cmds", "HostidCommand"),
    "iconv": ("usr_cmds", "IconvCommand"),
    "install": ("usr_cmds", "InstallCommand"),
    "installinfo": ("usr_cmds", "InstallInfoCommand"),
    "iostat": ("usr_cmds", "IostatCommand"),
    "join": ("usr_cmds", "JoinCommand"),
    "ld": ("usr_cmds", "LdCommand"),
    "locale": ("usr_cmds", "LocaleCommand"),
    "localedef": ("usr_cmds", "LocaledefCommand"),
    "logname": ("usr_cmds", "LognameCommand"),
    "lsbrelease": ("usr_cmds", "LsbReleaseCommand"),
    "lsof": ("usr_cmds", "LsofCommand"),
    "lsofnetwork": ("usr_cmds", "LsofNetworkCommand"),
    "ltrace": ("usr_cmds", "LtraceCommand"),
    "lzma": ("usr_cmds", "LzmaCommand"),
    "m4": ("usr_cmds", "M4Command"),
    "make": ("usr_cmds", "MakeCommand"),
    "makeinfo": ("usr_cmds", "MakeinfoCommand"),
    "man": ("usr_cmds", "ManCommand"),
    "md5sum": ("usr_cmds", "Md5sumCommand"),
    "nano": ("usr_cmds", "NanoCommand"),
    "nc": ("usr_cmds", "NcCommand"),
    "ncat": ("usr_cmds", "NcatCommand"),
    "nm": ("usr_cmds", "NmCommand"),
    "nproc": ("usr_cmds", "NprocCommand"),
    "nslookup": ("usr_cmds", "NslookupCommand"),
    "numfmt": ("usr_cmds", "NumfmtCommand"),
    "objcopy": ("usr_cmds", "ObjcopyCommand"),
    "objdump": ("usr_cmds", "ObjdumpCommand"),
    "od": ("usr_cmds", "OdCommand"),
    "paste": ("usr_cmds", "PasteCommand"),
    "pico": ("usr_cmds", "PicoCommand"),
    "pmap": ("usr_cmds", "PmapCommand"),
    "pr": ("usr_cmds", "PrCommand"),
    "pstree": ("usr_cmds", "PstreeCommand"),
    "ptx": ("usr_cmds", "PtxCommand"),
    "pwdx": ("usr_cmds", "PwdxCommand"),
    "ranlib": ("usr_cmds", "RanlibCommand"),
    "readelf": ("usr_cmds", "ReadelfCommand"),
    "reset": ("usr_cmds", "ResetCommand"),
    "rpm": ("usr_cmds", "RpmCommand"),
    "runuser": ("usr_cmds", "RunuserCommand"),
    "script": ("usr_cmds", "ScriptCommand"),
    "scriptreplay": ("usr_cmds", "ScriptreplayCommand"),
    "sha1sum": ("usr_cmds", "Sha1sumCommand"),
    "sha256sum": ("usr_cmds", "Sha256sumCommand"),
    "sha512sum": ("usr_cmds", "Sha512sumCommand"),
    "shred": ("usr_cmds", "ShredCommand"),
    "shuf": ("usr_cmds", "ShufCommand"),
    "size": ("usr_cmds", "SizeCommand"),
    "socat": ("usr_cmds", "SocatCommand"),
    "split": ("usr_cmds", "SplitCommand"),
    "strip": ("usr_cmds", "StripCommand"),
    "sudo": ("usr_cmds", "SudoCommand"),
    "sum": ("usr_cmds", "SumCommand"),
    "tabs": ("usr_cmds", "TabsCommand"),
    "tcpdump": ("usr_cmds", "TcpdumpCommand"),
    "testbrace": ("usr_cmds", "TestBraceCommand"),
    "tput": ("usr_cmds", "TputCommand"),
    "tracepath": ("usr_cmds", "TracepathCommand"),
    "tree": ("usr_cmds", "TreeCommand"),
    "tty": ("usr_cmds", "TtyCommand"),
    "unexpand": ("usr_cmds", "UnexpandCommand"),
    "unzip": ("usr_cmds", "UnzipCommand"),
    "valgrind": ("usr_cmds", "ValgrindCommand"),
    "vim": ("usr_cmds", "VimCommand"),
    "vmstat": ("usr_cmds", "VmstatCommand"),
    "watch": ("usr_cmds", "WatchCommand"),
    "wget": ("usr_cmds", "WgetCommand"),
    "whatis": ("usr_cmds", "WhatisCommand"),
    "who": ("usr_cmds", "WhoCommand"),
    "xdgopen": ("usr_cmds", "XdgOpenCommand"),
    "xdguserdirs": ("usr_cmds", "XdgUserDirsCommand"),
    "xz": ("usr_cmds", "XzCommand"),
    "yum": ("usr_cmds", "YumCommand"),
    "zip": ("usr_cmds", "ZipCommand"),
    "zstd": ("usr_cmds", "ZstdCommand"),
'''

# Insert before the closing } of COMMAND_REGISTRY
old_end = '    "updatedb": ("usr_commands", "UpdatedbCommand"),\n}'
new_end = '    "updatedb": ("usr_commands", "UpdatedbCommand"),\n' + new_entries + '}'

if old_end in content:
    content = content.replace(old_end, new_end)
    with open('bin/bin_manager.py', 'w') as f:
        f.write(content)
    print("SUCCESS: Added 115 entries to COMMAND_REGISTRY")
else:
    print("ERROR: Could not find insertion point")
