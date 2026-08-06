"""
UmerOS /bin Hierarchy Manager
==============================
Central registry for /bin essential command binaries.

According to FHS 3.0 / TLDP:
  - /bin contains essential command binaries required for booting, restoring,
    recovering, and/or repairing the system in addition to binaries in /usr/bin.
  - /bin must be statically linked (LSB).
  - No subdirectories allowed in /bin.
  - Essential for both root and non-privileged users.

Required /bin commands (FSSTND):
  cat, chgrp, chmod, chown, cp, date, dd, df, dmesg, echo, false, hostname,
  kill, ln, login, ls, mkdir, mknod, more, mount, mv, ps, pwd, rm, rmdir,
  sh, stty, su, sync, true, umount, uname

Module Registry:
  - essential_commands.py: CatCommand, CpCommand, MvCommand, RmCommand, LsCommand,
    MkdirCommand, RmdirCommand, LnCommand, DdCommand, MoreCommand
  - permissions.py: ChmodCommand, ChownCommand, ChgrpCommand
  - system_info.py: UnameCommand, DmesgCommand, HostnameCommand, DfCommand,
    EchoCommand, DateCommand, PwdCommand
  - process.py: PsCommand, KillCommand, MountCommand, UmountCommand,
    SttyCommand, SyncCommand
  - user_commands.py: SuCommand, LoginCommand
  - boolean_ops.py: TrueCommand, FalseCommand, TestCommand, BracketTestCommand,
    YesCommand, PrintenvCommand, EnvCommand
  - shell.py: ShCommand, SedCommand, GzipCommand, GunzipCommand, ZcatCommand,
    NetstatCommand, PingCommand
  - device.py: MknodCommand
  - archive.py: TarCommand
  - network_cmds.py: IfconfigCommand, IpCommand, RouteCommand, ArpCommand
  - csh.py: CshCommand
  - ed.py: EdCommand
  - usr_commands.py: 60+ utilities (cpio, fold, nohup, grep, less, find, awk,
    diff, du, file, stat, free, w, uptime, pkill, pgrep, useradd, usermod,
    userdel, groupadd, groupdel, groupmod, chfn, chsh, chage, gpasswd,
    newgrp, mesg, last, lastlog, patch, locate, updatedb, and more)
"""

from __future__ import annotations

import importlib
import os
import stat
import sys
import time
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ─── Constants ───────────────────────────────────────────────────────────────

BIN_PATH = "/bin"
SBIN_PATH = "/sbin"

# FHS 3.0 Required /bin commands
FHS_REQUIRED_BIN: List[str] = [
    "cat", "chgrp", "chmod", "chown", "cp", "date", "dd", "df", "dmesg",
    "echo", "false", "hostname", "kill", "ln", "login", "ls", "mkdir",
    "mknod", "more", "mount", "mv", "ps", "pwd", "rm", "rmdir", "sh",
    "stty", "su", "sync", "true", "umount", "uname",
]

# FHS 3.0 Required /sbin commands
FHS_REQUIRED_SBIN: List[str] = [
    "fdisk", "fsck", "getty", "halt", "ifconfig", "init", "insmod",
    "ip", "lsmod", "mkfs", "modprobe", "mount", "poweroff", "reboot",
    "rmmod", "route", "shutdown", "swapon", "sysctl",
]

# Binary categories per FHS/TLDP
BIN_CATEGORIES = {
    "FILE_OPS": "File manipulation (cp, mv, rm, ln, mkdir, rmdir, ls)",
    "TEXT": "Text processing (cat, echo, more)",
    "PERMISSIONS": "Permission management (chmod, chown, chgrp)",
    "SYSTEM_INFO": "System information (uname, dmesg, hostname, df)",
    "PROCESS": "Process management (ps, kill)",
    "FILESYSTEM": "Filesystem operations (mount, umount, dd, mknod)",
    "USER": "User operations (su, login)",
    "TIME": "Time and date (date)",
    "SHELL": "Shell and boolean operations (sh, true, false)",
    "SYNC": "System sync (sync)",
    "PATH": "Path operations (pwd)",
}

# Command import registry: maps command name to (module, class_name)
COMMAND_REGISTRY: Dict[str, Tuple[str, str]] = {
    # essential_commands.py
    "cat": ("essential_commands", "CatCommand"),
    "cp": ("essential_commands", "CpCommand"),
    "mv": ("essential_commands", "MvCommand"),
    "rm": ("essential_commands", "RmCommand"),
    "ls": ("essential_commands", "LsCommand"),
    "mkdir": ("essential_commands", "MkdirCommand"),
    "rmdir": ("essential_commands", "RmdirCommand"),
    "ln": ("essential_commands", "LnCommand"),
    "dd": ("essential_commands", "DdCommand"),
    "more": ("essential_commands", "MoreCommand"),
    # permissions.py
    "chmod": ("permissions", "ChmodCommand"),
    "chown": ("permissions", "ChownCommand"),
    "chgrp": ("permissions", "ChgrpCommand"),
    # system_info.py
    "uname": ("system_info", "UnameCommand"),
    "dmesg": ("system_info", "DmesgCommand"),
    "hostname": ("system_info", "HostnameCommand"),
    "df": ("system_info", "DfCommand"),
    "echo": ("system_info", "EchoCommand"),
    "date": ("system_info", "DateCommand"),
    "pwd": ("system_info", "PwdCommand"),
    # process.py
    "ps": ("process", "PsCommand"),
    "kill": ("process", "KillCommand"),
    "mount": ("process", "MountCommand"),
    "umount": ("process", "UmountCommand"),
    "stty": ("process", "SttyCommand"),
    "sync": ("process", "SyncCommand"),
    # user_commands.py
    "su": ("user_commands", "SuCommand"),
    "login": ("user_commands", "LoginCommand"),
    # boolean_ops.py
    "true": ("boolean_ops", "TrueCommand"),
    "false": ("boolean_ops", "FalseCommand"),
    "test": ("boolean_ops", "TestCommand"),
    "[": ("boolean_ops", "BracketTestCommand"),
    "yes": ("boolean_ops", "YesCommand"),
    "printenv": ("boolean_ops", "PrintenvCommand"),
    "env": ("boolean_ops", "EnvCommand"),
    # shell.py
    "sh": ("shell", "ShCommand"),
    "sed": ("shell", "SedCommand"),
    # device.py
    "mknod": ("device", "MknodCommand"),
    # archive.py
    "tar": ("archive", "TarCommand"),
    # compression.py (gzip/gunzip/zcat in shell.py)
    "gzip": ("shell", "GzipCommand"),
    "gunzip": ("shell", "GunzipCommand"),
    "zcat": ("shell", "ZcatCommand"),
    "netstat": ("shell", "NetstatCommand"),
    "ping": ("shell", "PingCommand"),
    # network_cmds.py
    "ifconfig": ("network_cmds", "IfconfigCommand"),
    "ip": ("network_cmds", "IpCommand"),
    "route": ("network_cmds", "RouteCommand"),
    "arp": ("network_cmds", "ArpCommand"),
    # csh.py
    "csh": ("csh", "CshCommand"),
    # ed.py
    "ed": ("ed", "EdCommand"),
    # usr_commands.py
    "cpio": ("usr_commands", "CpioCommand"),
    "fold": ("usr_commands", "FoldCommand"),
    "nohup": ("usr_commands", "NohupCommand"),
    "nsenter": ("usr_commands", "NsenterCommand"),
    "strace": ("usr_commands", "StraceCommand"),
    "taskset": ("usr_commands", "TasksetCommand"),
    "time": ("usr_commands", "TimeCommand"),
    "nice": ("usr_commands", "NiceCommand"),
    "ionice": ("usr_commands", "IoniceCommand"),
    "seq": ("usr_commands", "SeqCommand"),
    "tee": ("usr_commands", "TeeCommand"),
    "wc": ("usr_commands", "WcCommand"),
    "head": ("usr_commands", "HeadCommand"),
    "tail": ("usr_commands", "TailCommand"),
    "cut": ("usr_commands", "CutCommand"),
    "sort": ("usr_commands", "SortCommand"),
    "uniq": ("usr_commands", "UniqCommand"),
    "tr": ("usr_commands", "TrCommand"),
    "xargs": ("usr_commands", "XargsCommand"),
    "which": ("usr_commands", "WhichCommand"),
    "id": ("usr_commands", "IdCommand"),
    "whoami": ("usr_commands", "WhoamiCommand"),
    "groups": ("usr_commands", "GroupsCommand"),
    "basename": ("usr_commands", "BasenameCommand"),
    "dirname": ("usr_commands", "DirnameCommand"),
    "readlink": ("usr_commands", "ReadlinkCommand"),
    "realpath": ("usr_commands", "RealpathCommand"),
    "touch": ("usr_commands", "TouchCommand"),
    "chroot": ("usr_commands", "ChrootCommand"),
    "renice": ("usr_commands", "ReniceCommand"),
    "timeout": ("usr_commands", "TimeoutCommand"),
    # usr_commands.py — new TLDP 30 utilities
    "grep": ("usr_commands", "GrepCommand"),
    "less": ("usr_commands", "LessCommand"),
    "find": ("usr_commands", "FindCommand"),
    "awk": ("usr_commands", "AwkCommand"),
    "diff": ("usr_commands", "DiffCommand"),
    "du": ("usr_commands", "DuCommand"),
    "file": ("usr_commands", "FileCommand"),
    "stat": ("usr_commands", "StatCommand"),
    "free": ("usr_commands", "FreeCommand"),
    "w": ("usr_commands", "WCommand"),
    "uptime": ("usr_commands", "UptimeCommand"),
    "pkill": ("usr_commands", "PkillCommand"),
    "pgrep": ("usr_commands", "PgrepCommand"),
    "useradd": ("usr_commands", "UseraddCommand"),
    "usermod": ("usr_commands", "UsermodCommand"),
    "userdel": ("usr_commands", "UserdelCommand"),
    "groupadd": ("usr_commands", "GroupaddCommand"),
    "groupdel": ("usr_commands", "GroupdelCommand"),
    "groupmod": ("usr_commands", "GroupmodCommand"),
    "chfn": ("usr_commands", "ChfnCommand"),
    "chsh": ("usr_commands", "ChshCommand"),
    "chage": ("usr_commands", "ChageCommand"),
    "gpasswd": ("usr_commands", "GpasswdCommand"),
    "newgrp": ("usr_commands", "NewgrpCommand"),
    "mesg": ("usr_commands", "MesgCommand"),
    "last": ("usr_commands", "LastCommand"),
    "lastlog": ("usr_commands", "LastlogCommand"),
    "patch": ("usr_commands", "PatchCommand"),
    "locate": ("usr_commands", "LocateCommand"),
    "updatedb": ("usr_commands", "UpdatedbCommand"),
    # usr_cmds.py - 115 new TLDP/usr utilities
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
    "aptd": ("usr_sbin_cmds", "APTDCommand"),
    "atd": ("usr_sbin_cmds", "ATDCommand"),
    "chronyd": ("usr_sbin_cmds", "CHRONYCommand"),
    "col": ("usr_share", "COLCommand"),
    "colrm": ("usr_share", "COLRMCommand"),
    "containerd": ("usr_sbin_cmds", "CONTAINERDCommand"),
    "cron": ("usr_sbin_cmds", "CRONCommand"),
    "crond": ("usr_sbin_cmds", "CRONDCommand"),
    "crontab-daemon": ("usr_sbin_cmds", "CRONTABDaemonCommand"),
    "dnfd": ("usr_sbin_cmds", "DNFDCommand"),
    "dockerd": ("usr_sbin_cmds", "DOCKERDCommand"),
    "dpkg-daemon": ("usr_sbin_cmds", "DPKGDAEMONCommand"),
    "faq": ("usr_share", "FAQCommand"),
    "groff": ("usr_share", "GROFFCommand"),
    "howto": ("usr_share", "HOWTOCommand"),
    "httpd": ("usr_sbin_cmds", "HTTPDCommand"),
    "info": ("usr_share", "INFCommand"),
    "klogd": ("usr_sbin_cmds", "KLOGDCommand"),
    "kubelet": ("usr_sbin_cmds", "KUBELETCommand"),
    "libvirtd": ("usr_sbin_cmds", "LIBVIRTDCommand"),
    "local-bin": ("usr_local", "LOCALBINCommand"),
    "local-doc": ("usr_local", "LOCALDOCCommand"),
    "local-etc": ("usr_local", "LOCALETCCommand"),
    "local-include": ("usr_local", "LOCALINCLUDECommand"),
    "local-lib": ("usr_local", "LOCALLIBCommand"),
    "local-man": ("usr_local", "LOCALMANCommand"),
    "local-sbin": ("usr_local", "LOCALSBINCommand"),
    "local-share": ("usr_local", "LOCALSHARECommand"),
    "local-src": ("usr_local", "LOCALSRCCommand"),
    "monitord": ("usr_sbin_cmds", "MONITORDCommand"),
    "mysqld": ("usr_sbin_cmds", "MYSQLDCommand"),
    "nginx": ("usr_sbin_cmds", "NGINXCommand"),
    "nroff": ("usr_share", "NROFFCommand"),
    "nss-daemon": ("usr_sbin_cmds", "NSSDAEMONCommand"),
    "ntpd": ("usr_sbin_cmds", "NTDPCommand"),
    "pager": ("usr_share", "PAGERCommand"),
    "postgresql": ("usr_sbin_cmds", "POSTGRESQLCommand"),
    "redis": ("usr_sbin_cmds", "REDISCommand"),
    "rsyslogd": ("usr_sbin_cmds", "RSYSLOGDCommand"),
    "slapd": ("usr_sbin_cmds", "LDAPDAEMONCommand"),
    "snapd": ("usr_sbin_cmds", "SNAPPYDCommand"),
    "sshd": ("usr_sbin_cmds", "SSHDCommand"),
    "syslogd": ("usr_sbin_cmds", "SYSLOGDCommand"),
    "systemd": ("usr_sbin_cmds", "SYSTEMDCommand"),
    "systemd-journald": ("usr_sbin_cmds", "SYSTEMDJOURNALCommand"),
    "troff": ("usr_share", "TROFFCommand"),
    "tzselect": ("usr_share", "TZSELECTCommand"),
    "udevd": ("usr_sbin_cmds", "UDEVDDCommand"),
    "xinetd": ("usr_sbin_cmds", "XINETDCommand"),
    "yum-daemon": ("usr_sbin_cmds", "YUMDAEMONCommand"),
    "zdump": ("usr_share", "ZDUMPCommand"),
    "zic": ("usr_share", "ZICCommand"),
    # usr_libexec.py - FHS 3.0 §4.2.6
    "libexec": ("usr_libexec", "LIBEXECCommand"),
    "pppoe-discovery": ("usr_libexec", "PPPODCommand"),
    "sendmail.libexec": ("usr_libexec", "SENDMAILCommand"),
    "lpd.conf": ("usr_libexec", "LPDCCommand"),
    "miniupnpd": ("usr_libexec", "MINIUPNPCCommand"),
    # usr_libqual.py - FHS 3.0 §4.2.3
    "lib64": ("usr_libqual", "LIB64Command"),
    "lib32": ("usr_libqual", "LIB32Command"),
    "libx32": ("usr_libqual", "LIBX32Command"),
    # usr_share_color.py - FHS 3.0 §4.11.3
    "color-profiles": ("usr_share_color", "COLORPROFILESCommand"),
    "colormgr": ("usr_share_color", "COLORMANAGERCommand"),
    "oyranos-monitor": ("usr_share_color", "OYRANOSCommand"),
    # usr_share_dict.py - FHS 3.0 §4.11.4
    "look": ("usr_share_dict", "DICTCommand"),
    "dict-ls": ("usr_share_dict", "DICLSCommand"),
    "ispell": ("usr_share_dict", "ISpellCommand"),
    "aspell": ("usr_share_dict", "ASpellCommand"),
    "hunspell": ("usr_share_dict", "HUNSPELLCommand"),
    # usr_share_doc.py - FHS 3.0 §4.11.5
    "doc-dir": ("usr_share_doc", "DOCDIRCommand"),
    "doc-list": ("usr_share_doc", "LSCOMMAND"),
    "pkg-doc-info": ("usr_share_doc", "PKGDOCCOMMAND"),
    "pkg-changes": ("usr_share_doc", "PKGCHANGESCommand"),
    # usr_share_games.py - FHS 3.0 §4.11.6
    "game-data": ("usr_share_games", "GAMEDATADIRCommand"),
    "nethack-data": ("usr_share_games", "NETHACKCommand"),
    "mahjongg-data": ("usr_share_games", "MAHJOCommand"),
    # usr_share_info.py - FHS 3.0 §4.11.7
    "info-dir": ("usr_share_info", "INFODIRCommand"),
    "info-pages": ("usr_share_info", "INFODIR2Command"),
    "makeinfo-texi": ("usr_share_info", "MAKEINFOCommand"),
    # usr_share_locale.py - FHS 3.0 §4.11.8
    "locale-dir": ("usr_share_locale", "LOCALEDIRCommand"),
    "locale-list": ("usr_share_locale", "LOCALELISTCommand"),
    "gettext": ("usr_share_locale", "GETTEXTCommand"),
    "msgfmt": ("usr_share_locale", "MSGFMTCommand"),
    "msgunfmt": ("usr_share_locale", "MSGUNFMTCommand"),
    # usr_share_nls.py - FHS 3.0 §4.11.9
    "nls-dir": ("usr_share_nls", "NLSCommand"),
    "nls-list": ("usr_share_nls", "NLSLISTCommand"),
    # usr_share_ppd.py - FHS 3.0 §4.11.10
    "ppd-dir": ("usr_share_ppd", "PPDDIRCommand"),
    "lpadmin": ("usr_share_ppd", "LPADMINCommand"),
    "lpinfo": ("usr_share_ppd", "LPINFOCommand"),
    "foomatic": ("usr_share_ppd", "FOOMATICCommand"),

    # usr_share_sgml.py - FHS 3.0 §4.11.11
    "sgml-dir": ("usr_share_sgml", "SgmlDirCommand"),
    "sgml-catalog": ("usr_share_sgml", "SgmlCatalogCommand"),
    "docbook": ("usr_share_sgml", "DocbookCommand"),
    "sgml-entities": ("usr_share_sgml", "SgmlEntitiesCommand"),

    # usr_share_xml.py - FHS 3.0 §4.11.12
    "xml-dir": ("usr_share_xml", "XmlDirCommand"),
    "xmlcatalog": ("usr_share_xml", "XmlCatalogCommand"),
    "xml-core": ("usr_share_xml", "XmlCoreCommand"),
    "xml-docbook": ("usr_share_xml", "XmlDocBookCommand"),

    # usr_share_templates.py - FHS 3.0 §4.11.13
    "templates-dir": ("usr_share_templates", "TemplatesDirCommand"),
    "template-list": ("usr_share_templates", "TemplateListCommand"),
    "template-show": ("usr_share_templates", "TemplateShowCommand"),

    # usr_include.py - new header commands
    "linux-asm": ("usr_include", "LinuxAsmCommand"),
    "drm-headers": ("usr_include", "DrmHeadersCommand"),
    "mtd-headers": ("usr_include", "MtdHeadersCommand"),
    "rdma-headers": ("usr_include", "RdmaHeadersCommand"),
    "sound-headers": ("usr_include", "SoundHeadersCommand"),
    "video-headers": ("usr_include", "VideoHeadersCommand"),

    # usr_local.py - new share sub-commands
    "local-share-color": ("usr_local", "LOCALSHARECOLORCommand"),
    "local-share-sgml": ("usr_local", "LOCALSHARESGMLCommand"),
    "local-share-xml": ("usr_local", "LOCALSHAREXMLCommand"),
    "local-share-templates": ("usr_local", "LOCALSHARETEMPLATESCommand"),

    # usr_share.py - new commands
    "tmac": ("usr_share", "TMACCommand"),
    "usr-share-locale": ("usr_share", "LocaleCommand"),

    # usr_src.py - FHS 3.0 §4.9 Source code hierarchy
    "src-dir": ("usr_src", "SrcDirCommand"),
    "src-linux": ("usr_src", "SrcLinuxCommand"),
    "src-kernel-headers": ("usr_src", "SrcKernelHeadersCommand"),
    "src-rpm-build": ("usr_src", "SrcRPMBuildCommand"),
    "src-net": ("usr_src", "SrcNetCommand"),
    "src-drivers": ("usr_src", "SrcDriversCommand"),
    "src-fs": ("usr_src", "SrcFsCommand"),
    "src-mm": ("usr_src", "SrcMmCommand"),
    "src-ipc": ("usr_src", "SrcIpcCommand"),
    "src-security": ("usr_src", "SrcSecurityCommand"),
    "src-crypto": ("usr_src", "SrcCryptoCommand"),
    "src-block": ("usr_src", "SrcBlockCommand"),
    "src-init": ("usr_src", "SrcInitCommand"),
    "src-sound": ("usr_src", "SrcSoundCommand"),
    "src-lib": ("usr_src", "SrcLibCommand"),
    "src-scripts": ("usr_src", "SrcScriptsCommand"),
    "src-arch": ("usr_src", "SrcArchCommand"),

    # usr_man.py - man page system configuration
    "man-conf": ("usr_man", "ManConfCommand"),
    "man-glob": ("usr_man", "ManGlobCommand"),
    "man-local": ("usr_man", "ManLocalCommand"),
    "man-nls": ("usr_man", "ManNlsCommand"),
    "man-groff-tmac": ("usr_man", "ManGroffTmacCommand"),
    "man-groff": ("usr_man", "ManGroffCommand"),

    # usr_local_libexec.py - FHS 3.0 §4.2.6 Local libexec
    "local-libexec": ("usr_local_libexec", "LocalLibexecCommand"),
    "local-libexec-plugin": ("usr_local_libexec", "LocalLibexecPluginCommand"),
    "local-libexec-mail": ("usr_local_libexec", "LocalLibexecMailCommand"),
    "local-libexec-network": ("usr_local_libexec", "LocalLibexecNetworkCommand"),
}


# ─── Enums ───────────────────────────────────────────────────────────────────

class BinCategory(IntEnum):
    """Binary categories for /bin commands."""
    FILE_OPS = 1
    TEXT = 2
    PERMISSIONS = 3
    SYSTEM_INFO = 4
    PROCESS = 5
    FILESYSTEM = 6
    USER = 7
    TIME = 8
    SHELL = 9
    SYNC = 10
    PATH = 11
    UNKNOWN = 99


class BinPrivilege(IntEnum):
    """Required privilege level."""
    USER = 0
    SUDO = 1
    ROOT = 2
    ADMIN = 3
    ANY = 99


class BinStatus(IntEnum):
    """Binary status."""
    ACTIVE = 1
    DEPRECATED = 2
    REPLACED = 3
    REMOVED = 4
    BROKEN = 5


class BinType(IntEnum):
    """Binary type."""
    ELF_STATIC = 1
    ELF_DYNAMIC = 2
    SHELL_SCRIPT = 3
    SYMLINK = 4
    UNKNOWN = 0


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class BinBinary:
    """Represents a binary in /bin."""
    name: str
    path: str
    category: BinCategory = BinCategory.UNKNOWN
    privilege: BinPrivilege = BinPrivilege.USER
    status: BinStatus = BinStatus.ACTIVE
    binary_type: BinType = BinType.UNKNOWN
    description: str = ""
    version: str = ""
    size: int = 0
    permissions: int = 0o755
    owner_uid: int = 0
    group_gid: int = 0
    is_setuid: bool = False
    is_setgid: bool = False
    is_sticky: bool = False
    dependencies: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    man_page: str = ""
    symlink_target: str = ""
    aliases: List[str] = field(default_factory=list)

    def is_executable(self) -> bool:
        """Check if binary has execute permission."""
        return bool(self.permissions & stat.S_IXUSR)

    def is_statically_linked(self) -> bool:
        """Check if binary is statically linked (required for /bin)."""
        return self.binary_type == BinType.ELF_STATIC

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": self.path,
            "category": self.category.name,
            "privilege": self.privilege.name,
            "status": self.status.name,
            "binary_type": self.binary_type.name,
            "description": self.description,
            "version": self.version,
            "size": self.size,
            "permissions": oct(self.permissions),
            "owner_uid": self.owner_uid,
            "group_gid": self.group_gid,
            "is_setuid": self.is_setuid,
            "is_setgid": self.is_setgid,
            "is_sticky": self.is_sticky,
            "dependencies": self.dependencies,
            "provides": self.provides,
            "man_page": self.man_page,
            "symlink_target": self.symlink_target,
            "aliases": self.aliases,
        }


@dataclass
class BinIndex:
    """Index entry for a binary."""
    name: str
    path: str
    metadata: Optional[BinBinary] = None
    alias_for: Optional[str] = None


@dataclass
class BinSymlink:
    """Represents a symlink in /bin."""
    name: str
    source: str
    target: str
    is_broken: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "target": self.target,
            "is_broken": self.is_broken,
        }


# ─── Binary Manager ─────────────────────────────────────────────────────────

class BinManager:
    """
    Central registry for /bin hierarchy binaries.

    Manages essential command binaries required by FHS 3.0,
    provides discovery, validation, and metadata management.
    """

    def __init__(self) -> None:
        self._binaries: Dict[str, BinBinary] = {}
        self._symlinks: Dict[str, BinSymlink] = {}
        self._aliases: Dict[str, str] = {}
        self._categories: Dict[BinCategory, List[str]] = {}
        self._scan_paths: List[str] = [BIN_PATH, SBIN_PATH]
        self._fhs_compliance: Dict[str, bool] = {}

    # ── Initialization ──────────────────────────────────────────────────

    def register_fhs_required(self) -> int:
        """Register all FHS 3.0 required binaries."""
        count = 0
        for cmd in FHS_REQUIRED_BIN:
            if cmd not in self._binaries:
                binary = BinBinary(
                    name=cmd,
                    path=f"/bin/{cmd}",
                    status=BinStatus.ACTIVE,
                )
                self._binaries[cmd] = binary
                count += 1
        return count

    def register_fhs_sbin(self) -> int:
        """Register all FHS 3.0 required /sbin binaries."""
        count = 0
        for cmd in FHS_REQUIRED_SBIN:
            if cmd not in self._binaries:
                binary = BinBinary(
                    name=cmd,
                    path=f"/sbin/{cmd}",
                    category=BinCategory.UNKNOWN,
                    privilege=BinPrivilege.ROOT,
                    status=BinStatus.ACTIVE,
                )
                self._binaries[cmd] = binary
                count += 1
        return count

    # ── Path Management ─────────────────────────────────────────────────

    def add_scan_path(self, path: str) -> None:
        """Add a directory to scan for binaries."""
        if path not in self._scan_paths:
            self._scan_paths.append(path)

    def get_scan_paths(self) -> List[str]:
        """Get configured scan paths."""
        return list(self._scan_paths)

    # ── Binary Management ───────────────────────────────────────────────

    def register_binary(self, binary: BinBinary) -> None:
        """Register a binary."""
        self._binaries[binary.name] = binary

    def get_binary(self, name: str) -> Optional[BinBinary]:
        """Get binary by name."""
        return self._binaries.get(name)

    def get_binary_by_path(self, path: str) -> Optional[BinBinary]:
        """Get binary by path."""
        for binary in self._binaries.values():
            if binary.path == path:
                return binary
        return None

    def remove_binary(self, name: str) -> bool:
        """Remove a binary from registry."""
        if name in self._binaries:
            del self._binaries[name]
            return True
        return False

    def list_binaries(
        self,
        category: Optional[BinCategory] = None,
        privilege: Optional[BinPrivilege] = None,
        status: Optional[BinStatus] = None,
    ) -> List[BinBinary]:
        """List binaries with optional filtering."""
        results: List[BinBinary] = []
        for binary in self._binaries.values():
            if category is not None and binary.category != category:
                continue
            if privilege is not None and binary.privilege != privilege:
                continue
            if status is not None and binary.status != status:
                continue
            results.append(binary)
        return results

    def list_user_commands(self) -> List[BinBinary]:
        """List commands available to non-privileged users."""
        return [
            b for b in self._binaries.values()
            if b.privilege in (BinPrivilege.USER, BinPrivilege.ANY)
        ]

    def list_admin_commands(self) -> List[BinBinary]:
        """List commands requiring admin/root."""
        return [
            b for b in self._binaries.values()
            if b.privilege in (BinPrivilege.ROOT, BinPrivilege.ADMIN)
        ]

    # ── Symlink Management ──────────────────────────────────────────────

    def register_symlink(self, name: str, target: str) -> BinSymlink:
        """Register a symlink."""
        source = f"/bin/{name}"
        is_broken = not os.path.exists(target) if target.startswith("/") else False
        symlink = BinSymlink(
            name=name,
            source=source,
            target=target,
            is_broken=is_broken,
        )
        self._symlinks[name] = symlink
        return symlink

    def get_symlink(self, name: str) -> Optional[BinSymlink]:
        """Get symlink by name."""
        return self._symlinks.get(name)

    def list_symlinks(self) -> List[BinSymlink]:
        """List all symlinks."""
        return list(self._symlinks.values())

    def list_broken_symlinks(self) -> List[BinSymlink]:
        """List all broken symlinks."""
        return [s for s in self._symlinks.values() if s.is_broken]

    # ── Alias Management ────────────────────────────────────────────────

    def register_alias(self, alias: str, original: str) -> None:
        """Register an alias."""
        self._aliases[alias] = original

    def get_alias_target(self, alias: str) -> Optional[str]:
        """Get the target of an alias."""
        return self._aliases.get(alias)

    def list_aliases(self) -> Dict[str, str]:
        """List all aliases."""
        return dict(self._aliases)

    # ── Scanning ────────────────────────────────────────────────────────

    def scan_binaries(self) -> int:
        """Scan directories and register discovered binaries."""
        count = 0
        for scan_path in self._scan_paths:
            if not os.path.isdir(scan_path):
                continue
            count += self._scan_directory(scan_path)
        return count

    def _scan_directory(self, dirpath: str) -> int:
        """Scan a single directory for binaries."""
        count = 0
        try:
            for entry in os.scandir(dirpath):
                if entry.is_file() or entry.is_symlink():
                    binary = self._analyze_entry(entry, dirpath)
                    if binary:
                        self._binaries[binary.name] = binary
                        count += 1
        except (OSError, PermissionError):
            pass
        return count

    def _analyze_entry(self, entry: os.DirEntry, dirpath: str) -> Optional[BinBinary]:
        """Analyze a directory entry."""
        try:
            st = os.stat(entry.path)
        except OSError:
            return None

        binary_type = BinType.UNKNOWN
        is_symlink = os.path.islink(entry.path)
        symlink_target = ""

        if is_symlink:
            binary_type = BinType.SYMLINK
            try:
                symlink_target = os.readlink(entry.path)
            except OSError:
                pass
        elif entry.is_file():
            if st.st_mode & stat.S_IXUSR:
                binary_type = BinType.ELF_DYNAMIC
            else:
                binary_type = BinType.ELF_STATIC

        category = self._categorize_binary(entry.name)
        privilege = BinPrivilege.ROOT if dirpath == SBIN_PATH else BinPrivilege.USER

        return BinBinary(
            name=entry.name,
            path=entry.path,
            category=category,
            privilege=privilege,
            binary_type=binary_type,
            size=st.st_size,
            permissions=st.st_mode & 0o7777,
            owner_uid=st.st_uid,
            group_gid=st.st_gid,
            is_setuid=bool(st.st_mode & stat.S_ISUID),
            is_setgid=bool(st.st_mode & stat.S_ISGID),
            is_sticky=bool(st.st_mode & stat.S_ISVTX),
            symlink_target=symlink_target,
        )

    def _categorize_binary(self, name: str) -> BinCategory:
        """Categorize a binary by name."""
        file_ops = {"cp", "mv", "rm", "ls", "mkdir", "rmdir", "ln", "mknod"}
        text = {"cat", "echo", "more"}
        permissions = {"chmod", "chown", "chgrp"}
        system_info = {"uname", "dmesg", "hostname", "df", "date"}
        process = {"ps", "kill"}
        filesystem = {"mount", "umount", "dd", "mknod"}
        user = {"su", "login"}
        shell = {"sh", "bash", "true", "false"}
        sync = {"sync"}
        path_cmd = {"pwd"}

        if name in file_ops:
            return BinCategory.FILE_OPS
        if name in text:
            return BinCategory.TEXT
        if name in permissions:
            return BinCategory.PERMISSIONS
        if name in system_info:
            return BinCategory.SYSTEM_INFO
        if name in process:
            return BinCategory.PROCESS
        if name in filesystem:
            return BinCategory.FILESYSTEM
        if name in user:
            return BinCategory.USER
        if name in shell:
            return BinCategory.SHELL
        if name in sync:
            return BinCategory.SYNC
        if name in path_cmd:
            return BinCategory.PATH
        return BinCategory.UNKNOWN

    # ── FHS Compliance ──────────────────────────────────────────────────

    def check_fhs_compliance(self) -> Dict[str, bool]:
        """Check FHS 3.0 compliance for /bin."""
        compliance: Dict[str, bool] = {}

        # Check required binaries
        for cmd in FHS_REQUIRED_BIN:
            compliance[f"/bin/{cmd}"] = cmd in self._binaries

        # Check no subdirectories in /bin
        compliance["no_subdirs"] = self._check_no_subdirs(BIN_PATH)

        self._fhs_compliance = compliance
        return compliance

    def _check_no_subdirs(self, dirpath: str) -> bool:
        """Check that a directory has no subdirectories (FSSTND requirement)."""
        if not os.path.isdir(dirpath):
            return True
        try:
            for entry in os.scandir(dirpath):
                if entry.is_dir(follow_symlinks=False):
                    return False
        except OSError:
            pass
        return True

    def get_fhs_report(self) -> Dict[str, Any]:
        """Generate FHS compliance report."""
        compliance = self.check_fhs_compliance()
        missing = [k for k, v in compliance.items() if not v]
        present = [k for k, v in compliance.items() if v]

        return {
            "total_required": len(FHS_REQUIRED_BIN),
            "present_count": len(present),
            "missing_count": len(missing),
            "missing": missing,
            "is_compliant": len(missing) == 0,
            "details": compliance,
        }

    # ── Statistics ──────────────────────────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        """Get /bin hierarchy statistics."""
        total = len(self._binaries)
        by_category: Dict[str, int] = {}
        by_privilege: Dict[str, int] = {}
        by_status: Dict[str, int] = {}

        for binary in self._binaries.values():
            cat_name = binary.category.name
            by_category[cat_name] = by_category.get(cat_name, 0) + 1

            priv_name = binary.privilege.name
            by_privilege[priv_name] = by_privilege.get(priv_name, 0) + 1

            status_name = binary.status.name
            by_status[status_name] = by_status.get(status_name, 0) + 1

        return {
            "total_binaries": total,
            "total_symlinks": len(self._symlinks),
            "broken_symlinks": len(self.list_broken_symlinks()),
            "total_aliases": len(self._aliases),
            "by_category": by_category,
            "by_privilege": by_privilege,
            "by_status": by_status,
            "fhs_required_count": len(FHS_REQUIRED_BIN),
            "fhs_required_sbin_count": len(FHS_REQUIRED_SBIN),
        }

    # ── Import/Export ───────────────────────────────────────────────────

    def export_index(self) -> List[Dict[str, Any]]:
        """Export binary index as list of dictionaries."""
        return [b.to_dict() for b in self._binaries.values()]

    def import_from_dict(self, data: Dict[str, Any]) -> int:
        """Import binaries from dictionary."""
        count = 0
        for name, info in data.items():
            binary = BinBinary(
                name=name,
                path=info.get("path", f"/bin/{name}"),
                category=BinCategory[info.get("category", "UNKNOWN")],
                privilege=BinPrivilege[info.get("privilege", "USER")],
                status=BinStatus[info.get("status", "ACTIVE")],
                description=info.get("description", ""),
                version=info.get("version", ""),
                size=info.get("size", 0),
            )
            self._binaries[name] = binary
            count += 1
        return count

    # ── Command Import ─────────────────────────────────────────────────

    def import_command(self, command_name: str) -> Optional[Any]:
        """
        Import and instantiate a command class by name.

        Args:
            command_name: The command name (e.g., 'cat', 'ls', 'ps')

        Returns:
            An instance of the command class, or None if not found
        """
        if command_name not in COMMAND_REGISTRY:
            return None

        module_name, class_name = COMMAND_REGISTRY[command_name]
        try:
            module = importlib.import_module(f".{module_name}", package=__package__)
            command_class = getattr(module, class_name)
            return command_class()
        except (ImportError, AttributeError) as e:
            print(f"Error importing {command_name}: {e}", file=sys.stderr)
            return None

    def import_all_commands(self) -> Dict[str, Any]:
        """
        Import all registered command classes.

        Returns:
            Dictionary mapping command name to command instance
        """
        commands: Dict[str, Any] = {}
        for cmd_name in COMMAND_REGISTRY:
            instance = self.import_command(cmd_name)
            if instance is not None:
                commands[cmd_name] = instance
        return commands

    def execute_command(self, command_name: str, args: Optional[List[str]] = None) -> int:
        """
        Import and execute a command by name.

        Args:
            command_name: The command name (e.g., 'cat', 'ls', 'ps')
            args: Command arguments (optional)

        Returns:
            Exit code from the command
        """
        command = self.import_command(command_name)
        if command is None:
            print(f"{command_name}: command not found", file=sys.stderr)
            return 127

        if hasattr(command, "execute"):
            return command.execute(args)
        else:
            print(f"{command_name}: no execute method", file=sys.stderr)
            return 1

    def get_command_help(self, command_name: str) -> Optional[str]:
        """
        Get help text for a command.

        Args:
            command_name: The command name

        Returns:
            Help text string, or None if not found
        """
        command = self.import_command(command_name)
        if command is None:
            return None

        if hasattr(command, "help"):
            return command.help()
        elif hasattr(command, "__doc__"):
            return command.__doc__
        return None

    def list_available_commands(self) -> List[str]:
        """List all commands that can be imported."""
        return sorted(COMMAND_REGISTRY.keys())

    def get_module_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all command modules.

        Returns:
            Dictionary with module info including available commands
        """
        modules: Dict[str, Dict[str, Any]] = {}
        for cmd_name, (module_name, class_name) in COMMAND_REGISTRY.items():
            if module_name not in modules:
                modules[module_name] = {
                    "commands": [],
                    "loaded": False,
                    "error": None,
                }
            modules[module_name]["commands"].append(cmd_name)

        # Check which modules can be imported
        for module_name in modules:
            try:
                importlib.import_module(f".{module_name}", package=__package__)
                modules[module_name]["loaded"] = True
            except ImportError as e:
                modules[module_name]["error"] = str(e)

        return modules


# ─── Module-Level Singleton ─────────────────────────────────────────────────

_bin_manager: Optional[BinManager] = None


def get_bin_manager() -> BinManager:
    """Get or create the singleton BinManager."""
    global _bin_manager
    if _bin_manager is None:
        _bin_manager = BinManager()
        _bin_manager.register_fhs_required()
    return _bin_manager
