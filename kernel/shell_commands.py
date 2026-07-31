"""
Umer OS Shell Command Registry
==============================
Implements comprehensive standard Linux commands (User Info, Filesystem,
Permissions, Process Management, Network, System Info, Search, and Utilities)
for the FluidicShell environment.
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
# 1. FILE & DIRECTORY COMMANDS
# ============================================================================

class PwdCommand(ShellCommand):
    name = "pwd"
    help_text = "Print name of current/working directory"
    category = "Filesystem"
    
    def execute(self, ctx, args):
        return ctx.kernel.vfs.cwd

class CdCommand(ShellCommand):
    name = "cd"
    help_text = "Change the shell working directory"
    category = "Filesystem"
    
    def execute(self, ctx, args):
        path = args[0] if args else "/home/umer"
        try:
            ctx.kernel.vfs.cd(path)
            return ""
        except Exception as e:
            return f"-bash: cd: {path}: {str(e)}"

class LsCommand(ShellCommand):
    name = "ls"
    help_text = "List directory contents (-l long format, -a show hidden)"
    category = "Filesystem"
    
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

class MkdirCommand(ShellCommand):
    name = "mkdir"
    help_text = "Make directories (-p create parent directories)"
    category = "Filesystem"
    
    def execute(self, ctx, args):
        if not args:
            return "mkdir: missing operand"
        
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
    category = "Filesystem"
    
    def execute(self, ctx, args):
        if not args:
            return "rm: missing operand"
            
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

class RmDirCommand(ShellCommand):
    name = "rmdir"
    help_text = "Remove empty directories"
    category = "Filesystem"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if not targets: return "rmdir: missing operand"
        output = []
        for d in targets:
            try:
                ctx.kernel.vfs.rmdir(d)
            except Exception as e:
                output.append(f"rmdir: failed to remove '{d}': {str(e)}")
        return "\n".join(output)

class TouchCommand(ShellCommand):
    name = "touch"
    help_text = "Change file timestamps or create empty files"
    category = "Filesystem"
    
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
    help_text = "Concatenate files and print on the standard output"
    category = "Filesystem"
    
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

class CpCommand(ShellCommand):
    name = "cp"
    help_text = "Copy files and directories (-r recursive)"
    category = "Filesystem"
    
    def execute(self, ctx, args):
        recursive = "-r" in args or "-R" in args or "-a" in args
        targets = [a for a in args if not a.startswith("-")]
        if len(targets) < 2:
            return "cp: missing destination file operand after '" + (targets[0] if targets else "") + "'"
        
        src, dest = targets[0], targets[1]
        try:
            ctx.kernel.vfs.cp(src, dest, recursive=recursive)
            return ""
        except Exception as e:
            return f"cp: {str(e)}"

class MvCommand(ShellCommand):
    name = "mv"
    help_text = "Move (rename) files"
    category = "Filesystem"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if len(targets) < 2:
            return "mv: missing destination file operand"
        src, dest = targets[0], targets[1]
        try:
            ctx.kernel.vfs.mv(src, dest)
            return ""
        except Exception as e:
            return f"mv: {str(e)}"

class HeadCommand(ShellCommand):
    name = "head"
    help_text = "Output the first part of files (-n lines)"
    category = "Filesystem"
    
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
            else:
                i += 1
                
        if not filename: return "head: missing file operand"
        try:
            content = ctx.kernel.vfs.read_file(filename)
            lines = content.splitlines()[:lines_count]
            return "\n".join(lines)
        except Exception as e:
            return f"head: cannot open '{filename}': {str(e)}"

class TailCommand(ShellCommand):
    name = "tail"
    help_text = "Output the last part of files (-n lines)"
    category = "Filesystem"
    
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
            else:
                i += 1
                
        if not filename: return "tail: missing file operand"
        try:
            content = ctx.kernel.vfs.read_file(filename)
            lines = content.splitlines()[-lines_count:]
            return "\n".join(lines)
        except Exception as e:
            return f"tail: cannot open '{filename}': {str(e)}"

class EchoCommand(ShellCommand):
    name = "echo"
    help_text = "Display a line of text, supports > and >> redirection"
    category = "Filesystem"
    
    def execute(self, ctx, args):
        if not args: return ""
        raw = " ".join(args)
        
        # Check for redirection
        if " > " in raw or " >> " in raw:
            append = " >> " in raw
            sep = " >> " if append else " > "
            text_part, file_part = raw.split(sep, 1)
            text_part = text_part.strip().strip('"').strip("'")
            file_part = file_part.strip()
            
            try:
                if append:
                    try:
                        existing = ctx.kernel.vfs.read_file(file_part)
                        new_content = existing + text_part + "\n"
                    except Exception:
                        new_content = text_part + "\n"
                else:
                    new_content = text_part + "\n"
                ctx.kernel.vfs.write_file(file_part, new_content)
                return ""
            except Exception as e:
                return f"echo: redirection error: {str(e)}"
        
        return raw.strip('"').strip("'")

class StatCommand(ShellCommand):
    name = "stat"
    help_text = "Display file or file system status"
    category = "Filesystem"
    
    def execute(self, ctx, args):
        if not args: return "stat: missing operand"
        target = args[0]
        try:
            st = ctx.kernel.vfs.stat(target)
            ftype = "directory" if st["is_dir"] else "regular file"
            mtime_str = time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(st["mtime"]))
            return (
                f"  File: {st['name']}\n"
                f"  Size: {st['size']:<10} Blocks: 8          IO Block: 4096   {ftype}\n"
                f"Access: ({st['mode']})  Uid: (1000/{st['owner']})   Gid: (1000/{st['group']})\n"
                f"Modify: {mtime_str}"
            )
        except Exception as e:
            return f"stat: cannot stat '{target}': {str(e)}"

class WcCommand(ShellCommand):
    name = "wc"
    help_text = "Print newline, word, and byte counts for files"
    category = "Filesystem"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if not targets: return "0 0 0"
        lines_out = []
        for t in targets:
            try:
                c = ctx.kernel.vfs.read_file(t)
                l = len(c.splitlines())
                w = len(c.split())
                b = len(c.encode('utf-8'))
                lines_out.append(f" {l:>4} {w:>4} {b:>4} {t}")
            except Exception as e:
                lines_out.append(f"wc: {t}: {str(e)}")
        return "\n".join(lines_out)

class FileCommand(ShellCommand):
    name = "file"
    help_text = "Determine file type"
    category = "Filesystem"
    
    def execute(self, ctx, args):
        targets = [a for a in args if not a.startswith("-")]
        if not targets: return "file: missing operand"
        output = []
        for t in targets:
            try:
                st = ctx.kernel.vfs.stat(t)
                if st["is_dir"]:
                    output.append(f"{t}: directory")
                else:
                    output.append(f"{t}: ASCII text")
            except Exception as e:
                output.append(f"file: cannot open '{t}': {str(e)}")
        return "\n".join(output)

# ============================================================================
# 2. FILE PERMISSIONS COMMANDS
# ============================================================================

class ChmodCommand(ShellCommand):
    name = "chmod"
    help_text = "Change file mode bits (e.g. chmod 755 file)"
    category = "Permissions"
    
    def execute(self, ctx, args):
        if len(args) < 2: return "chmod: missing operand"
        mode_arg = args[0]
        target = args[1]
        
        # Translate mode numeric or symbol
        if mode_arg == "755" or mode_arg == "+x":
            mode_str = "rwxr-xr-x"
        elif mode_arg == "644":
            mode_str = "rw-r--r--"
        elif mode_arg == "700":
            mode_str = "rwx------"
        elif mode_arg == "777":
            mode_str = "rwxrwxrwx"
        else:
            mode_str = mode_arg
            
        try:
            ctx.kernel.vfs.chmod(target, mode_str)
            return ""
        except Exception as e:
            return f"chmod: {str(e)}"

class ChownCommand(ShellCommand):
    name = "chown"
    help_text = "Change file owner and group (e.g. chown umer:sudo file)"
    category = "Permissions"
    
    def execute(self, ctx, args):
        if len(args) < 2: return "chown: missing operand"
        owner_spec = args[0]
        target = args[1]
        
        if ":" in owner_spec:
            owner, group = owner_spec.split(":", 1)
        else:
            owner, group = owner_spec, None
            
        try:
            ctx.kernel.vfs.chown(target, owner, group)
            return ""
        except Exception as e:
            return f"chown: {str(e)}"

# ============================================================================
# 3. USER INFORMATION COMMANDS
# ============================================================================

class WhoAmICommand(ShellCommand):
    name = "whoami"
    help_text = "Print effective userid"
    category = "User Info"
    def execute(self, ctx, args):
        return ctx.shell.current_user

class IdCommand(ShellCommand):
    name = "id"
    help_text = "Print real and effective user and group IDs"
    category = "User Info"
    def execute(self, ctx, args):
        user = ctx.shell.current_user
        return f"uid=1000({user}) gid=1000({user}) groups=1000({user}),27(sudo),4(adm)"

class GroupsCommand(ShellCommand):
    name = "groups"
    help_text = "Print the groups a user is in"
    category = "User Info"
    def execute(self, ctx, args):
        user = ctx.shell.current_user
        return f"{user} : {user} sudo adm cdrom plugdev lpadmin lxd sambashare"

class WhoCommand(ShellCommand):
    name = "who"
    help_text = "Show who is logged on"
    category = "User Info"
    def execute(self, ctx, args):
        t = time.strftime("%Y-%m-%d %H:%M")
        return f"{ctx.shell.current_user} :0 {t} (:0)"

class UsersCommand(ShellCommand):
    name = "users"
    help_text = "Print the user names of users currently logged in"
    category = "User Info"
    def execute(self, ctx, args):
        return ctx.shell.current_user

class FingerCommand(ShellCommand):
    name = "finger"
    help_text = "User information lookup program"
    category = "User Info"
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
    category = "User Info"
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
    category = "User Info"
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
    category = "User Info"
    def execute(self, ctx, args):
        user = ctx.shell.current_user
        t_str = time.strftime("%a %b %d %H:%M:%S %z %Y")
        return (
            "Username         Port     From             Latest\n"
            "root                                       **Never logged in**\n"
            f"{user:<16} tty1                      {t_str}\n"
        )

# ============================================================================
# 4. SEARCH COMMANDS
# ============================================================================

class GrepCommand(ShellCommand):
    name = "grep"
    help_text = "Print lines that match patterns (-i ignore case, -n line numbers)"
    category = "Search"
    
    def execute(self, ctx, args):
        ignore_case = "-i" in args
        line_num = "-n" in args
        invert = "-v" in args
        
        non_flag_args = [a for a in args if not a.startswith("-")]
        if not non_flag_args:
            return "grep: missing pattern"
        pattern = non_flag_args[0]
        files = non_flag_args[1:]
        
        if not files:
            return "" # Expect stdin in bash
            
        output = []
        flags = re.IGNORECASE if ignore_case else 0
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            return f"grep: invalid pattern: {e}"

        for f in files:
            try:
                content = ctx.kernel.vfs.read_file(f)
                lines = content.splitlines()
                for idx, line in enumerate(lines):
                    matched = bool(rx.search(line))
                    if invert: matched = not matched
                    if matched:
                        prefix = f"{f}:" if len(files) > 1 else ""
                        num_str = f"{idx+1}:" if line_num else ""
                        output.append(f"{prefix}{num_str}{line}")
            except Exception as e:
                output.append(f"grep: {f}: {str(e)}")
        return "\n".join(output)

class FindCommand(ShellCommand):
    name = "find"
    help_text = "Search for files in a directory hierarchy (-name pattern)"
    category = "Search"
    
    def execute(self, ctx, args):
        path = "."
        name_pattern = None
        
        i = 0
        while i < len(args):
            if args[i] == "-name" and i + 1 < len(args):
                name_pattern = args[i+1].strip('"').strip("'")
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

class WhichCommand(ShellCommand):
    name = "which"
    help_text = "Locate a command binary"
    category = "Search"
    
    def execute(self, ctx, args):
        if not args: return ""
        cmd_name = args[0]
        if cmd_name in ctx.shell.registry:
            return f"/bin/{cmd_name}"
        return f"{cmd_name} not found"

class WhereIsCommand(ShellCommand):
    name = "whereis"
    help_text = "Locate binary, source, and manual page files for a command"
    category = "Search"
    
    def execute(self, ctx, args):
        if not args: return ""
        cmd_name = args[0]
        if cmd_name in ctx.shell.registry:
            return f"{cmd_name}: /bin/{cmd_name} /usr/bin/{cmd_name}"
        return f"{cmd_name}:"

# ============================================================================
# 5. SYSTEM & HARDWARE INFORMATION COMMANDS
# ============================================================================

class UnameCommand(ShellCommand):
    name = "uname"
    help_text = "Print system information (-a all, -r kernel release, -m machine)"
    category = "System Info"
    
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
    category = "System Info"
    
    def execute(self, ctx, args):
        uptime_sec = int(time.monotonic() - ctx.kernel._boot_time)
        t_str = time.strftime("%H:%M:%S")
        return f" {t_str} up {uptime_sec}s,  1 user,  load average: 0.02, 0.01, 0.00"

class LscpuCommand(ShellCommand):
    name = "lscpu"
    help_text = "Display information about the CPU architecture"
    category = "System Info"
    
    def execute(self, ctx, args):
        return (
            "Architecture:                    x86_64\n"
            "CPU op-mode(s):                  32-bit, 64-bit\n"
            "Byte Order:                      Little Endian\n"
            "Address sizes:                   39 bits physical, 48 bits virtual\n"
            "CPU(s):                          8\n"
            "On-line CPU(s) list:             0-7\n"
            "Vendor ID:                       QuantumGenuineIntel\n"
            "Model name:                      UmerOS Quantum AI Accelerator CPU @ 3.40GHz"
        )

class DfCommand(ShellCommand):
    name = "df"
    help_text = "Report file system disk space usage (-h human readable)"
    category = "System Info"
    
    def execute(self, ctx, args):
        return (
            "Filesystem     1K-blocks      Used Available Use% Mounted on\n"
            "udev             2000000         0   2000000   0% /dev\n"
            "tmpfs             400000      1200    398800   1% /run\n"
            "qfs_root        50000000   5000000  45000000  10% /\n"
            "tmpfs            2000000         0   2000000   0% /dev/shm"
        )

class DuCommand(ShellCommand):
    name = "du"
    help_text = "Estimate file space usage (-h human readable, -s summary)"
    category = "System Info"
    
    def execute(self, ctx, args):
        path = "."
        for a in args:
            if not a.startswith("-"): path = a
            
        try:
            st = ctx.kernel.vfs.stat(path)
            return f"{st['size'] // 1024 + 4}\t{path}"
        except Exception as e:
            return f"du: cannot access '{path}': {str(e)}"

class FreeCommand(ShellCommand):
    name = "free"
    help_text = "Display amount of free and used memory in the system (-m, -h)"
    category = "System Info"
    
    def execute(self, ctx, args):
        return (
            "              total        used        free      shared  buff/cache   available\n"
            "Mem:        4194304     1048576     2097152       16384     1048576     2883584\n"
            "Swap:       2097152           0     2097152"
        )

class DmesgCommand(ShellCommand):
    name = "dmesg"
    help_text = "Print or control the kernel ring buffer"
    category = "System Info"
    
    def execute(self, ctx, args):
        try:
            return ctx.kernel.vfs.read_file("/var/log/dmesg.log")
        except Exception:
            return "[ 0.000000] UmerOS Quantum Kernel initialized successfully."

# ============================================================================
# 6. PROCESS MANAGEMENT COMMANDS
# ============================================================================

class HistoryCommand(ShellCommand):
    name = "history"
    help_text = "Display command history"
    category = "Process & Shell"
    
    def execute(self, ctx, args):
        lines = []
        for idx, cmd in enumerate(ctx.shell.history):
            lines.append(f" {idx+1:>5}  {cmd}")
        return "\n".join(lines)

class TopCommand(ShellCommand):
    name = "top"
    help_text = "Display Linux processes"
    category = "Process & Shell"
    
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
    category = "Process & Shell"
    
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
    category = "Process & Shell"
    
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
    category = "Process & Shell"
    
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
    category = "Process & Shell"
    
    def execute(self, ctx, args):
        return KillallCommand().execute(ctx, args)

# ============================================================================
# 7. NETWORKING COMMANDS
# ============================================================================

class CurlCommand(ShellCommand):
    name = "curl"
    help_text = "Transfer a URL"
    category = "Networking"
    
    def execute(self, ctx, args):
        if not args: return "curl: try 'curl --help' or 'curl --manual' for more information"
        url = args[-1]
        if url.startswith("-"): return "curl: no URL specified!"
        
        return f"<!DOCTYPE html><html><body><h1>Response from {url}</h1><p>Fetched by UmerOS Virtual HTTP Client.</p></body></html>"

class WgetCommand(ShellCommand):
    name = "wget"
    help_text = "Non-interactive network downloader"
    category = "Networking"
    
    def execute(self, ctx, args):
        if not args: return "wget: missing URL"
        url = args[-1]
        filename = url.rstrip("/").split("/")[-1] or "index.html"
        try:
            ctx.kernel.vfs.write_file(filename, f"<!-- Downloaded from {url} -->\n<html><body>Content from {url}</body></html>")
            return f"--2026-07-31--  {url}\nConnecting to {url}... connected.\nHTTP request sent, awaiting response... 200 OK\nLength: 120 [text/html]\nSaving to: '{filename}'\n\n'{filename}' saved [120/120]"
        except Exception as e:
            return f"wget: error saving to {filename}: {e}"

class PingCommand(ShellCommand):
    name = "ping"
    help_text = "Send ICMP ECHO_REQUEST to network hosts"
    category = "Networking"
    
    def execute(self, ctx, args):
        if not args: return "ping: usage: ping host"
        host = args[-1]
        out = f"PING {host} (127.0.0.1) 56(84) bytes of data.\n"
        out += f"64 bytes from {host} (127.0.0.1): icmp_seq=1 ttl=64 time=0.045 ms\n"
        out += f"64 bytes from {host} (127.0.0.1): icmp_seq=2 ttl=64 time=0.038 ms\n"
        out += f"--- {host} ping statistics ---\n"
        out += "2 packets transmitted, 2 received, 0% packet loss, time 1001ms"
        return out

class IfconfigCommand(ShellCommand):
    name = "ifconfig"
    help_text = "Configure or display network interface parameters"
    category = "Networking"
    
    def execute(self, ctx, args):
        return (
            "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n"
            "        inet 192.168.1.100  netmask 255.255.255.0  broadcast 192.168.1.255\n"
            "        rx_packets 10420  bytes 8420100 (8.4 MB)\n"
            "        tx_packets 8920  bytes 4120900 (4.1 MB)\n\n"
            "lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536\n"
            "        inet 127.0.0.1  netmask 255.0.0.0\n"
            "        rx_packets 120  bytes 9800 (9.8 KB)\n"
            "        tx_packets 120  bytes 9800 (9.8 KB)"
        )

class IpCommand(ShellCommand):
    name = "ip"
    help_text = "Show / manipulate routing, devices, policy routing and tunnels"
    category = "Networking"
    
    def execute(self, ctx, args):
        return IfconfigCommand().execute(ctx, args)

class HostnameCommand(ShellCommand):
    name = "hostname"
    help_text = "Show or set system hostname"
    category = "Networking"
    
    def execute(self, ctx, args):
        if args:
            new_name = args[0]
            ctx.kernel.vfs.write_file("/etc/hostname", new_name + "\n")
            return ""
        try:
            return ctx.kernel.vfs.read_file("/etc/hostname").strip()
        except Exception:
            return "UmerOS-Node1"

# ============================================================================
# 8. UTILITIES & EDITORS
# ============================================================================

class ClearCommand(ShellCommand):
    name = "clear"
    help_text = "Clear the terminal screen"
    category = "Utilities"
    
    def execute(self, ctx, args):
        return "\033[H\033[2J"

class HelpCommand(ShellCommand):
    name = "help"
    help_text = "Display information about available commands"
    category = "Utilities"
    
    def execute(self, ctx, args):
        categories = {}
        for cmd in COMMANDS:
            cat = getattr(cmd, "category", "General")
            if cat not in categories: categories[cat] = []
            categories[cat].append(cmd)
            
        out = "UmerOS Shell - Supported Linux Commands Cheat Sheet\n"
        out += "=====================================================\n\n"
        for cat, cmds in categories.items():
            out += f"[{cat}]\n"
            for c in cmds:
                out += f"  {c.name:<12} - {c.help_text}\n"
            out += "\n"
        return out

class ManCommand(ShellCommand):
    name = "man"
    help_text = "An interface to the system reference manuals"
    category = "Utilities"
    
    def execute(self, ctx, args):
        if not args: return "What manual page do you want?"
        cmd_name = args[0]
        if cmd_name in ctx.shell.registry:
            cmd_obj = ctx.shell.registry[cmd_name]
            return f"MANUAL PAGE FOR '{cmd_name.upper()}'\n\nNAME\n   {cmd_name} - {cmd_obj.help_text}\n\nDESCRIPTION\n   Executes native UmerOS POSIX subsystem implementation."
        return f"No manual entry for {cmd_name}"

class NanoCommand(ShellCommand):
    name = "nano"
    help_text = "Nano's ANOther editor (simple file creator/editor)"
    category = "Utilities"
    
    def execute(self, ctx, args):
        if not args: return "nano: missing file operand"
        filename = args[0]
        if len(args) > 1:
            # Writing content directly if passed: nano file.txt "content..."
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
    help_text = "Vi / Vim text editor"
    category = "Utilities"
    
    def execute(self, ctx, args):
        return NanoCommand().execute(ctx, args)


# ============================================================================
# COMMAND REGISTRY EXPORT
# ============================================================================

COMMANDS = [
    # Filesystem
    PwdCommand(), CdCommand(), LsCommand(), MkdirCommand(), RmCommand(), RmDirCommand(),
    TouchCommand(), CatCommand(), CpCommand(), MvCommand(), HeadCommand(), TailCommand(),
    EchoCommand(), StatCommand(), WcCommand(), FileCommand(),
    
    # Permissions
    ChmodCommand(), ChownCommand(),
    
    # User Info
    WhoAmICommand(), IdCommand(), GroupsCommand(), WhoCommand(), UsersCommand(),
    FingerCommand(), WCommand(), LastCommand(), LastlogCommand(),
    
    # Search
    GrepCommand(), FindCommand(), WhichCommand(), WhereIsCommand(),
    
    # System Info
    UnameCommand(), UptimeCommand(), LscpuCommand(), DfCommand(), DuCommand(),
    FreeCommand(), DmesgCommand(),
    
    # Process & Shell
    HistoryCommand(), TopCommand(), PsCommand(), KillCommand(), KillallCommand(), PkillCommand(),
    
    # Networking
    CurlCommand(), WgetCommand(), PingCommand(), IfconfigCommand(), IpCommand(), HostnameCommand(),
    
    # Utilities & Editors
    ClearCommand(), HelpCommand(), ManCommand(), NanoCommand(), ViCommand()
]

def get_registry():
    return {cmd.name: cmd for cmd in COMMANDS}
