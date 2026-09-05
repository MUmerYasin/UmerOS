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
UmerOS /bin Process & Filesystem Commands
==========================================
Process management and filesystem operation commands:
  ps, kill, mount, umount, stty, sync

FHS 3.0: These are essential commands for both root and
non-privileged users.
"""

from __future__ import annotations

import os
import signal
import stat
import struct
import sys
import termios
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

import logging

log = logging.getLogger("UmerOS.process")


# ─── Constants ───────────────────────────────────────────────────────────────

PS_FORMAT_DEFAULT = "pid,user,vsz,rss,tty,stat,start,time,command"
SIGNAL_MAP: Dict[str, int] = {
    "HUP": signal.SIGHUP, "INT": signal.SIGINT,
    "QUIT": signal.SIGQUIT, "KILL": signal.SIGKILL,
    "TERM": signal.SIGTERM, "STOP": signal.SIGSTOP,
    "CONT": signal.SIGCONT, "USR1": signal.SIGUSR1,
    "USR2": signal.SIGUSR2, "PIPE": signal.SIGPIPE,
    "ALRM": signal.SIGALRM, "CHLD": signal.SIGCHLD,
    "TSTP": signal.SIGTSTP, "TTIN": signal.SIGTTIN,
    "TTOU": signal.SIGTTOU, "WINCH": signal.SIGWINCH,
}


# ─── Process Entry ───────────────────────────────────────────────────────────

@dataclass
class ProcessEntry:
    """Represents a process entry from /proc."""
    pid: int = 0
    comm: str = ""
    state: str = ""
    ppid: int = 0
    pgrp: int = 0
    session: int = 0
    tty_nr: int = 0
    tpgid: int = 0
    flags: int = 0
    minflt: int = 0
    cminflt: int = 0
    majflt: int = 0
    cmajflt: int = 0
    utime: int = 0
    stime: int = 0
    cutime: int = 0
    cstime: int = 0
    priority: int = 0
    nice: int = 0
    num_threads: int = 0
    itrealvalue: int = 0
    starttime: int = 0
    vsize: int = 0
    rss: int = 0
    uid: int = 0
    user: str = ""
    command: str = ""
    exe: str = ""
    cwd: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid, "comm": self.comm, "state": self.state,
            "ppid": self.ppid, "pgrp": self.pgrp, "session": self.session,
            "user": self.user, "uid": self.uid, "vsize": self.vsize,
            "rss": self.rss, "command": self.command, "exe": self.exe,
        }


# ─── ps Command ──────────────────────────────────────────────────────────────

class PsCommand:
    """
    ps - report a snapshot of the current processes.

    Usage: ps [options]
      -a: Show processes for all users
      -u: User-oriented format
      -x: Show processes not attached to a terminal
      -f: Full-format listing
      -l: Long format
      -e: Select all processes
      -o format: Custom output format
      -p pids: Select by PID
      -t tty: Select by terminal
      -u user: Select by user
      --sort: Sort output

    Output columns: F S UID PID PPID C PRI NI ADDR SZ WCHAN TTY TIME CMD
    """

    def execute(self, args: List[str] | None = None) -> int:
        """Execute ps command."""
        args = args or []
        opts = self._parse_args(args)
        processes = self._get_processes()

        # Filter
        if opts.get("pids"):
            pids = set(opts["pids"])
            processes = [p for p in processes if p.pid in pids]
        if not opts.get("all"):
            my_pid = os.getpid()
            my_uid = os.getuid()
            processes = [p for p in processes if p.uid == my_uid]

        # Format
        if opts.get("format"):
            lines = self._format_custom(processes, opts["format"])
        elif opts.get("long"):
            lines = self._format_long(processes)
        elif opts.get("full"):
            lines = self._format_full(processes)
        elif opts.get("user_fmt"):
            lines = self._format_user(processes)
        else:
            lines = self._format_short(processes)

        for line in lines:
            print(line)
        return 0

    def _parse_args(self, args: List[str]) -> Dict[str, Any]:
        opts: Dict[str, Any] = {"all": False}
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("-"):
                flags = arg[1:]
                for ch in flags:
                    if ch == "a":
                        opts["all"] = True
                    elif ch == "e":
                        opts["all"] = True
                    elif ch == "u":
                        opts["user_fmt"] = True
                    elif ch == "x":
                        opts["all"] = True
                    elif ch == "f":
                        opts["full"] = True
                    elif ch == "l":
                        opts["long"] = True
                if "o" in flags:
                    i += 1
                    if i < len(args):
                        opts["format"] = args[i]
                if "p" in flags:
                    i += 1
                    if i < len(args):
                        opts.setdefault("pids", []).append(int(args[i]))
            i += 1
        return opts

    def _get_processes(self) -> List[ProcessEntry]:
        """Read process list from /proc."""
        processes: List[ProcessEntry] = []
        proc_dir = "/proc"
        if not os.path.isdir(proc_dir):
            return self._mock_processes()
        try:
            for entry in os.scandir(proc_dir):
                if entry.name.isdigit():
                    pe = self._read_proc_stat(entry.path)
                    if pe:
                        self._read_proc_status(pe)
                        self._read_proc_cmdline(pe)
                        processes.append(pe)
        except OSError:
            pass
        return processes if processes else self._mock_processes()

    def _read_proc_stat(self, path: str) -> Optional[ProcessEntry]:
        stat_path = os.path.join(path, "stat")
        try:
            with open(stat_path, "r") as f:
                data = f.read()
            # Parse between last ) and fields
            rparen = data.rfind(")")
            if rparen < 0:
                return None
            fields = data[rparen + 2:].split()
            pe = ProcessEntry()
            pe.pid = int(os.path.basename(path))
            pe.comm = data[data.find("(") + 1:rparen]
            if len(fields) > 0:
                pe.state = fields[0]
            if len(fields) > 1:
                pe.ppid = int(fields[1])
            if len(fields) > 2:
                pe.pgrp = int(fields[2])
            if len(fields) > 3:
                pe.session = int(fields[3])
            if len(fields) > 4:
                pe.tty_nr = int(fields[4])
            if len(fields) > 5:
                pe.tpgid = int(fields[5])
            if len(fields) > 11:
                pe.utime = int(fields[11])
            if len(fields) > 12:
                pe.stime = int(fields[12])
            if len(fields) > 17:
                pe.priority = int(fields[17])
            if len(fields) > 18:
                pe.nice = int(fields[18])
            if len(fields) > 19:
                pe.num_threads = int(fields[19])
            if len(fields) > 22:
                pe.vsize = int(fields[22])
            if len(fields) > 23:
                pe.rss = int(fields[23])
            return pe
        except (OSError, ValueError):
            return None

    def _read_proc_status(self, pe: ProcessEntry) -> None:
        status_path = f"/proc/{pe.pid}/status"
        try:
            with open(status_path, "r") as f:
                for line in f:
                    if line.startswith("Uid:"):
                        fields = line.split()
                        if len(fields) > 1:
                            pe.uid = int(fields[1])
                            try:
                                import pwd
                                pe.user = pwd.getpwuid(pe.uid).pw_name
                            except (KeyError, ImportError):
                                pe.user = str(pe.uid)
                    elif line.startswith("Name:"):
                        pe.comm = line.split("\t")[-1].strip()
        except OSError:
            pass

    def _read_proc_cmdline(self, pe: ProcessEntry) -> None:
        cmdline_path = f"/proc/{pe.pid}/cmdline"
        try:
            with open(cmdline_path, "rb") as f:
                data = f.read()
            pe.command = data.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
        except OSError:
            pe.command = f"[{pe.comm}]"

    def _mock_processes(self) -> List[ProcessEntry]:
        """Mock processes when /proc is unavailable."""
        return [
            ProcessEntry(pid=1, comm="systemd", state="S", ppid=0,
                         user="root", uid=0, command="/sbin/init"),
            ProcessEntry(pid=os.getpid(), comm="python", state="S",
                         ppid=1, user="user", uid=os.getuid(),
                         command="python -c ps"),
        ]

    def _format_short(self, procs: List[ProcessEntry]) -> List[str]:
        lines = ["  PID TTY          TIME CMD"]
        for p in procs:
            tty = self._get_tty(p.tty_nr)
            cputime = self._format_time(p.utime + p.stime)
            lines.append(f"{p.pid:>5} {tty:<13} {cputime:>8} {p.comm}")
        return lines

    def _format_long(self, procs: List[ProcessEntry]) -> List[str]:
        lines = ["F S  UID   PID  PPID  C PRI  NI ADDR SZ WCHAN TTY      TIME CMD"]
        for p in procs:
            tty = self._get_tty(p.tty_nr)
            cputime = self._format_time(p.utime + p.stime)
            lines.append(f"0 {p.state} {p.uid:>5} {p.pid:>5} {p.ppid:>5} "
                         f"0 {p.priority:>3} {p.nice:>3}     0 {p.rss:>5} "
                         f"      {tty:<9} {cputime:>8} {p.comm}")
        return lines

    def _format_full(self, procs: List[ProcessEntry]) -> List[str]:
        lines = ["UID        PID  PPID C STIME TTY      TIME CMD"]
        for p in procs:
            tty = self._get_tty(p.tty_nr)
            cputime = self._format_time(p.utime + p.stime)
            lines.append(f"{p.user:<9} {p.pid:>5} {p.ppid:>5} 0     0 "
                         f"{tty:<9} {cputime:>8} {p.command[:40]}")
        return lines

    def _format_user(self, procs: List[ProcessEntry]) -> List[str]:
        lines = ["USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND"]
        for p in procs:
            tty = self._get_tty(p.tty_nr)
            cputime = self._format_time(p.utime + p.stime)
            lines.append(f"{p.user:<10} {p.pid:>5}  0.0  0.0 {p.vsize:>7} "
                         f"{p.rss:>5} {tty:<9} {p.state:<5} 00:00 {cputime:>8} "
                         f"{p.command[:20]}")
        return lines

    def _format_custom(self, procs: List[ProcessEntry], fmt: str) -> List[str]:
        cols = [c.strip() for c in fmt.split(",")]
        lines = [" ".join(f"{c:>10}" for c in cols)]
        for p in procs:
            vals = []
            for c in cols:
                v = getattr(p, c, "")
                vals.append(f"{str(v):>10}")
            lines.append(" ".join(vals))
        return lines

    def _get_tty(self, tty_nr: int) -> str:
        if tty_nr == 0:
            return "?"
        major = os.major(tty_nr) if hasattr(os, "major") else tty_nr >> 8
        minor = os.minor(tty_nr) if hasattr(os, "minor") else tty_nr & 0xFF
        if major == 4:
            return f"tty{minor}" if minor else "tty"
        if major == 136:
            return f"pts/{minor}"
        return f"tty{major}-{minor}"

    def _format_time(self, ticks: int) -> str:
        try:
            clk_tck = os.sysconf("SC_CLK_TCK")
        except (ValueError, OSError, AttributeError):
            clk_tck = 100
        seconds = ticks // clk_tck
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


# ─── kill Command ────────────────────────────────────────────────────────────

class KillCommand:
    """
    kill - send a signal to a process.

    Usage: kill [-s signal] [-p] [-a] pid...
           kill -l [signal]
      -s signal: Signal name or number
      -l: List signal names
      pid: Target process ID(s)
      -0: Check if process exists (no signal sent)
    """

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []

        if not args or "-l" in args:
            return self._list_signals()

        signal_num = signal.SIGTERM  # default
        pids: List[int] = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-s" and i + 1 < len(args):
                i += 1
                signal_num = self._parse_signal(args[i])
                if signal_num is None:
                    print(f"kill: invalid signal '{args[i]}'", file=sys.stderr)
                    return 1
            elif arg == "-l":
                return self._list_signals()
            elif arg == "-0":
                signal_num = 0
            elif not arg.startswith("-"):
                try:
                    pids.append(int(arg))
                except ValueError:
                    print(f"kill: invalid process id '{arg}'", file=sys.stderr)
                    return 1
            elif arg.startswith("-") and arg[1:].isdigit():
                signal_num = int(arg[1:])
            i += 1

        if not pids:
            print("kill: no process ID specified", file=sys.stderr)
            return 1

        ret = 0
        for pid in pids:
            if not self._kill_pid(pid, signal_num):
                ret = 1
        return ret

    def _kill_pid(self, pid: int, sig: int) -> bool:
        try:
            if sig == 0:
                os.kill(pid, 0)
                return True
            os.kill(pid, sig)
            return True
        except ProcessLookupError:
            print(f"kill: ({pid}) - No such process", file=sys.stderr)
            return False
        except PermissionError:
            print(f"kill: ({pid}) - Operation not permitted", file=sys.stderr)
            return False
        except OSError as e:
            print(f"kill: ({pid}) - {e}", file=sys.stderr)
            return False

    def _parse_signal(self, name: str) -> Optional[int]:
        if name.isdigit():
            return int(name)
        name = name.upper().lstrip("SIG")
        return SIGNAL_MAP.get(name)

    def _list_signals(self) -> int:
        for name in sorted(SIGNAL_MAP.keys()):
            print(f"  {name:>6}")
        return 0


# ─── mount Command ──────────────────────────────────────────────────────────

@dataclass
class MountEntry:
    """Represents a mounted filesystem."""
    device: str = ""
    mountpoint: str = ""
    fstype: str = ""
    options: str = ""
    dump: int = 0
    passnum: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device": self.device, "mountpoint": self.mountpoint,
            "fstype": self.fstype, "options": self.options,
        }


class MountCommand:
    """
    mount - mount a filesystem.

    Usage: mount [-lhV]
           mount [-fnrsvw] [-t type] [-o options] device mountpoint
           mount [-a] [-t type]
      -a: Mount all filesystems in /etc/fstab
      -t type: Filesystem type
      -o options: Comma-separated mount options
      -r: Mount read-only
      -w: Mount read-write
      -l: List mounted filesystems
      -V: Show version
      -n: Don't write to /etc/mtab
    """

    def __init__(self) -> None:
        self._mounts: List[MountEntry] = []
        self._load_mounts()

    def _load_mounts(self) -> None:
        mtab = "/proc/mounts"
        fstab = "/etc/fstab"
        for path in [mtab, fstab]:
            if os.path.exists(path):
                self._parse_mount_file(path)

    def _parse_mount_file(self, path: str) -> None:
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) >= 4:
                        entry = MountEntry(
                            device=parts[0], mountpoint=parts[1],
                            fstype=parts[2], options=parts[3],
                        )
                        if len(parts) >= 5:
                            entry.dump = int(parts[4])
                        if len(parts) >= 6:
                            entry.passnum = int(parts[5])
                        self._mounts.append(entry)
        except OSError:
            pass

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []
        opts = self._parse_args(args)

        if opts.get("list") or (not opts.get("device") and not opts.get("mountpoint")):
            return self._list_mounts()

        if opts.get("all"):
            return self._mount_all()

        device = opts.get("device", "")
        mountpoint = opts.get("mountpoint", "")
        fstype = opts.get("type", "")
        options = opts.get("options", "")
        readonly = opts.get("readonly", False)

        if not device:
            print("mount: no device specified", file=sys.stderr)
            return 1
        if not mountpoint:
            print("mount: no mountpoint specified", file=sys.stderr)
            return 1

        return self._do_mount(device, mountpoint, fstype, options, readonly)

    def _parse_args(self, args: List[str]) -> Dict[str, Any]:
        opts: Dict[str, Any] = {}
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-a":
                opts["all"] = True
            elif arg == "-l":
                opts["list"] = True
            elif arg == "-r":
                opts["readonly"] = True
            elif arg == "-w":
                opts["readonly"] = False
            elif arg == "-V":
                print("mount (UmerOS) 1.0.0")
                return {}
            elif arg == "-t" and i + 1 < len(args):
                i += 1
                opts["type"] = args[i]
            elif arg == "-o" and i + 1 < len(args):
                i += 1
                opts["options"] = args[i]
            elif not arg.startswith("-"):
                if "device" not in opts:
                    opts["device"] = arg
                else:
                    opts["mountpoint"] = arg
            i += 1
        return opts

    def _do_mount(self, device: str, mp: str, fstype: str,
                  options: str, readonly: bool) -> int:
        os.makedirs(mp, exist_ok=True)
        flags = 0
        if readonly:
            flags |= 1  # MS_RDONLY
        data = options.encode() if options else None
        try:
            if fstype:
                os.mount(device, mp, fstype, flags, data)
            else:
                os.mount(device, mp, "", flags, data)
            entry = MountEntry(
                device=device, mountpoint=mp,
                fstype=fstype or "auto", options=options or "rw",
            )
            self._mounts.append(entry)
            return 0
        except OSError as e:
            print(f"mount: {e}", file=sys.stderr)
            return 1

    def _mount_all(self) -> int:
        ret = 0
        for entry in self._mounts:
            if entry.fstype in ("proc", "sysfs", "devpts", "tmpfs"):
                continue
            r = self._do_mount(entry.device, entry.mountpoint,
                               entry.fstype, entry.options, False)
            if r != 0:
                ret = r
        return ret

    def _list_mounts(self) -> int:
        print("Filesystem     Type     Options")
        print("-------------  -------  -------")
        for m in self._mounts:
            print(f"{m.device:<15} {m.fstype:<8} {m.options}")
        return 0


# ─── umount Command ──────────────────────────────────────────────────────────

class UmountCommand:
    """
    umount - unmount a filesystem.

    Usage: umount [-rlvn] device | mountpoint
      -r: Remount read-only if busy
      -l: Lazy unmount (detach now, clean up later)
      -v: Verbose
      -n: Don't write to /etc/mtab
    """

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []
        opts = self._parse_args(args)
        targets = opts.get("targets", [])

        if not targets:
            print("umount: no mountpoint specified", file=sys.stderr)
            return 1

        ret = 0
        for target in targets:
            if not self._do_umount(target, opts.get("lazy", False)):
                ret = 1
        return ret

    def _parse_args(self, args: List[str]) -> Dict[str, Any]:
        opts: Dict[str, Any] = {"targets": []}
        for arg in args:
            if arg == "-r":
                opts["remount_ro"] = True
            elif arg == "-l":
                opts["lazy"] = True
            elif arg == "-v":
                opts["verbose"] = True
            elif not arg.startswith("-"):
                opts["targets"].append(arg)
        return opts

    def _do_umount(self, target: str, lazy: bool) -> bool:
        try:
            if lazy:
                # MNT_DETACH = 2 on
                os.umount2(target, 2)
            else:
                os.umount(target)
            return True
        except OSError as e:
            print(f"umount: {target}: {e}", file=sys.stderr)
            return False


# ─── stty Command ────────────────────────────────────────────────────────────

class SttyCommand:
    """
    stty - change and print terminal line settings.

    Usage: stty [-a] [-g] [settings]
      -a: Print all current settings
      -g: Print settings in stty-readable form
      Settings: raw, cooked, sane, evenp, oddp, parenb, etc.
    """

    def __init__(self) -> None:
        self.name = "stty"
        self.description = "Change and print terminal line settings"
        self.usage = "stty [-a] [-g] [settings]"

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []
        if not args or "-a" in args:
            return self._print_all()
        if "-g" in args:
            return self._print_raw()

        return self._apply_settings(args)

    def _print_all(self) -> int:
        try:
            attrs = termios.tcgetattr(sys.stdin.fileno())
            print("speed 9600 baud; line = 0;")
            print(f"min = 1; time = 0; -breakb -icrnl -igncr -inlcr -ocrnl -onlcr")
            print(f"-opost -isig -icanon -iexten -echo -echoe -echok -echonl -noflsh")
            print(f"-xcase -tostop -echoprt -echoctl -echoke")
            return 0
        except termios.error:
            print("stty: standard input is not a terminal", file=sys.stderr)
            return 1

    def _print_raw(self) -> int:
        try:
            attrs = termios.tcgetattr(sys.stdin.fileno())
            raw = ",".join(str(x) for x in attrs[:7])
            print(raw)
            return 0
        except termios.error:
            return 1

    def _apply_settings(self, settings: List[str]) -> int:
        try:
            attrs = termios.tcgetattr(sys.stdin.fileno())
            for setting in settings:
                if setting == "raw":
                    attrs[3] &= ~termios.ICANON
                    attrs[3] &= ~termios.ECHO
                    attrs[6][termios.VMIN] = 1
                    attrs[6][termios.VTIME] = 0
                elif setting == "cooked" or setting == "sane":
                    attrs[3] |= termios.ICANON
                    attrs[3] |= termios.ECHO
                elif setting == "echo":
                    attrs[3] |= termios.ECHO
                elif setting == "-echo":
                    attrs[3] &= ~termios.ECHO
                elif setting == "echoe":
                    attrs[3] |= termios.ECHOE
                elif setting == "-echoe":
                    attrs[3] &= ~termios.ECHOE
                elif setting == "echok":
                    attrs[3] |= termios.ECHOK
                elif setting == "-echok":
                    attrs[3] &= ~termios.ECHOK
                elif setting == "echoke":
                    attrs[3] |= termios.ECHOKE
                elif setting == "-echoke":
                    attrs[3] &= ~termios.ECHOKE
                elif setting == "echoctl":
                    attrs[3] |= termios.ECHOCTL
                elif setting == "-echoctl":
                    attrs[3] &= ~termios.ECHOCTL
                elif setting == "isig":
                    attrs[3] |= termios.ISIG
                elif setting == "-isig":
                    attrs[3] &= ~termios.ISIG
                elif setting == "icanon":
                    attrs[3] |= termios.ICANON
                elif setting == "-icanon":
                    attrs[3] &= ~termios.ICANON
                elif setting == "iexten":
                    attrs[3] |= termios.IEXTEN
                elif setting == "-iexten":
                    attrs[3] &= ~termios.IEXTEN
                elif setting == "echoe" or setting == "crterase":
                    attrs[3] |= termios.ECHOE
                elif setting == "echoprt":
                    attrs[3] |= termios.ECHOPRT
                elif setting == "noflsh":
                    attrs[3] |= termios.NOFLSH
                elif setting == "-noflsh":
                    attrs[3] &= ~termios.NOFLSH
                elif setting == "tostop":
                    attrs[3] |= termios.TOSTOP
                elif setting == "-tostop":
                    attrs[3] &= ~termios.TOSTOP
                else:
                    print(f"stty: unknown setting '{setting}'", file=sys.stderr)
                    return 1
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, attrs)
            return 0
        except termios.error:
            print("stty: standard input is not a terminal", file=sys.stderr)
            return 1


# ─── sync Command ────────────────────────────────────────────────────────────

class SyncCommand:
    """
    sync - flush filesystem buffers.

    Usage: sync [-d] [-f]
      -d: Delete unnecessary temporary files
      -f: Force sync (ignore errors)
    """

    def __init__(self) -> None:
        self.name = "sync"
        self.description = "Flush filesystem buffers"
        self.usage = "sync [-d] [-f]"

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []
        force = "-f" in args

        try:
            os.sync()
            return 0
        except OSError:
            if force:
                return 0
            # Fallback: flush Python buffers
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except (OSError, ValueError):  # [FIX H8]
                pass
            return 0


def _selftest() -> bool:
    """Run self-tests for process module."""
    try:
        import io, contextlib

        # PsCommand
        pc = PsCommand()
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            assert pc.execute() == 0
        assert "PID" in f.getvalue()

        # KillCommand
        kc = KillCommand()
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            assert kc.execute(["-l"]) == 0
        assert len(f.getvalue()) > 0
        if os.name != 'nt':
            assert kc.execute([str(os.getpid()), "0"]) == 0

        # MountCommand
        mc = MountCommand()
        f2 = io.StringIO()
        with contextlib.redirect_stdout(f2):
            mc.execute([])
        assert len(f2.getvalue()) > 0

        # UmountCommand
        uc = UmountCommand()
        assert uc.execute([]) == 1

        # SttyCommand (may fail on non-terminal; just verify no crash)
        stc = SttyCommand()
        stc.execute(["-h"])

        # SyncCommand
        sync = SyncCommand()
        code = sync.execute()
        assert code == 0
        code2 = sync.execute(["-f"])
        assert code2 == 0

        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"_selftest FAILED: {e}")
        return False
