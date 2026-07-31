"""
Umer OS Shell Command Registry
==============================
Implements comprehensive Linux commands covering:
- Hardware Information (lscpu, lsblk, lspci, lsusb, lshw, dmidecode, hdparm, badblocks, fsck)
- Searching (find, grep, locate, which, whereis, awk, sed)
- File Management (mkdir, rm, cp, mv, ln, touch, cat, head, tail, more, less, nano, vi/vim, gpg, wc, xargs, cut, shred, diff, source, tee)
- Directory Navigation (ls, pwd, cd, dirs)
- File Compression (tar, gzip, gunzip, bzip2, bunzip2)
- File Transfer (scp, rsync, wget, curl, ftp, sftp)
- User & Group Management (id, last, who, w, finger, useradd, adduser, userdel, usermod, passwd, groupadd, groupdel, groupmod, sudo, su, chgrp)
- Package Managers (apt-get, apt, dpkg, yum, dnf, rpm, snap, flatpak, make)
- Process Management (ps, pstree, pmap, top, htop, kill, pkill, killall, pgrep, pidof, bg, fg, lsof, trap, wait, nohup)
- System Management (uname, uptime, hostname, date, timedatectl, cal, ulimit, shutdown, modprobe, dmesg)
- Disk Usage (df, fdisk, du, mount, findmnt)
- SSH & Remote (ssh, ssh-keygen, service, telnet)
- Variables & Shell Utilities (let, export, declare, set, unset, alias, watch, sleep, at, man, history, clear, exit)
"""

import time
import os
import re

class CommandContext:
    """Provides execution context (kernel access, shell state) to commands."""
    def __init__(self, kernel, shell):
        self.kernel = kernel
        self.shell = shell

class ShellCommand:
    """Base class for shell commands."""
    name = "command"
    help_text = "No help available."
    category = "General"
    
    def execute(self, ctx: CommandContext, args: list) -> str:
        raise NotImplementedError()

# ============================================================================
# 1. HARDWARE INFORMATION COMMANDS
# ============================================================================

class LscpuCommand(ShellCommand):
    name = "lscpu"
    help_text = "See CPU information"
    category = "Hardware Info"
    
    def execute(self, ctx, args):
        try:
            return ctx.kernel.vfs.read_file("/proc/cpuinfo")
        except Exception:
            return (
                "Architecture:                    x86_64\n"
                "CPU op-mode(s):                  32-bit, 64-bit\n"
                "CPU(s):                          8\n"
                "Vendor ID:                       QuantumGenuineIntel\n"
                "Model name:                      UmerOS Quantum AI Accelerator CPU @ 3.40GHz"
            )

class LsblkCommand(ShellCommand):
    name = "lsblk"
    help_text = "See information about block devices"
    category = "Hardware Info"
    
    def execute(self, ctx, args):
        return (
            "NAME        MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT\n"
            "loop0         7:0    0  62.1M  1 loop /snap/core/1000\n"
            "sda           8:0    0 500.0G  0 disk \n"
            "├─sda1        8:1    0   512M  0 part /boot/efi\n"
            "├─sda2        8:2    0 480.0G  0 part /\n"
            "└─sda3        8:3    0  19.5G  0 part [SWAP]\n"
            "nvme0n1     259:0    0   1.0T  0 disk \n"
            "└─nvme0n1p1 259:1    0   1.0T  0 part /mnt/qfs_storage"
        )

class LspciCommand(ShellCommand):
    name = "lspci"
    help_text = "Show PCI devices in a tree-like diagram (-tv)"
    category = "Hardware Info"
    
    def execute(self, ctx, args):
        return (
            "-[0000:00]-+-00.0  Intel Corporation 10th Gen Core Processor Host Bridge\n"
            "           +-02.0  Intel Corporation UHD Graphics 630\n"
            "           +-14.0  Intel Corporation Cannon Lake PCH USB 3.1 xHCI Host Controller\n"
            "           +-16.0  Intel Corporation Cannon Lake PCH HECI Controller\n"
            "           +-1c.0-[01]--+-00.0  Realtek Semiconductor Co. RTL8111 Ethernet Controller\n"
            "           |            └-00.1  Intel Corporation Wi-Fi 6 AX200\n"
            "           └-1f.3  Intel Corporation Cannon Lake PCH cHD Audio"
        )

class LsusbCommand(ShellCommand):
    name = "lsusb"
    help_text = "Display USB devices in a tree-like diagram (-tv)"
    category = "Hardware Info"
    
    def execute(self, ctx, args):
        return (
            "Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub\n"
            "Bus 001 Device 004: ID 046d:c52b Logitech, Inc. Unifying Receiver\n"
            "Bus 001 Device 003: ID 05e3:0610 Genesys Logic, Inc. Hub\n"
            "Bus 001 Device 002: ID 8087:0029 Intel Corp. AX200 Bluetooth\n"
            "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub"
        )

class LshwCommand(ShellCommand):
    name = "lshw"
    help_text = "List hardware configuration information"
    category = "Hardware Info"
    
    def execute(self, ctx, args):
        return (
            "UmerOS-Node1\n"
            "    description: Computer\n"
            "    product: UmerOS Quantum Workstation\n"
            "    width: 64 bits\n"
            "  *-core\n"
            "       description: Motherboard\n"
            "       product: UmerOS Custom Quantum Mainboard\n"
            "     *-firmware\n"
            "          description: BIOS\n"
            "          version: UmerOS UEFI v2.1.0\n"
            "     *-cpu\n"
            "          description: CPU\n"
            "          product: UmerOS Quantum AI Accelerator CPU @ 3.40GHz\n"
            "     *-memory\n"
            "          description: System Memory\n"
            "          size: 4GiB\n"
            "     *-network\n"
            "          description: Ethernet interface\n"
            "          product: RTL8111/8168/8411 PCI Express Gigabit Ethernet Controller"
        )

class DmidecodeCommand(ShellCommand):
    name = "dmidecode"
    help_text = "Show hardware information from BIOS (DMI)"
    category = "Hardware Info"
    
    def execute(self, ctx, args):
        return (
            "# dmidecode 3.2\n"
            "Getting SMBIOS data from sysfs.\n"
            "SMBIOS 3.3.0 present.\n\n"
            "Handle 0x0000, DMI type 0, 26 bytes\n"
            "BIOS Information\n"
            "\tVendor: UmerOS Core BIOS\n"
            "\tVersion: 2.1.0-Release\n"
            "\tRelease Date: 07/31/2026\n"
            "\tAddress: 0xF0000\n"
            "\tRuntime Size: 64 kB\n"
            "\tROM Size: 16 MB"
        )

class HdparmCommand(ShellCommand):
    name = "hdparm"
    help_text = "Display disk data information / read speed test (-i, -tT)"
    category = "Hardware Info"
    
    def execute(self, ctx, args):
        dev = args[-1] if args else "/dev/sda"
        return (
            f"{dev}:\n"
            f" Timing cached reads:   18420 MB in  2.00 seconds = 9210.00 MB/sec\n"
            f" Timing buffered disk reads: 1540 MB in  3.01 seconds =  511.63 MB/sec"
        )

class BadblocksCommand(ShellCommand):
    name = "badblocks"
    help_text = "Test for unreadable blocks on device/disk"
    category = "Hardware Info"
    
    def execute(self, ctx, args):
        dev = args[-1] if args else "/dev/sda"
        return f"Checking blocks 0 to 524288000 on {dev}...\nDone. Found 0 bad blocks. (0/0/0 errors)"

class FsckCommand(ShellCommand):
    name = "fsck"
    help_text = "Run a disk check on an unmounted disk or partition"
    category = "Hardware Info"
    
    def execute(self, ctx, args):
        dev = args[-1] if args else "/dev/sda1"
        return (
            f"fsck from util-linux 2.34\n"
            f"e2fsck 1.45.5 (07-Jan-2020)\n"
            f"{dev}: clean, 120485/30000000 files, 2104950/120000000 blocks"
        )

# ============================================================================
# 2. SEARCHING COMMANDS
# ============================================================================

class FindCommand(ShellCommand):
    name = "find"
    help_text = "Find files and directories matching pattern or size"
    category = "Search"
    
    def execute(self, ctx, args):
        path = "."
        name_pattern = None
        
        i = 0
        while i < len(args):
            if args[i] == "-name" and i + 1 < len(args):
                name_pattern = args[i+1].strip('"').strip("'")
                i += 2
            elif args[i] == "-size":
                i += 2
            elif not args[i].startswith("-"):
                path = args[i]
                i += 1
            else:
                i += 1
                
        try:
            results = ctx.kernel.vfs.find(path, name_pattern)
            return "\n".join(results)
        except Exception as e:
            return f"find: {str(e)}"

class GrepCommand(ShellCommand):
    name = "grep"
    help_text = "Search for a specific pattern in files (-r, -i, -n, -v)"
    category = "Search"
    
    def execute(self, ctx, args):
        ignore_case = "-i" in args
        line_num = "-n" in args
        invert = "-v" in args
        recursive = "-r" in args or "-R" in args
        
        non_flag_args = [a for a in args if not a.startswith("-")]
        if not non_flag_args:
            return "grep: missing pattern"
        pattern = non_flag_args[0]
        files = non_flag_args[1:]
        
        if not files:
            files = ["."] if recursive else []
            
        output = []
        flags = re.IGNORECASE if ignore_case else 0
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            return f"grep: invalid pattern: {e}"

        target_files = []
        for f in files:
            try:
                st = ctx.kernel.vfs.stat(f)
                if st["is_dir"]:
                    if recursive:
                        target_files.extend(ctx.kernel.vfs.find(f))
                else:
                    target_files.append(f)
            except Exception:
                pass

        for tf in target_files:
            try:
                st = ctx.kernel.vfs.stat(tf)
                if st["is_dir"]: continue
                content = ctx.kernel.vfs.read_file(tf)
                lines = content.splitlines()
                for idx, line in enumerate(lines):
                    matched = bool(rx.search(line))
                    if invert: matched = not matched
                    if matched:
                        prefix = f"{tf}:" if len(target_files) > 1 else ""
                        num_str = f"{idx+1}:" if line_num else ""
                        output.append(f"{prefix}{num_str}{line}")
            except Exception:
                pass
        return "\n".join(output)

class LocateCommand(ShellCommand):
    name = "locate"
    help_text = "Locate all files and directories related to a particular name"
    category = "Search"
    
    def execute(self, ctx, args):
        if not args: return "locate: no pattern given"
        name_pattern = args[0]
        try:
            results = ctx.kernel.vfs.find("/", name_pattern)
            return "\n".join(results)
        except Exception as e:
            return f"locate: {e}"

class WhichCommand(ShellCommand):
    name = "which"
    help_text = "Search the command path in environment variables"
    category = "Search"
    
    def execute(self, ctx, args):
        if not args: return ""
        cmd_name = args[0]
        if cmd_name in ctx.shell.registry:
            return f"/bin/{cmd_name}"
        return f"{cmd_name} not found"

class WhereIsCommand(ShellCommand):
    name = "whereis"
    help_text = "Find source, binary, and manual page for a command"
    category = "Search"
    
    def execute(self, ctx, args):
        if not args: return ""
        cmd_name = args[0]
        if cmd_name in ctx.shell.registry:
            return f"{cmd_name}: /bin/{cmd_name} /usr/bin/{cmd_name} /usr/share/man/man1/{cmd_name}.1.gz"
        return f"{cmd_name}:"

class AwkCommand(ShellCommand):
    name = "awk"
    help_text = "Pattern scanning and processing language"
    category = "Search"
    
    def execute(self, ctx, args):
        if not args: return "awk: missing pattern or file"
        pattern = args[0]
        files = [a for a in args[1:] if not a.startswith("-")]
        
        output = []
        for f in files:
            try:
                c = ctx.kernel.vfs.read_file(f)
                lines = c.splitlines()
                for l in lines:
                    output.append(l)
            except Exception as e:
                output.append(f"awk: {f}: {e}")
        return "\n".join(output) if output else "\n".join(args)

class SedCommand(ShellCommand):
    name = "sed"
    help_text = "Stream editor for filtering and transforming text"
    category = "Search"
    
    def execute(self, ctx, args):
        if not args: return "sed: missing expression"
        expr = args[0]
        files = [a for a in args[1:] if not a.startswith("-")]
        
        # Match s/old/new/ pattern
        m = re.match(r"s/(.*?)/(.*?)/(g?)", expr)
        if not m:
            return f"sed: expression failed: {expr}"
            
        old_text, new_text, flag = m.groups()
        output = []
        for f in files:
            try:
                c = ctx.kernel.vfs.read_file(f)
                if flag == "g":
                    res = c.replace(old_text, new_text)
                else:
                    res = c.replace(old_text, new_text, 1)
                output.append(res)
            except Exception as e:
                output.append(f"sed: {f}: {e}")
        return "\n".join(output)

# ============================================================================
# 3. FILE COMMANDS
# ============================================================================

class MkdirCommand(ShellCommand):
    name = "mkdir"
    help_text = "Create a new directory (-p parents)"
    category = "File Commands"
    
    def execute(self, ctx, args):
        if not args: return "mkdir: missing operand"
        parents = "-p" in args
        targets = [a for a in args if not a.startswith("-")]
        output = []
        for d in targets:
            try:
                ctx.kernel.vfs.mkdir(d, parents=parents)
            except Exception as e:
                output.append(f"mkdir: cannot create directory '{d}': {str(e)}")
        return "\n".join(output)

class RmCommand(ShellCommand):
    name = "rm"
    help_text = "Remove files or directories (-r recursive, -f force)"
    category = "File Commands"
    
    def execute(self, ctx, args):
        if not args: return "rm: missing operand"
        force = "-f" in args or "-rf" in args or "-fr" in args
        recursive = "-r" in args or "-rf" in args or "-fr" in args or "-R" in args
        targets = [a for a in args if not a.startswith("-")]
        
        output = []
        for target in targets:
            try:
                ctx.kernel.vfs.rm(target, recursive=recursive)
            except Exception as e:
                if not force:
                    output.append(f"rm: cannot remove '{target}': {str(e)}")
        return "\n".join(output)

class CpCommand(ShellCommand):
    name = "cp"
    help_text = "Copy file or directory (-r recursive)"
    category = "File Commands"
    
    def execute(self, ctx, args):
        recursive = "-r" in args or "-R" in args or "-a" in args
        targets = [a for a in args if not a.startswith("-")]
        if len(targets) < 2:
            return "cp: missing destination file operand"
        src, dest = targets[0], targets[1]
        try:
            ctx.kernel.vfs.cp(src, dest, recursive=recursive)
            return ""
        except Exception as e:
            return f"cp: {str(e)}"

class MvCommand(ShellCommand):
    name = "mv"
    help_text = "Move or rename files or directories"
    category = "File Commands"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if len(targets) < 2: return "mv: missing destination file operand"
        src, dest = targets[0], targets[1]
        try:
            ctx.kernel.vfs.mv(src, dest)
            return ""
        except Exception as e:
            return f"mv: {str(e)}"

class LnCommand(ShellCommand):
    name = "ln"
    help_text = "Create a symbolic link (-s soft link)"
    category = "File Commands"
    
    def execute(self, ctx, args):
        is_sym = "-s" in args or "-sf" in args
        targets = [a for a in args if not a.startswith("-")]
        if len(targets) < 2: return "ln: missing file operand"
        target, link_name = targets[0], targets[1]
        try:
            ctx.kernel.vfs.touch(link_name)
            node, _ = ctx.kernel.vfs._resolve(link_name)
            if node:
                node.is_symlink = is_sym
                node.symlink_target = target
            return ""
        except Exception as e:
            return f"ln: {e}"

class TouchCommand(ShellCommand):
    name = "touch"
    help_text = "Create a new empty file or update timestamp"
    category = "File Commands"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if not targets: return "touch: missing file operand"
        output = []
        for f in targets:
            try:
                ctx.kernel.vfs.touch(f)
            except Exception as e:
                output.append(f"touch: cannot touch '{f}': {str(e)}")
        return "\n".join(output)

class CatCommand(ShellCommand):
    name = "cat"
    help_text = "Show file contents or append (>>) to file"
    category = "File Commands"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if not targets: return ""
        output = []
        for f in targets:
            try:
                content = ctx.kernel.vfs.read_file(f)
                output.append(content)
            except Exception as e:
                output.append(f"cat: {f}: {str(e)}")
        return "\n".join(output)

class HeadCommand(ShellCommand):
    name = "head"
    help_text = "Show the first ten lines of a file"
    category = "File Commands"
    
    def execute(self, ctx, args):
        lines_count = 10
        filename = None
        i = 0
        while i < len(args):
            if args[i] == "-n" and i + 1 < len(args):
                try: lines_count = int(args[i+1])
                except ValueError: pass
                i += 2
            elif not args[i].startswith("-"):
                filename = args[i]
                i += 1
            else: i += 1
                
        if not filename: return "head: missing file operand"
        try:
            content = ctx.kernel.vfs.read_file(filename)
            return "\n".join(content.splitlines()[:lines_count])
        except Exception as e:
            return f"head: cannot open '{filename}': {str(e)}"

class TailCommand(ShellCommand):
    name = "tail"
    help_text = "Show the last ten lines of a file"
    category = "File Commands"
    
    def execute(self, ctx, args):
        lines_count = 10
        filename = None
        i = 0
        while i < len(args):
            if args[i] == "-n" and i + 1 < len(args):
                try: lines_count = int(args[i+1])
                except ValueError: pass
                i += 2
            elif not args[i].startswith("-"):
                filename = args[i]
                i += 1
            else: i += 1
                
        if not filename: return "tail: missing file operand"
        try:
            content = ctx.kernel.vfs.read_file(filename)
            return "\n".join(content.splitlines()[-lines_count:])
        except Exception as e:
            return f"tail: cannot open '{filename}': {str(e)}"

class MoreCommand(ShellCommand):
    name = "more"
    help_text = "Display contents of a file page by page"
    category = "File Commands"
    def execute(self, ctx, args):
        return CatCommand().execute(ctx, args)

class LessCommand(ShellCommand):
    name = "less"
    help_text = "Show contents of a file with navigation"
    category = "File Commands"
    def execute(self, ctx, args):
        return CatCommand().execute(ctx, args)

class NanoCommand(ShellCommand):
    name = "nano"
    help_text = "Open or create a file using Nano text editor"
    category = "File Commands"
    
    def execute(self, ctx, args):
        if not args: return "nano: missing file operand"
        filename = args[0]
        if len(args) > 1:
            content = " ".join(args[1:])
            ctx.kernel.vfs.write_file(filename, content)
            return f"[nano] Saved {len(content)} bytes to {filename}"
        else:
            try:
                content = ctx.kernel.vfs.read_file(filename)
                return f"[nano] File '{filename}' contents:\n----------------------------------------\n{content}\n----------------------------------------"
            except Exception:
                ctx.kernel.vfs.touch(filename)
                return f"[nano] Created new file '{filename}'"

class ViCommand(ShellCommand):
    name = "vi"
    help_text = "Open or create a file using Vi/Vim editor"
    category = "File Commands"
    def execute(self, ctx, args):
        return NanoCommand().execute(ctx, args)

class VimCommand(ShellCommand):
    name = "vim"
    help_text = "Vim text editor"
    category = "File Commands"
    def execute(self, ctx, args):
        return NanoCommand().execute(ctx, args)

class GpgCommand(ShellCommand):
    name = "gpg"
    help_text = "Encrypt or decrypt files (-c file.txt)"
    category = "File Commands"
    
    def execute(self, ctx, args):
        if not args: return "gpg: no command given"
        if "-c" in args:
            target = args[-1]
            try:
                c = ctx.kernel.vfs.read_file(target)
                ctx.kernel.vfs.write_file(target + ".gpg", f"-----BEGIN PGP MESSAGE-----\nENCRYPTED:{c}\n-----END PGP MESSAGE-----")
                return f"gpg: encrypted '{target}' to '{target}.gpg'"
            except Exception as e:
                return f"gpg: encryption failed: {e}"
        else:
            target = args[-1]
            try:
                c = ctx.kernel.vfs.read_file(target)
                decrypted = c.replace("-----BEGIN PGP MESSAGE-----\nENCRYPTED:", "").replace("\n-----END PGP MESSAGE-----", "")
                return decrypted
            except Exception as e:
                return f"gpg: decryption failed: {e}"

class WcCommand(ShellCommand):
    name = "wc"
    help_text = "Show number of words, lines, and bytes in a file (-w, -l, -c)"
    category = "File Commands"
    
    def execute(self, ctx, args):
        show_words = "-w" in args
        show_lines = "-l" in args
        show_bytes = "-c" in args or "-m" in args
        
        targets = [a for a in args if not a.startswith("-")]
        if not targets: return "0 0 0"
        lines_out = []
        for t in targets:
            try:
                c = ctx.kernel.vfs.read_file(t)
                l = len(c.splitlines())
                w = len(c.split())
                b = len(c.encode('utf-8'))
                
                if show_words and not show_lines and not show_bytes:
                    lines_out.append(f"{w} {t}")
                elif show_lines and not show_words and not show_bytes:
                    lines_out.append(f"{l} {t}")
                elif show_bytes and not show_lines and not show_words:
                    lines_out.append(f"{b} {t}")
                else:
                    lines_out.append(f" {l:>4} {w:>4} {b:>4} {t}")
            except Exception as e:
                lines_out.append(f"wc: {t}: {str(e)}")
        return "\n".join(lines_out)

class XargsCommand(ShellCommand):
    name = "xargs"
    help_text = "Build and execute command lines from standard input"
    category = "File Commands"
    
    def execute(self, ctx, args):
        if not args: return ""
        sub_cmd = args[0]
        sub_args = args[1:]
        if sub_cmd in ctx.shell.registry:
            return ctx.shell.registry[sub_cmd].execute(ctx, sub_args)
        return f"xargs: {sub_cmd}: command not found"

class CutCommand(ShellCommand):
    name = "cut"
    help_text = "Cut out sections of each line of a file"
    category = "File Commands"
    
    def execute(self, ctx, args):
        delim = " "
        field = 1
        i = 0
        filename = None
        while i < len(args):
            if args[i] == "-d" and i + 1 < len(args):
                delim = args[i+1]
                i += 2
            elif args[i] == "-f" and i + 1 < len(args):
                try: field = int(args[i+1])
                except ValueError: pass
                i += 2
            elif not args[i].startswith("-"):
                filename = args[i]
                i += 1
            else: i += 1
                
        if not filename: return "cut: missing file operand"
        try:
            c = ctx.kernel.vfs.read_file(filename)
            out = []
            for line in c.splitlines():
                parts = line.split(delim)
                if len(parts) >= field:
                    out.append(parts[field - 1])
                else:
                    out.append(line)
            return "\n".join(out)
        except Exception as e:
            return f"cut: {e}"

class ShredCommand(ShellCommand):
    name = "shred"
    help_text = "Overwrite a file to prevent recovery, then delete it (-u)"
    category = "File Commands"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if not targets: return "shred: missing file operand"
        remove = "-u" in args or "--remove" in args
        out = []
        for t in targets:
            try:
                ctx.kernel.vfs.write_file(t, "\x00" * 4096)
                if remove:
                    ctx.kernel.vfs.rm(t)
                out.append(f"shred: {t}: overwritten successfully")
            except Exception as e:
                out.append(f"shred: {t}: {e}")
        return "\n".join(out)

class DiffCommand(ShellCommand):
    name = "diff"
    help_text = "Compare two files line by line"
    category = "File Commands"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if len(targets) < 2: return "diff: missing operand"
        f1, f2 = targets[0], targets[1]
        try:
            c1 = ctx.kernel.vfs.read_file(f1).splitlines()
            c2 = ctx.kernel.vfs.read_file(f2).splitlines()
            diff_lines = []
            for i in range(max(len(c1), len(c2))):
                l1 = c1[i] if i < len(c1) else ""
                l2 = c2[i] if i < len(c2) else ""
                if l1 != l2:
                    diff_lines.append(f"{i+1}c{i+1}\n< {l1}\n---\n> {l2}")
            return "\n".join(diff_lines)
        except Exception as e:
            return f"diff: {e}"

class SourceCommand(ShellCommand):
    name = "source"
    help_text = "Read and execute commands from a file in the current shell"
    category = "File Commands"
    
    def execute(self, ctx, args):
        if not args: return "source: filename argument required"
        script = args[0]
        try:
            content = ctx.kernel.vfs.read_file(script)
            results = []
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    cmd = parts[0]
                    c_args = parts[1:]
                    if cmd in ctx.shell.registry:
                        res = ctx.shell.registry[cmd].execute(ctx, c_args)
                        if res: results.append(res)
            return "\n".join(results)
        except Exception as e:
            return f"source: {script}: {e}"

class TeeCommand(ShellCommand):
    name = "tee"
    help_text = "Read from standard input and write to standard output and files"
    category = "File Commands"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if targets:
            try:
                ctx.kernel.vfs.write_file(targets[0], "Tee output buffer\n")
            except Exception: pass
        return "Tee execution complete."

# ============================================================================
# 4. DIRECTORY NAVIGATION COMMANDS
# ============================================================================

class LsCommand(ShellCommand):
    name = "ls"
    help_text = "List files and directories (-a show hidden, -l long format)"
    category = "Navigation"
    
    def execute(self, ctx, args):
        show_long = False
        show_all = False
        path = ctx.kernel.vfs.cwd
        
        for arg in args:
            if arg.startswith("-"):
                if "l" in arg: show_long = True
                if "a" in arg: show_all = True
            else:
                path = arg
                
        try:
            contents = ctx.kernel.vfs.ls(path)
            if not show_all:
                contents = [c for c in contents if not c.startswith(".")]
            
            if not show_long:
                return "  ".join(contents)
            
            lines = [f"total {len(contents)}"]
            for item in contents:
                item_path = path.rstrip("/") + "/" + item if path != "/" else "/" + item
                try:
                    st = ctx.kernel.vfs.stat(item_path)
                    prefix = "d" if st["is_dir"] else "-"
                    mode = st["mode"]
                    owner = st["owner"]
                    group = st["group"]
                    size = st["size"]
                    mtime_str = time.strftime("%b %d %H:%M", time.localtime(st["mtime"]))
                    lines.append(f"{prefix}{mode} 1 {owner} {group} {size:>8} {mtime_str} {item}")
                except Exception:
                    lines.append(f"-rw-r--r-- 1 umer umer 0 {item}")
            return "\n".join(lines)
        except Exception as e:
            return f"ls: cannot access '{path}': {str(e)}"

class PwdCommand(ShellCommand):
    name = "pwd"
    help_text = "Show the directory you are currently working in"
    category = "Navigation"
    def execute(self, ctx, args):
        return ctx.kernel.vfs.cwd

class CdCommand(ShellCommand):
    name = "cd"
    help_text = "Change directory (cd ~, cd .., cd -)"
    category = "Navigation"
    
    def execute(self, ctx, args):
        if not args or args[0] == "~":
            target = "/home/umer"
        elif args[0] == "-":
            target = getattr(ctx.shell, "prev_cwd", "/home/umer")
        else:
            target = args[0]
            
        ctx.shell.prev_cwd = ctx.kernel.vfs.cwd
        try:
            ctx.kernel.vfs.cd(target)
            return ""
        except Exception as e:
            return f"-bash: cd: {target}: {str(e)}"

class DirsCommand(ShellCommand):
    name = "dirs"
    help_text = "Display list of currently remembered directories"
    category = "Navigation"
    def execute(self, ctx, args):
        return ctx.kernel.vfs.cwd

# ============================================================================
# 5. FILE COMPRESSION COMMANDS
# ============================================================================

class TarCommand(ShellCommand):
    name = "tar"
    help_text = "Archive and extract files (tar cf, tar xf, tar czf, tar zxvf)"
    category = "Compression"
    
    def execute(self, ctx, args):
        if not args: return "tar: Must specify one of the '-Acdtrux' options"
        flags = args[0]
        archive_name = args[1] if len(args) > 1 else "archive.tar"
        
        if "c" in flags:
            targets = args[2:] if len(args) > 2 else ["."]
            ctx.kernel.vfs.write_file(archive_name, f"TAR_ARCHIVE:{','.join(targets)}")
            return f"tar: created archive '{archive_name}' containing {len(targets)} target(s)"
        elif "x" in flags:
            try:
                c = ctx.kernel.vfs.read_file(archive_name)
                return f"tar: extracted archive '{archive_name}'"
            except Exception as e:
                return f"tar: error reading {archive_name}: {e}"
        return f"tar: processed {archive_name}"

class GzipCommand(ShellCommand):
    name = "gzip"
    help_text = "Compress files into .gz format"
    category = "Compression"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if not targets: return "gzip: missing file operand"
        for t in targets:
            try:
                c = ctx.kernel.vfs.read_file(t)
                ctx.kernel.vfs.write_file(t + ".gz", f"GZ_COMPRESSED:{c}")
                ctx.kernel.vfs.rm(t)
            except Exception as e:
                return f"gzip: {t}: {e}"
        return ""

class GunzipCommand(ShellCommand):
    name = "gunzip"
    help_text = "Decompress .gz compressed files"
    category = "Compression"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if not targets: return "gunzip: missing file operand"
        for t in targets:
            try:
                c = ctx.kernel.vfs.read_file(t)
                decompressed = c.replace("GZ_COMPRESSED:", "")
                out_name = t.rstrip(".gz")
                ctx.kernel.vfs.write_file(out_name, decompressed)
                if t.endswith(".gz"): ctx.kernel.vfs.rm(t)
            except Exception as e:
                return f"gunzip: {t}: {e}"
        return ""

class Bzip2Command(ShellCommand):
    name = "bzip2"
    help_text = "Compress files into .bz2 format"
    category = "Compression"
    
    def execute(self, ctx, args):
        return GzipCommand().execute(ctx, args)

class Bunzip2Command(ShellCommand):
    name = "bunzip2"
    help_text = "Decompress .bz2 compressed files"
    category = "Compression"
    
    def execute(self, ctx, args):
        return GunzipCommand().execute(ctx, args)

# ============================================================================
# 6. FILE TRANSFER COMMANDS
# ============================================================================

class ScpCommand(ShellCommand):
    name = "scp"
    help_text = "Secure copy files between hosts using SSH"
    category = "File Transfer"
    
    def execute(self, ctx, args):
        if len(args) < 2: return "usage: scp [-346BCpqrvr] source ... target"
        src, dest = args[0], args[1]
        return f"Sending {src} -> {dest} (100% 4KB/s, 0.1s)"

class RsyncCommand(ShellCommand):
    name = "rsync"
    help_text = "Fast and versatile file copying and synchronization tool"
    category = "File Transfer"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if len(targets) < 2: return "rsync error: syntax or usage error"
        return f"sending incremental file list\n{targets[0]}\n\nsent 410 bytes  received 35 bytes  890.00 bytes/sec\ntotal size is {targets[0]} speedup is 1.0"

class WgetCommand(ShellCommand):
    name = "wget"
    help_text = "Download files from web or FTP servers"
    category = "File Transfer"
    
    def execute(self, ctx, args):
        if not args: return "wget: missing URL"
        url = args[-1]
        filename = url.rstrip("/").split("/")[-1] or "index.html"
        try:
            ctx.kernel.vfs.write_file(filename, f"<!-- Downloaded from {url} -->\n<html><body>Content from {url}</body></html>")
            return f"--2026-07-31--  {url}\nConnecting to {url}... connected.\nHTTP request sent, awaiting response... 200 OK\nLength: 120 [text/html]\nSaving to: '{filename}'\n\n'{filename}' saved [120/120]"
        except Exception as e:
            return f"wget: error saving to {filename}: {e}"

class CurlCommand(ShellCommand):
    name = "curl"
    help_text = "Transfer data to or from a server (-O download)"
    category = "File Transfer"
    
    def execute(self, ctx, args):
        if not args: return "curl: try 'curl --help' or 'curl --manual' for more information"
        url = args[-1]
        if url.startswith("-"): return "curl: no URL specified!"
        if "-O" in args:
            filename = url.rstrip("/").split("/")[-1] or "download"
            ctx.kernel.vfs.write_file(filename, f"Data from {url}")
            return f"  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current\n 100   120  100   120    0     0   1200      0 --:--:-- --:--:-- --:--:--  1200"
        return f"<!DOCTYPE html><html><body><h1>Response from {url}</h1><p>Fetched by UmerOS Virtual HTTP Client.</p></body></html>"

class FtpCommand(ShellCommand):
    name = "ftp"
    help_text = "Interactive File Transfer Protocol"
    category = "File Transfer"
    def execute(self, ctx, args):
        host = args[0] if args else "remote_host"
        return f"Connected to {host}.\n220 (vsFTPd 3.0.3)\nName ({host}:umer): 230 Login successful.\nftp> "

class SftpCommand(ShellCommand):
    name = "sftp"
    help_text = "Secure File Transfer Program over SSH"
    category = "File Transfer"
    def execute(self, ctx, args):
        host = args[0] if args else "remote_host"
        return f"Connected to {host}.\nsftp> "

# ============================================================================
# 7. USER & GROUP COMMANDS
# ============================================================================

class WhoAmICommand(ShellCommand):
    name = "whoami"
    help_text = "Print effective userid"
    category = "User & Group"
    def execute(self, ctx, args):
        return ctx.shell.current_user

class IdCommand(ShellCommand):
    name = "id"
    help_text = "Print real and effective user and group IDs"
    category = "User & Group"
    def execute(self, ctx, args):
        user = ctx.shell.current_user
        return f"uid=1000({user}) gid=1000({user}) groups=1000({user}),27(sudo),4(adm)"

class GroupsCommand(ShellCommand):
    name = "groups"
    help_text = "Print the groups a user is in"
    category = "User & Group"
    def execute(self, ctx, args):
        user = ctx.shell.current_user
        return f"{user} : {user} sudo adm cdrom plugdev lpadmin lxd sambashare"

class WhoCommand(ShellCommand):
    name = "who"
    help_text = "Show who is logged on"
    category = "User & Group"
    def execute(self, ctx, args):
        t = time.strftime("%Y-%m-%d %H:%M")
        return f"{ctx.shell.current_user} :0 {t} (:0)"

class UsersCommand(ShellCommand):
    name = "users"
    help_text = "Print the user names of users currently logged in"
    category = "User & Group"
    def execute(self, ctx, args):
        return ctx.shell.current_user

class FingerCommand(ShellCommand):
    name = "finger"
    help_text = "User information lookup program"
    category = "User & Group"
    def execute(self, ctx, args):
        user = ctx.shell.current_user
        return (
            f"Login: {user:<15} Name: Umer OS Operator\n"
            f"Directory: /home/{user:<12} Shell: /bin/bash\n"
            f"On since {time.strftime('%b %d %H:%M')} (:0) 0 minutes idle"
        )

class WCommand(ShellCommand):
    name = "w"
    help_text = "Show who is logged on and what they are doing"
    category = "User & Group"
    def execute(self, ctx, args):
        t_str = time.strftime("%H:%M:%S")
        uptime = int(time.monotonic() - ctx.kernel._boot_time)
        user = ctx.shell.current_user
        return (
            f" {t_str} up {uptime}s, 1 user, load average: 0.04, 0.02, 0.01\n"
            f"USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT\n"
            f"{user:<8} :0       :0               01:27   .      0.05s  0.01s -bash"
        )

class LastCommand(ShellCommand):
    name = "last"
    help_text = "Show a list of last logged in users"
    category = "User & Group"
    def execute(self, ctx, args):
        user = ctx.shell.current_user
        t_str = time.strftime("%a %b %d %H:%M")
        return (
            f"{user:<8} :0           :0               {t_str}   still logged in\n"
            f"reboot   system boot  5.4.0-UmerOS     {t_str}   still running\n\n"
            f"wtmp begins {t_str} 2026"
        )

class LastlogCommand(ShellCommand):
    name = "lastlog"
    help_text = "Reports the most recent login of all users"
    category = "User & Group"
    def execute(self, ctx, args):
        user = ctx.shell.current_user
        t_str = time.strftime("%a %b %d %H:%M:%S %z %Y")
        return (
            "Username         Port     From             Latest\n"
            "root                                       **Never logged in**\n"
            f"{user:<16} tty1                      {t_str}\n"
        )

class UseraddCommand(ShellCommand):
    name = "useradd"
    help_text = "Create a new user account"
    category = "User & Group"
    
    def execute(self, ctx, args):
        if not args: return "useradd: missing username"
        username = args[-1]
        try:
            passwd = ctx.kernel.vfs.read_file("/etc/passwd")
            passwd += f"{username}:x:1001:1001:{username}:/home/{username}:/bin/bash\n"
            ctx.kernel.vfs.write_file("/etc/passwd", passwd)
            ctx.kernel.vfs.mkdir(f"/home/{username}", parents=True)
            return ""
        except Exception as e:
            return f"useradd: {e}"

class AdduserCommand(ShellCommand):
    name = "adduser"
    help_text = "Create a new user account interface"
    category = "User & Group"
    def execute(self, ctx, args):
        return UseraddCommand().execute(ctx, args)

class UserdelCommand(ShellCommand):
    name = "userdel"
    help_text = "Delete a user account"
    category = "User & Group"
    
    def execute(self, ctx, args):
        if not args: return "userdel: missing username"
        username = args[-1]
        try:
            passwd = ctx.kernel.vfs.read_file("/etc/passwd")
            lines = [l for l in passwd.splitlines() if not l.startswith(f"{username}:")]
            ctx.kernel.vfs.write_file("/etc/passwd", "\n".join(lines) + "\n")
            return ""
        except Exception as e:
            return f"userdel: {e}"

class UsermodCommand(ShellCommand):
    name = "usermod"
    help_text = "Modify a user account (-aG add to group)"
    category = "User & Group"
    
    def execute(self, ctx, args):
        if len(args) < 2: return "usermod: missing argument"
        username = args[-1]
        return f"usermod: updated configuration for user '{username}'"

class PasswdCommand(ShellCommand):
    name = "passwd"
    help_text = "Change user password"
    category = "User & Group"
    
    def execute(self, ctx, args):
        username = args[0] if args else ctx.shell.current_user
        return f"passwd: password updated successfully for '{username}'"

class GroupaddCommand(ShellCommand):
    name = "groupadd"
    help_text = "Add a new group"
    category = "User & Group"
    
    def execute(self, ctx, args):
        if not args: return "groupadd: missing group name"
        group = args[-1]
        try:
            grp = ctx.kernel.vfs.read_file("/etc/group")
            grp += f"{group}:x:1002:\n"
            ctx.kernel.vfs.write_file("/etc/group", grp)
            return ""
        except Exception as e:
            return f"groupadd: {e}"

class GroupdelCommand(ShellCommand):
    name = "groupdel"
    help_text = "Delete a group"
    category = "User & Group"
    
    def execute(self, ctx, args):
        if not args: return "groupdel: missing group name"
        group = args[-1]
        try:
            grp = ctx.kernel.vfs.read_file("/etc/group")
            lines = [l for l in grp.splitlines() if not l.startswith(f"{group}:")]
            ctx.kernel.vfs.write_file("/etc/group", "\n".join(lines) + "\n")
            return ""
        except Exception as e:
            return f"groupdel: {e}"

class GroupmodCommand(ShellCommand):
    name = "groupmod"
    help_text = "Modify a user group (-n new name)"
    category = "User & Group"
    def execute(self, ctx, args):
        return ""

class SudoCommand(ShellCommand):
    name = "sudo"
    help_text = "Execute a command as superuser or root"
    category = "User & Group"
    
    def execute(self, ctx, args):
        if not args: return "usage: sudo -h | -K | -k | -V"
        sub_cmd = args[0]
        sub_args = args[1:]
        
        # Execute sub_cmd with root context
        orig_user = ctx.shell.current_user
        ctx.shell.current_user = "root"
        try:
            if sub_cmd in ctx.shell.registry:
                res = ctx.shell.registry[sub_cmd].execute(ctx, sub_args)
            else:
                res = f"sudo: {sub_cmd}: command not found"
        finally:
            ctx.shell.current_user = orig_user
        return res

class SuCommand(ShellCommand):
    name = "su"
    help_text = "Switch user account or become superuser"
    category = "User & Group"
    
    def execute(self, ctx, args):
        user = args[0].replace("-", "") if args else "root"
        if not user: user = "root"
        ctx.shell.current_user = user
        return f"Switched to user {user}."

class ChgrpCommand(ShellCommand):
    name = "chgrp"
    help_text = "Change file or directory group"
    category = "User & Group"
    
    def execute(self, ctx, args):
        if len(args) < 2: return "chgrp: missing operand"
        group = args[0]
        target = args[1]
        try:
            ctx.kernel.vfs.chown(target, ctx.shell.current_user, group)
            return ""
        except Exception as e:
            return f"chgrp: {e}"

# ============================================================================
# 8. PACKAGE INSTALLATION COMMANDS
# ============================================================================

class AptGetCommand(ShellCommand):
    name = "apt-get"
    help_text = "APT package handling utility (install, update, remove)"
    category = "Packages"
    
    def execute(self, ctx, args):
        if not args: return "apt-get 2.0.2 (amd64)"
        action = args[0]
        pkg = args[1] if len(args) > 1 else ""
        if action == "install":
            return f"Reading package lists... Done\nBuilding dependency tree... Done\nThe following NEW packages will be installed:\n  {pkg}\n0 upgraded, 1 newly installed, 0 to remove.\nUnpacking {pkg}... Setting up {pkg}..."
        return f"[apt-get] Executed {action} {pkg}"

class AptCommand(ShellCommand):
    name = "apt"
    help_text = "Commandline package manager (install, search, list, show)"
    category = "Packages"
    
    def execute(self, ctx, args):
        if not args: return "apt 2.0.2 (amd64)"
        action = args[0]
        pkg = args[1] if len(args) > 1 else ""
        if action == "search":
            return f"{pkg}/stable 1.2.0-1 amd64\n  High performance package for {pkg}"
        elif action == "list":
            return "Listing... Done\ncore/stable 2.1.0 amd64 [installed]\npython3/stable 3.10.0 amd64 [installed]"
        return AptGetCommand().execute(ctx, args)

class DpkgCommand(ShellCommand):
    name = "dpkg"
    help_text = "Debian package manager (-i install, -l list)"
    category = "Packages"
    
    def execute(self, ctx, args):
        if "-l" in args:
            return "Desired=Unknown/Install/Remove/Purge/Hold\n|| Name           Version      Architecture Description\n++=-==============-============-============-=========================\nii  umer-core      2.1.0        amd64        UmerOS Kernel Core Package"
        pkg = args[-1] if args else "package.deb"
        return f"(Reading database ... 120495 files and directories currently installed.)\nPreparing to unpack {pkg} ...\nUnpacking {pkg} ...\nSetting up {pkg} ..."

class YumCommand(ShellCommand):
    name = "yum"
    help_text = "Yellowdog Updater Modified package manager (install, search, list)"
    category = "Packages"
    def execute(self, ctx, args):
        return AptCommand().execute(ctx, args)

class DnfCommand(ShellCommand):
    name = "dnf"
    help_text = "DANDIFIED YUM package manager"
    category = "Packages"
    def execute(self, ctx, args):
        return AptCommand().execute(ctx, args)

class RpmCommand(ShellCommand):
    name = "rpm"
    help_text = "RPM Package Manager (-i install)"
    category = "Packages"
    def execute(self, ctx, args):
        return DpkgCommand().execute(ctx, args)

class SnapCommand(ShellCommand):
    name = "snap"
    help_text = "Snap package management utility (install, find, list)"
    category = "Packages"
    
    def execute(self, ctx, args):
        if "list" in args:
            return "Name    Version    Rev    Tracking       Publisher   Notes\ncore    16-2.54    1200   latest/stable  canonical*  core\n"
        pkg = args[-1] if args else "app"
        return f"{pkg} 1.0.0 installed"

class FlatpakCommand(ShellCommand):
    name = "flatpak"
    help_text = "Flatpak application deployment framework"
    category = "Packages"
    def execute(self, ctx, args):
        return SnapCommand().execute(ctx, args)

class MakeCommand(ShellCommand):
    name = "make"
    help_text = "GNU make utility to maintain groups of programs"
    category = "Packages"
    def execute(self, ctx, args):
        return "make: Nothing to be done for 'all'."

# ============================================================================
# 9. PROCESS RELATED COMMANDS
# ============================================================================

class HistoryCommand(ShellCommand):
    name = "history"
    help_text = "Display command history"
    category = "Process Management"
    
    def execute(self, ctx, args):
        lines = []
        for idx, cmd in enumerate(ctx.shell.history):
            lines.append(f" {idx+1:>5}  {cmd}")
        return "\n".join(lines)

class TopCommand(ShellCommand):
    name = "top"
    help_text = "Display Linux processes"
    category = "Process Management"
    
    def execute(self, ctx, args):
        stats = ctx.kernel.status()
        uptime_sec = int(time.monotonic() - ctx.kernel._boot_time)
        out = f"top - {time.strftime('%H:%M:%S')} up {uptime_sec}s,  1 user,  load average: 0.05, 0.02, 0.01\n"
        out += f"Tasks: {stats['scheduler_tasks']} total,   {stats['running']} running\n"
        out += "%Cpu(s):  1.5 us,  0.5 sy,  0.0 ni, 98.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st\n"
        out += "KiB Mem :  4194304 total,  2048000 free,  1024000 used,  1122304 buff/cache\n"
        out += "\n  PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND\n"
        
        if hasattr(ctx.kernel.scheduler, '_tasks'):
            for pid, task in ctx.kernel.scheduler._tasks.items():
                state_char = "R" if task.state == "RUNNING" else "S" if task.state == "READY" else "Z"
                out += f"{pid:>5} root      20   0  100000   4000   2000 {state_char}   0.1  0.1   0:00.10 {task.name}\n"
        else:
            out += "    1 root      20   0  100000   4000   2000 R   0.1  0.1   0:00.10 init\n"
        return out

class PsCommand(ShellCommand):
    name = "ps"
    help_text = "Report a snapshot of the current processes"
    category = "Process Management"
    
    def execute(self, ctx, args):
        out = "  PID TTY          TIME CMD\n"
        if hasattr(ctx.kernel.scheduler, '_tasks'):
            for pid, task in ctx.kernel.scheduler._tasks.items():
                out += f"{pid:>5} ?        00:00:00 {task.name}\n"
        else:
            out += "    1 ?        00:00:00 init\n"
        return out

class KillCommand(ShellCommand):
    name = "kill"
    help_text = "Send a signal to a process (e.g. kill 101)"
    category = "Process Management"
    
    def execute(self, ctx, args):
        if not args: return "kill: usage: kill [-s sigspec | -n signum | -sigspec] pid | jobspec ..."
        pid_str = args[-1]
        try:
            pid = int(pid_str)
            if hasattr(ctx.kernel.scheduler, '_tasks'):
                if pid in ctx.kernel.scheduler._tasks:
                    ctx.kernel.scheduler.terminate(pid)
                    return f"Sent SIGTERM to process {pid}"
                else:
                    return f"-bash: kill: ({pid}) - No such process"
            return "Scheduler API mismatch for kill."
        except ValueError:
            return f"-bash: kill: {pid_str}: arguments must be process or job IDs"

class KillallCommand(ShellCommand):
    name = "killall"
    help_text = "Kill processes by name (e.g. killall umer-worker)"
    category = "Process Management"
    
    def execute(self, ctx, args):
        if not args: return "killall: usage: killall process_name"
        target_name = args[0]
        killed = 0
        if hasattr(ctx.kernel.scheduler, '_tasks'):
            for pid, task in list(ctx.kernel.scheduler._tasks.items()):
                if task.name == target_name:
                    ctx.kernel.scheduler.terminate(pid)
                    killed += 1
            if killed > 0:
                return f"Terminated {killed} process(es) named '{target_name}'"
            return f"{target_name}: no process found"
        return "Scheduler API mismatch."

class PkillCommand(ShellCommand):
    name = "pkill"
    help_text = "Signal processes based on name pattern"
    category = "Process Management"
    
    def execute(self, ctx, args):
        return KillallCommand().execute(ctx, args)

class PstreeCommand(ShellCommand):
    name = "pstree"
    help_text = "Display a tree of processes"
    category = "Process Management"
    
    def execute(self, ctx, args):
        return (
            "init(1)─┬─systemd-journal(101)\n"
            "        ├─systemd-udevd(102)\n"
            "        ├─umer-scheduler(103)─┬─worker-1(104)\n"
            "        │                     └─worker-2(105)\n"
            "        └─bash(200)───pstree(301)"
        )

class PmapCommand(ShellCommand):
    name = "pmap"
    help_text = "Report memory map of a process"
    category = "Process Management"
    
    def execute(self, ctx, args):
        pid = args[0] if args else "1"
        return (
            f"{pid}:   bash\n"
            "000055c0a1b2c000   1024K r-x-- bash\n"
            "000055c0a1c2c000    128K r---- bash\n"
            "000055c0a1c4c000     64K rw--- bash\n"
            "total           1216K"
        )

class HtopCommand(ShellCommand):
    name = "htop"
    help_text = "Interactive and colorful process viewer"
    category = "Process Management"
    def execute(self, ctx, args):
        return TopCommand().execute(ctx, args)

class PgrepCommand(ShellCommand):
    name = "pgrep"
    help_text = "Look up processes based on name pattern"
    category = "Process Management"
    
    def execute(self, ctx, args):
        if not args: return ""
        pattern = args[0]
        pids = []
        if hasattr(ctx.kernel.scheduler, '_tasks'):
            for pid, task in ctx.kernel.scheduler._tasks.items():
                if pattern in task.name:
                    pids.append(str(pid))
        return "\n".join(pids) if pids else "101"

class PidofCommand(ShellCommand):
    name = "pidof"
    help_text = "Find the process ID of a running program"
    category = "Process Management"
    def execute(self, ctx, args):
        return PgrepCommand().execute(ctx, args)

class BgCommand(ShellCommand):
    name = "bg"
    help_text = "Resume stopped jobs in the background"
    category = "Process Management"
    def execute(self, ctx, args):
        return "[1]+ job running &"

class FgCommand(ShellCommand):
    name = "fg"
    help_text = "Bring a job to the foreground"
    category = "Process Management"
    def execute(self, ctx, args):
        return "[1]+ job brought to foreground"

class LsofCommand(ShellCommand):
    name = "lsof"
    help_text = "List open files by running processes"
    category = "Process Management"
    
    def execute(self, ctx, args):
        return (
            "COMMAND     PID USER   FD   TYPE DEVICE SIZE/OFF   NODE NAME\n"
            "init          1 root  cwd    DIR    8,2     4096      2 /\n"
            "bash        200 umer  cwd    DIR    8,2     4096 120485 /home/umer\n"
            "bash        200 umer    0u   CHR  136,0      0t0      3 /dev/pts/0"
        )

class TrapCommand(ShellCommand):
    name = "trap"
    help_text = "Trap signals and execute commands"
    category = "Process Management"
    def execute(self, ctx, args):
        return ""

class WaitCommand(ShellCommand):
    name = "wait"
    help_text = "Wait for process completion"
    category = "Process Management"
    def execute(self, ctx, args):
        return ""

class NohupCommand(ShellCommand):
    name = "nohup"
    help_text = "Run a command immune to hangups, with output to a non-tty"
    category = "Process Management"
    
    def execute(self, ctx, args):
        if not args: return "nohup: usage: nohup COMMAND [ARG]..."
        sub_cmd = args[0]
        sub_args = args[1:]
        if sub_cmd in ctx.shell.registry:
            res = ctx.shell.registry[sub_cmd].execute(ctx, sub_args)
            ctx.kernel.vfs.write_file("nohup.out", res + "\n")
            return "nohup: appending output to nohup.out"
        return f"nohup: {sub_cmd}: command not found"

# ============================================================================
# 10. SYSTEM MANAGEMENT COMMANDS
# ============================================================================

class UnameCommand(ShellCommand):
    name = "uname"
    help_text = "Print system information (-a all, -r kernel release, -m machine)"
    category = "System Management"
    
    def execute(self, ctx, args):
        show_all = "-a" in args or "--all" in args
        if show_all:
            return "UmerOS UmerOS-Node1 5.4.0-UmerOS #1 SMP PREEMPT 2026 x86_64 GNU/Linux"
        if "-r" in args:
            return "5.4.0-UmerOS"
        if "-m" in args:
            return "x86_64"
        return "UmerOS"

class UptimeCommand(ShellCommand):
    name = "uptime"
    help_text = "Tell how long the system has been running"
    category = "System Management"
    
    def execute(self, ctx, args):
        uptime_sec = int(time.monotonic() - ctx.kernel._boot_time)
        t_str = time.strftime("%H:%M:%S")
        return f" {t_str} up {uptime_sec}s,  1 user,  load average: 0.02, 0.01, 0.00"

class DateCommand(ShellCommand):
    name = "date"
    help_text = "Display current date and time"
    category = "System Management"
    def execute(self, ctx, args):
        return time.strftime("%a %b %d %H:%M:%S %Z %Y")

class TimedatectlCommand(ShellCommand):
    name = "timedatectl"
    help_text = "Query and change system clock and time zone settings"
    category = "System Management"
    
    def execute(self, ctx, args):
        return (
            f"               Local time: {time.strftime('%a %Y-%m-%d %H:%M:%S %Z')}\n"
            "           Universal time: 2026-07-31 07:54:00 UTC\n"
            "                 RTC time: 2026-07-31 07:54:00\n"
            "                Time zone: Asia/Karachi (PKT, +0500)\n"
            "System clock synchronized: yes\n"
            "              NTP service: active"
        )

class CalCommand(ShellCommand):
    name = "cal"
    help_text = "Display current month calendar"
    category = "System Management"
    
    def execute(self, ctx, args):
        return (
            "      July 2026      \n"
            "Su Mo Tu We Th Fr Sa\n"
            "          1  2  3  4\n"
            " 5  6  7  8  9 10 11\n"
            "12 13 14 15 16 17 18\n"
            "19 20 21 22 23 24 25\n"
            "26 27 28 29 30 \033[7m31\033[0m"
        )

class UlimitCommand(ShellCommand):
    name = "ulimit"
    help_text = "View or limit system resource limits (-a all)"
    category = "System Management"
    
    def execute(self, ctx, args):
        return (
            "real-time file limit        (-f) unlimited\n"
            "pending signals             (-i) 31754\n"
            "open files                  (-n) 102400\n"
            "stack size          (kbytes, -s) 8192\n"
            "virtual memory      (kbytes, -v) unlimited"
        )

class ShutdownCommand(ShellCommand):
    name = "shutdown"
    help_text = "Halt, power-off or reboot the machine"
    category = "System Management"
    
    def execute(self, ctx, args):
        ctx.kernel.request_shutdown()
        return "System is shutting down now!"

class ModprobeCommand(ShellCommand):
    name = "modprobe"
    help_text = "Add and remove modules from the Linux Kernel"
    category = "System Management"
    
    def execute(self, ctx, args):
        if not args: return "modprobe: missing module name"
        mod = args[-1]
        return f"modprobe: Module {mod} loaded into kernel ring buffer."

class DmesgCommand(ShellCommand):
    name = "dmesg"
    help_text = "Print or control the kernel ring buffer"
    category = "System Management"
    
    def execute(self, ctx, args):
        try:
            return ctx.kernel.vfs.read_file("/var/log/dmesg.log")
        except Exception:
            return "[ 0.000000] UmerOS Quantum Kernel initialized successfully."

# ============================================================================
# 11. DISK USAGE COMMANDS
# ============================================================================

class DfCommand(ShellCommand):
    name = "df"
    help_text = "Check free and used disk space on mounted filesystems (-h, -i)"
    category = "Disk Usage"
    
    def execute(self, ctx, args):
        if "-i" in args:
            return (
                "Filesystem     Inodes  IUsed  IFree IUse% Mounted on\n"
                "qfs_root      3000000 120485 2879515    5% /\n"
                "devtmpfs       500000      0  500000    0% /dev"
            )
        return (
            "Filesystem     1K-blocks      Used Available Use% Mounted on\n"
            "udev             2000000         0   2000000   0% /dev\n"
            "tmpfs             400000      1200    398800   1% /run\n"
            "qfs_root        50000000   5000000  45000000  10% /\n"
            "tmpfs            2000000         0   2000000   0% /dev/shm"
        )

class FdiskCommand(ShellCommand):
    name = "fdisk"
    help_text = "Display disk partitions, sizes, and types (-l)"
    category = "Disk Usage"
    
    def execute(self, ctx, args):
        return (
            "Disk /dev/sda: 500 GiB, 536870912000 bytes, 1048576000 sectors\n"
            "Disk model: QFS Quantum Disk\n"
            "Units: sectors of 1 * 512 = 512 bytes\n\n"
            "Device     Start        End    Sectors  Size Type\n"
            "/dev/sda1   2048    1050623    1048576  512M EFI System\n"
            "/dev/sda2 1050624 1007615999 1006565376  480G Linux filesystem\n"
            "/dev/sda3 1007616000 1048573951   40957952 19.5G Linux swap"
        )

class MountCommand(ShellCommand):
    name = "mount"
    help_text = "Mount a filesystem or show currently mounted filesystems"
    category = "Disk Usage"
    
    def execute(self, ctx, args):
        try:
            return ctx.kernel.vfs.read_file("/proc/mounts")
        except Exception:
            return "qfs_root / qfs rw,relatime 0 0"

class FindmntCommand(ShellCommand):
    name = "findmnt"
    help_text = "Display target mount point for all file systems"
    category = "Disk Usage"
    
    def execute(self, ctx, args):
        return (
            "TARGET  SOURCE   FSTYPE  OPTIONS\n"
            "/       qfs_root qfs     rw,relatime\n"
            "├─/proc proc     proc    rw,nosuid,nodev,noexec\n"
            "├─/sys  sysfs    sysfs   rw,nosuid,nodev,noexec\n"
            "└─/dev  devtmpfs devtmpfs rw,nosuid,mode=755"
        )

# ============================================================================
# 12. SSH & REMOTE COMMANDS
# ============================================================================

class SshCommand(ShellCommand):
    name = "ssh"
    help_text = "Connect to a remote host via SSH"
    category = "SSH & Remote"
    
    def execute(self, ctx, args):
        if not args: return "usage: ssh [-46b] [user@]hostname [command]"
        host = args[-1]
        return f"Connecting to {host}... Connected.\nWelcome to UmerOS Remote Shell.\n{host}$ "

class SshKeygenCommand(ShellCommand):
    name = "ssh-keygen"
    help_text = "Generate SSH key pairs"
    category = "SSH & Remote"
    
    def execute(self, ctx, args):
        ctx.kernel.vfs.mkdir("/home/umer/.ssh", parents=True)
        ctx.kernel.vfs.write_file("/home/umer/.ssh/id_rsa", "-----BEGIN OPENSSH PRIVATE KEY-----\nKEY_DATA\n-----END OPENSSH PRIVATE KEY-----")
        ctx.kernel.vfs.write_file("/home/umer/.ssh/id_rsa.pub", "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ... umer@UmerOS")
        return "Generating public/private rsa key pair.\nYour identification has been saved in /home/umer/.ssh/id_rsa.\nYour public key has been saved in /home/umer/.ssh/id_rsa.pub."

class ServiceCommand(ShellCommand):
    name = "service"
    help_text = "Run a System V init script or systemd service"
    category = "SSH & Remote"
    
    def execute(self, ctx, args):
        if len(args) < 2: return "service: missing service or command"
        srv, action = args[0], args[1]
        return f" * {action}ing {srv} daemon... [ OK ]"

class TelnetCommand(ShellCommand):
    name = "telnet"
    help_text = "User interface to the TELNET protocol"
    category = "SSH & Remote"
    
    def execute(self, ctx, args):
        host = args[0] if args else "127.0.0.1"
        return f"Trying {host}...\nConnected to {host}.\nEscape character is '^]'."

# ============================================================================
# 13. VARIABLE & SHELL MANAGEMENT COMMANDS
# ============================================================================

class LetCommand(ShellCommand):
    name = "let"
    help_text = "Evaluate arithmetic expression"
    category = "Variables & Shell"
    def execute(self, ctx, args):
        return ""

class ExportCommand(ShellCommand):
    name = "export"
    help_text = "Export environment variables (e.g. export PATH=/bin)"
    category = "Variables & Shell"
    
    def execute(self, ctx, args):
        if not hasattr(ctx.shell, "env"): ctx.shell.env = {}
        if args:
            for a in args:
                if "=" in a:
                    k, v = a.split("=", 1)
                    ctx.shell.env[k] = v.strip('"')
            return ""
        lines = [f"declare -x {k}=\"{v}\"" for k, v in getattr(ctx.shell, "env", {}).items()]
        return "\n".join(lines)

class DeclareCommand(ShellCommand):
    name = "declare"
    help_text = "Declare variables and give them attributes"
    category = "Variables & Shell"
    def execute(self, ctx, args):
        return ExportCommand().execute(ctx, args)

class SetCommand(ShellCommand):
    name = "set"
    help_text = "List names and values of shell variables and functions"
    category = "Variables & Shell"
    def execute(self, ctx, args):
        return ExportCommand().execute(ctx, args)

class UnsetCommand(ShellCommand):
    name = "unset"
    help_text = "Remove environment variable"
    category = "Variables & Shell"
    
    def execute(self, ctx, args):
        if hasattr(ctx.shell, "env") and args:
            ctx.shell.env.pop(args[0], None)
        return ""

class AliasCommand(ShellCommand):
    name = "alias"
    help_text = "Create an alias for a command (e.g. alias ll='ls -l')"
    category = "Variables & Shell"
    
    def execute(self, ctx, args):
        if not hasattr(ctx.shell, "aliases"): ctx.shell.aliases = {}
        if args:
            raw = " ".join(args)
            if "=" in raw:
                name, val = raw.split("=", 1)
                ctx.shell.aliases[name.strip()] = val.strip().strip("'").strip('"')
                return ""
        lines = [f"alias {k}='{v}'" for k, v in getattr(ctx.shell, "aliases", {}).items()]
        return "\n".join(lines)

class WatchCommand(ShellCommand):
    name = "watch"
    help_text = "Execute a program periodically (-n interval)"
    category = "Variables & Shell"
    
    def execute(self, ctx, args):
        sub_cmd = args[-1] if args else "status"
        if sub_cmd in ctx.shell.registry:
            return ctx.shell.registry[sub_cmd].execute(ctx, [])
        return ""

class SleepCommand(ShellCommand):
    name = "sleep"
    help_text = "Delay for a specified amount of time"
    category = "Variables & Shell"
    
    def execute(self, ctx, args):
        sec = float(args[0]) if args else 1.0
        time.sleep(min(sec, 2.0))
        return ""

class AtCommand(ShellCommand):
    name = "at"
    help_text = "Queue, examine or delete jobs for later execution"
    category = "Variables & Shell"
    def execute(self, ctx, args):
        return "job 1 at " + time.strftime("%H:%M")


# ============================================================================
# EXPORT ALL COMMANDS
# ============================================================================

COMMANDS = [
    # Hardware Info
    LscpuCommand(), LsblkCommand(), LspciCommand(), LsusbCommand(), LshwCommand(),
    DmidecodeCommand(), HdparmCommand(), BadblocksCommand(), FsckCommand(),
    
    # Searching
    FindCommand(), GrepCommand(), LocateCommand(), WhichCommand(), WhereIsCommand(),
    AwkCommand(), SedCommand(),
    
    # File Commands
    MkdirCommand(), RmCommand(), CpCommand(), MvCommand(), LnCommand(), TouchCommand(),
    CatCommand(), HeadCommand(), TailCommand(), MoreCommand(), LessCommand(),
    NanoCommand(), ViCommand(), VimCommand(), GpgCommand(), WcCommand(), XargsCommand(),
    CutCommand(), ShredCommand(), DiffCommand(), SourceCommand(), TeeCommand(),
    
    # Directory Navigation
    LsCommand(), PwdCommand(), CdCommand(), DirsCommand(),
    
    # File Compression
    TarCommand(), GzipCommand(), GunzipCommand(), Bzip2Command(), Bunzip2Command(),
    
    # File Transfer
    ScpCommand(), RsyncCommand(), WgetCommand(), CurlCommand(), FtpCommand(), SftpCommand(),
    
    # User & Group Commands
    WhoAmICommand(), IdCommand(), GroupsCommand(), WhoCommand(), UsersCommand(),
    FingerCommand(), WCommand(), LastCommand(), LastlogCommand(),
    UseraddCommand(), AdduserCommand(), UserdelCommand(), UsermodCommand(), PasswdCommand(),
    GroupaddCommand(), GroupdelCommand(), GroupmodCommand(), SudoCommand(), SuCommand(), ChgrpCommand(),
    
    # Package Managers
    AptGetCommand(), AptCommand(), DpkgCommand(), YumCommand(), DnfCommand(), RpmCommand(),
    SnapCommand(), FlatpakCommand(), MakeCommand(),
    
    # Process Management
    HistoryCommand(), TopCommand(), HtopCommand(), PsCommand(), PstreeCommand(), PmapCommand(),
    KillCommand(), KillallCommand(), PkillCommand(), PgrepCommand(), PidofCommand(),
    BgCommand(), FgCommand(), LsofCommand(), TrapCommand(), WaitCommand(), NohupCommand(),
    
    # System Management
    UnameCommand(), UptimeCommand(), DateCommand(), TimedatectlCommand(), CalCommand(),
    UlimitCommand(), ShutdownCommand(), ModprobeCommand(), DmesgCommand(),
    
    # Disk Usage
    DfCommand(), FdiskCommand(), MountCommand(), FindmntCommand(), DuCommand(),
    
    # SSH & Remote
    SshCommand(), SshKeygenCommand(), ServiceCommand(), TelnetCommand(),
    
    # Permissions
    ChmodCommand(), ChownCommand(),
    
    # Variables & Shell Utilities
    LetCommand(), ExportCommand(), DeclareCommand(), SetCommand(), UnsetCommand(),
    AliasCommand(), WatchCommand(), SleepCommand(), AtCommand(), ClearCommand(),
    HelpCommand(), ManCommand()
]

def get_registry():
    return {cmd.name: cmd for cmd in COMMANDS}
