"""
Umer OS Shell Command Registry
==============================
Implements standard Linux commands (User Info, Filesystem, Process, Network)
for the FluidicShell environment.
"""

import time
import os

class CommandContext:
    """Provides execution context (kernel access, shell state) to commands."""
    def __init__(self, kernel, shell):
        self.kernel = kernel
        self.shell = shell

class ShellCommand:
    """Base class for shell commands."""
    name = "command"
    help_text = "No help available."
    
    def execute(self, ctx: CommandContext, args: list) -> str:
        raise NotImplementedError()

# --- FILE & DIRECTORY COMMANDS ---

class PwdCommand(ShellCommand):
    name = "pwd"
    help_text = "Print name of current/working directory"
    
    def execute(self, ctx, args):
        return ctx.kernel.vfs.cwd

class CdCommand(ShellCommand):
    name = "cd"
    help_text = "Change the shell working directory"
    
    def execute(self, ctx, args):
        path = args[0] if args else "/"
        try:
            ctx.kernel.vfs.cd(path)
            return ""
        except Exception as e:
            return f"-bash: cd: {path}: {str(e)}"

class LsCommand(ShellCommand):
    name = "ls"
    help_text = "List directory contents"
    
    def execute(self, ctx, args):
        # We simplify flags for now. Real ls handles -l, -a, etc.
        path = ctx.kernel.vfs.cwd
        for arg in args:
            if not arg.startswith("-"):
                path = arg
                
        try:
            contents = ctx.kernel.vfs.ls(path)
            return "  ".join(contents)
        except Exception as e:
            return f"ls: cannot access '{path}': {str(e)}"

class MkdirCommand(ShellCommand):
    name = "mkdir"
    help_text = "Make directories"
    
    def execute(self, ctx, args):
        if not args:
            return "mkdir: missing operand"
        
        output = []
        for d in args:
            if d.startswith("-"): continue
            try:
                ctx.kernel.vfs.mkdir(d)
            except Exception as e:
                output.append(f"mkdir: cannot create directory '{d}': {str(e)}")
        return "\n".join(output)

class RmCommand(ShellCommand):
    name = "rm"
    help_text = "Remove files or directories"
    
    def execute(self, ctx, args):
        if not args:
            return "rm: missing operand"
            
        force = "-f" in args or "-rf" in args
        recursive = "-r" in args or "-rf" in args
        
        output = []
        for target in args:
            if target.startswith("-"): continue
            try:
                ctx.kernel.vfs.rm(target, recursive=recursive)
            except Exception as e:
                if not force:
                    output.append(f"rm: cannot remove '{target}': {str(e)}")
        return "\n".join(output)

class RmDirCommand(ShellCommand):
    name = "rmdir"
    help_text = "Remove empty directories"
    
    def execute(self, ctx, args):
        if not args: return "rmdir: missing operand"
        output = []
        for d in args:
            if d.startswith("-"): continue
            try:
                ctx.kernel.vfs.rmdir(d)
            except Exception as e:
                output.append(f"rmdir: failed to remove '{d}': {str(e)}")
        return "\n".join(output)

class TouchCommand(ShellCommand):
    name = "touch"
    help_text = "Change file timestamps or create empty files"
    
    def execute(self, ctx, args):
        if not args: return "touch: missing file operand"
        output = []
        for f in args:
            if f.startswith("-"): continue
            try:
                ctx.kernel.vfs.touch(f)
            except Exception as e:
                output.append(f"touch: cannot touch '{f}': {str(e)}")
        return "\n".join(output)

class CatCommand(ShellCommand):
    name = "cat"
    help_text = "Concatenate files and print on the standard output"
    
    def execute(self, ctx, args):
        if not args: return "" # Technically hangs waiting for stdin in real Linux
        output = []
        for f in args:
            try:
                content = ctx.kernel.vfs.read_file(f)
                output.append(content)
            except Exception as e:
                output.append(f"cat: {f}: {str(e)}")
        return "\n".join(output)

# --- USER INFO COMMANDS ---

class WhoAmICommand(ShellCommand):
    name = "whoami"
    help_text = "Print effective userid"
    def execute(self, ctx, args):
        return ctx.shell.current_user

class IdCommand(ShellCommand):
    name = "id"
    help_text = "Print real and effective user and group IDs"
    def execute(self, ctx, args):
        user = ctx.shell.current_user
        return f"uid=1000({user}) gid=1000({user}) groups=1000({user}),27(sudo)"

class GroupsCommand(ShellCommand):
    name = "groups"
    help_text = "Print the groups a user is in"
    def execute(self, ctx, args):
        user = ctx.shell.current_user
        return f"{user}: {user} sudo adm cdrom plugdev lpadmin lxd sambashare"

class WhoCommand(ShellCommand):
    name = "who"
    help_text = "Show who is logged on"
    def execute(self, ctx, args):
        t = time.strftime("%Y-%m-%d %H:%M")
        return f"{ctx.shell.current_user} :0 {t} (:0)"

class UsersCommand(ShellCommand):
    name = "users"
    help_text = "Print the user names of users currently logged in"
    def execute(self, ctx, args):
        return ctx.shell.current_user

# --- SYSTEM & PROCESS COMMANDS ---

class HistoryCommand(ShellCommand):
    name = "history"
    help_text = "Display command history"
    def execute(self, ctx, args):
        lines = []
        for idx, cmd in enumerate(ctx.shell.history):
            lines.append(f" {idx+1}  {cmd}")
        return "\n".join(lines)

class TopCommand(ShellCommand):
    name = "top"
    help_text = "Display Linux processes"
    def execute(self, ctx, args):
        stats = ctx.kernel.status()
        out = f"top - {time.strftime('%H:%M:%S')} up {stats['uptime_seconds']}s,  1 user,  load average: 0.05, 0.02, 0.01\n"
        out += f"Tasks: {stats['scheduler_tasks']} total,   {stats['running']} running\n"
        out += "%Cpu(s):  1.5 us,  0.5 sy,  0.0 ni, 98.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st\n"
        out += "KiB Mem :  4194304 total,  2048000 free,  1024000 used,  1122304 buff/cache\n"
        out += "\n  PID USER      PR  NI    VIRT    RES    SHR S  %CPU %MEM     TIME+ COMMAND\n"
        
        # Pull tasks from scheduler if possible
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
    help_text = "Send a signal to a process"
    def execute(self, ctx, args):
        if not args: return "kill: usage: kill [-s sigspec | -n signum | -sigspec] pid | jobspec ... or kill -l [sigspec]"
        pid_str = args[-1]
        try:
            pid = int(pid_str)
            if hasattr(ctx.kernel.scheduler, '_tasks'):
                if pid in ctx.kernel.scheduler._tasks:
                    ctx.kernel.scheduler.terminate(pid)
                    return f"Sent SIGTERM to {pid}"
                else:
                    return f"-bash: kill: ({pid}) - No such process"
            return "Scheduler API mismatch for kill."
        except ValueError:
            return f"-bash: kill: {pid_str}: arguments must be process or job IDs"

class CurlCommand(ShellCommand):
    name = "curl"
    help_text = "Transfer a URL"
    def execute(self, ctx, args):
        if not args: return "curl: try 'curl --help' or 'curl --manual' for more information"
        url = args[-1]
        if url.startswith("-"): return "curl: no URL specified!"
        
        # Mock HTTP fetch
        return f"<!DOCTYPE html><html><body><h1>Response from {url}</h1><p>Fetched by UmerOS Virtual HTTP Client.</p></body></html>"

# --- REGISTRY ---

COMMANDS = [
    PwdCommand(), CdCommand(), LsCommand(), MkdirCommand(), RmCommand(), RmDirCommand(),
    TouchCommand(), CatCommand(), WhoAmICommand(), IdCommand(), GroupsCommand(),
    WhoCommand(), UsersCommand(), HistoryCommand(), TopCommand(), PsCommand(),
    KillCommand(), CurlCommand()
]

def get_registry():
    return {cmd.name: cmd for cmd in COMMANDS}
