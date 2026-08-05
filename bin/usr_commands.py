"""
UmerOS /bin /usr/bin Utilities
===============================
Implements common /usr/bin commands as stubs for FHS compliance.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, List, Optional, Tuple


class CpioCommand:
    """Copy file archives (cpio)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("cpio: missing operand", file=sys.stderr)
            print("Usage: cpio -o < files > archive.cpio", file=sys.stderr)
            return 1

        flags = args[0]
        if flags.startswith('-'):
            if 'o' in flags:
                print("cpio: create mode (stub)", file=sys.stderr)
                return 0
            elif 'i' in flags:
                print("cpio: extract mode (stub)", file=sys.stderr)
                return 0
            elif 't' in flags:
                print("cpio: list mode (stub)", file=sys.stderr)
                return 0
            elif 'p' in flags:
                print("cpio: pass-through mode (stub)", file=sys.stderr)
                return 0

        print("cpio: unknown option", file=sys.stderr)
        return 1

    def help(self) -> str:
        return "cpio - copy file archives"


class FoldCommand:
    """Fold long lines (fold)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        width = 80
        files = []
        i = 0
        while i < len(args):
            if args[i] == '-w' and i + 1 < len(args):
                width = int(args[i + 1])
                i += 2
            elif args[i] == '-s':
                i += 1
            elif args[i] == '-b':
                i += 1
            else:
                files.append(args[i])
                i += 1

        input_stream = stdin or sys.stdin

        try:
            for line in input_stream:
                line = line.rstrip('\n')
                if len(line) <= width:
                    print(line)
                else:
                    for i in range(0, len(line), width):
                        print(line[i:i + width])
        except Exception as e:
            print(f"fold: {e}", file=sys.stderr)
            return 1

        return 0

    def help(self) -> str:
        return "fold - wrap each input line to fit in specified width"


class NohupCommand:
    """Run command immune to hangups (nohup)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("nohup: missing command", file=sys.stderr)
            return 1

        cmd = args[0]
        cmd_args = args[1:]

        print(f"nohup: running '{cmd}' (stub - would run detached)", file=sys.stderr)

        try:
            module = __import__("bin.shell", fromlist=["ShCommand"])
            sh_cmd = module.ShCommand()
            return sh_cmd.execute([cmd] + cmd_args, stdin, stdout)
        except Exception:
            print(f"nohup: command '{cmd}' not found", file=sys.stderr)
            return 127

    def help(self) -> str:
        return "nohup - run a command immune to hangups"


class NsenterCommand:
    """Run program in new namespaces (nsenter)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("nsenter: missing target", file=sys.stderr)
            return 1

        print("nsenter: namespace enter (stub - not implemented in UmerOS)", file=sys.stderr)
        return 0

    def help(self) -> str:
        return "nsenter - run program in new namespaces"


class StraceCommand:
    """Trace system calls and signals (strace)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("strace: missing command", file=sys.stderr)
            return 1

        cmd = args[0]
        cmd_args = args[1:]

        print(f"strace: tracing '{cmd}' (stub - would trace syscalls)", file=sys.stderr)

        try:
            module = __import__("bin.shell", fromlist=["ShCommand"])
            sh_cmd = module.ShCommand()
            return sh_cmd.execute([cmd] + cmd_args, stdin, stdout)
        except Exception:
            print(f"strace: command '{cmd}' not found", file=sys.stderr)
            return 127

    def help(self) -> str:
        return "strace - trace system calls and signals"


class TasksetCommand:
    """Set or retrieve a process's CPU affinity (taskset)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if len(args) == 0:
            print("taskset: missing argument", file=sys.stderr)
            return 1

        if args[0] == '-p':
            if len(args) < 2:
                print("taskset: -p requires a PID", file=sys.stderr)
                return 1
            pid = args[1]
            print(f"taskset: affinity for PID {pid}: 0x1 (stub)")
            return 0

        if len(args) < 2:
            print("taskset: missing command", file=sys.stderr)
            return 1

        mask = args[0]
        cmd = args[1]
        cmd_args = args[2:]

        print(f"taskset: running '{cmd}' with mask {mask} (stub)", file=sys.stderr)

        try:
            module = __import__("bin.shell", fromlist=["ShCommand"])
            sh_cmd = module.ShCommand()
            return sh_cmd.execute([cmd] + cmd_args, stdin, stdout)
        except Exception:
            print(f"taskset: command '{cmd}' not found", file=sys.stderr)
            return 127

    def help(self) -> str:
        return "taskset - set or retrieve a process's CPU affinity"


class TimeCommand:
    """Run command and print time statistics (time)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("time: missing command", file=sys.stderr)
            return 1

        cmd = args[0]
        cmd_args = args[1:]

        start_time = time.time()

        try:
            module = __import__("bin.shell", fromlist=["ShCommand"])
            sh_cmd = module.ShCommand()
            exit_code = sh_cmd.execute([cmd] + cmd_args, stdin, stdout)
        except Exception:
            print(f"time: command '{cmd}' not found", file=sys.stderr)
            return 127

        elapsed = time.time() - start_time
        print(f"\nreal\t{elapsed:.3f}s")
        print(f"user\t{elapsed * 0.8:.3f}s")
        print(f"sys\t{elapsed * 0.2:.3f}s")

        return exit_code

    def help(self) -> str:
        return "time - run command and print time statistics"


class NiceCommand:
    """Run command with modified scheduling priority (nice)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        adjustment = 10
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                adjustment = int(args[i + 1])
                i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                adjustment = int(args[i][1:])
                i += 1
            else:
                break

        if i >= len(args):
            print(f"nice: {adjustment}")
            return 0

        cmd = args[i]
        cmd_args = args[i + 1:]

        print(f"nice: running '{cmd}' with adjustment {adjustment} (stub)", file=sys.stderr)

        try:
            module = __import__("bin.shell", fromlist=["ShCommand"])
            sh_cmd = module.ShCommand()
            return sh_cmd.execute([cmd] + cmd_args, stdin, stdout)
        except Exception:
            print(f"nice: command '{cmd}' not found", file=sys.stderr)
            return 127

    def help(self) -> str:
        return "nice - run a command with modified scheduling priority"


class IoniceCommand:
    """Get or set I/O scheduling class and priority (ionice)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args:
            print("none: default class")
            return 0

        if args[0] == '-p' and len(args) > 1:
            print(f"PID {args[1]}: none/0 (stub)")
            return 0

        if args[0] in ('-c', '--class'):
            if len(args) > 1:
                print(f"ionice: class set to {args[1]} (stub)")
                return 0

        print("ionice: get/set I/O scheduling (stub)")
        return 0

    def help(self) -> str:
        return "ionice - get or set I/O scheduling class and priority"


class SeqCommand:
    """Print a sequence of numbers (seq)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if len(args) == 0:
            print("seq: missing operand", file=sys.stderr)
            return 1

        try:
            if len(args) == 1:
                end = int(args[0])
                for i in range(1, end + 1):
                    print(i)
            elif len(args) == 2:
                start = int(args[0])
                end = int(args[1])
                for i in range(start, end + 1):
                    print(i)
            elif len(args) == 3:
                start = int(args[0])
                step = int(args[1])
                end = int(args[2])
                if step == 0:
                    print("seq: step cannot be zero", file=sys.stderr)
                    return 1
                if step > 0:
                    i = start
                    while i <= end:
                        print(i)
                        i += step
                else:
                    i = start
                    while i >= end:
                        print(i)
                        i += step
            else:
                print("seq: too many arguments", file=sys.stderr)
                return 1
        except ValueError as e:
            print(f"seq: {e}", file=sys.stderr)
            return 1

        return 0

    def help(self) -> str:
        return "seq - print a sequence of numbers"


class TeeCommand:
    """Read from standard input and write to standard output and files (tee)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        append = False
        files = []
        i = 0
        while i < len(args):
            if args[i] == '-a':
                append = True
                i += 1
            elif args[i] == '--append':
                append = True
                i += 1
            else:
                files.append(args[i])
                i += 1

        input_stream = stdin or sys.stdin
        file_handles = []

        for f in files:
            try:
                mode = 'a' if append else 'w'
                file_handles.append(open(f, mode))
            except Exception as e:
                print(f"tee: {e}", file=sys.stderr)
                return 1

        try:
            for line in input_stream:
                line = line.rstrip('\n') + '\n'
                sys.stdout.write(line)
                sys.stdout.flush()
                for fh in file_handles:
                    fh.write(line)
                    fh.flush()
        except Exception as e:
            print(f"tee: {e}", file=sys.stderr)
            return 1
        finally:
            for fh in file_handles:
                fh.close()

        return 0

    def help(self) -> str:
        return "tee - read from standard input and write to standard output and files"


class WcCommand:
    """Print line, word, and byte counts (wc)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        show_lines = show_words = show_bytes = False
        files = []
        i = 0
        while i < len(args):
            if args[i] == '-l':
                show_lines = True
                i += 1
            elif args[i] == '-w':
                show_words = True
                i += 1
            elif args[i] == '-c':
                show_bytes = True
                i += 1
            elif args[i] == '-m':
                show_bytes = True
                i += 1
            else:
                files.append(args[i])
                i += 1

        if not show_lines and not show_words and not show_bytes:
            show_lines = show_words = show_bytes = True

        input_stream = stdin or sys.stdin
        total_lines = total_words = total_bytes = 0

        try:
            for line in input_stream:
                total_lines += 1
                total_words += len(line.split())
                total_bytes += len(line.encode('utf-8'))
        except Exception as e:
            print(f"wc: {e}", file=sys.stderr)
            return 1

        if show_lines:
            print(f"{total_lines:8d}", end="")
        if show_words:
            print(f"{total_words:8d}", end="")
        if show_bytes:
            print(f"{total_bytes:8d}", end="")
        print()

        return 0

    def help(self) -> str:
        return "wc - print line, word, and byte counts for each file"


class HeadCommand:
    """Output the first lines of files (head)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        n = 10
        files = []
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                n = int(args[i + 1])
                i += 2
            elif args[i] == '-c' and i + 1 < len(args):
                n = int(args[i + 1])
                i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                n = int(args[i][1:])
                i += 1
            else:
                files.append(args[i])
                i += 1

        input_stream = stdin or sys.stdin
        count = 0
        try:
            for line in input_stream:
                if count >= n:
                    break
                print(line.rstrip('\n'))
                count += 1
        except Exception as e:
            print(f"head: {e}", file=sys.stderr)
            return 1

        return 0

    def help(self) -> str:
        return "head - output the first 10 lines of each file"


class TailCommand:
    """Output the last lines of files (tail)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        n = 10
        files = []
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                n = int(args[i + 1])
                i += 2
            elif args[i] == '-c' and i + 1 < len(args):
                n = int(args[i + 1])
                i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                n = int(args[i][1:])
                i += 1
            elif args[i] == '-f':
                i += 1
            else:
                files.append(args[i])
                i += 1

        lines = []
        input_stream = stdin or sys.stdin

        try:
            for line in input_stream:
                lines.append(line.rstrip('\n'))
                if len(lines) > n * 2:
                    lines = lines[-n:]

            for line in lines[-n:]:
                print(line)
        except Exception as e:
            print(f"tail: {e}", file=sys.stderr)
            return 1

        return 0

    def help(self) -> str:
        return "tail - output the last 10 lines of each file"


class CutCommand:
    """Remove sections from each line of files (cut)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        delimiter = '\t'
        fields = []
        characters = []
        i = 0
        while i < len(args):
            if args[i] == '-d' and i + 1 < len(args):
                delimiter = args[i + 1]
                i += 2
            elif args[i] == '-f' and i + 1 < len(args):
                fields = self._parse_fields(args[i + 1])
                i += 2
            elif args[i] == '-c' and i + 1 < len(args):
                characters = self._parse_fields(args[i + 1])
                i += 2
            elif args[i] == '--delimiter' and i + 1 < len(args):
                delimiter = args[i + 1]
                i += 2
            elif args[i] == '--fields' and i + 1 < len(args):
                fields = self._parse_fields(args[i + 1])
                i += 2
            else:
                i += 1

        input_stream = stdin or sys.stdin
        try:
            for line in input_stream:
                line = line.rstrip('\n')
                if fields:
                    parts = line.split(delimiter)
                    selected = []
                    for f in fields:
                        if 1 <= f <= len(parts):
                            selected.append(parts[f - 1])
                    print(delimiter.join(selected))
                elif characters:
                    selected = []
                    for c in characters:
                        if 1 <= c <= len(line):
                            selected.append(line[c - 1])
                    print(''.join(selected))
                else:
                    print(line)
        except Exception as e:
            print(f"cut: {e}", file=sys.stderr)
            return 1

        return 0

    def _parse_fields(self, spec: str) -> List[int]:
        fields = []
        for part in spec.split(','):
            if '-' in part:
                start, end = part.split('-', 1)
                for i in range(int(start), int(end) + 1):
                    fields.append(i)
            else:
                fields.append(int(part))
        return sorted(set(fields))

    def help(self) -> str:
        return "cut - remove sections from each line of files"


class SortCommand:
    """Sort lines of text files (sort)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        reverse = False
        numeric = False
        unique = False
        i = 0
        while i < len(args):
            if args[i] in ('-r', '--reverse'):
                reverse = True
                i += 1
            elif args[i] in ('-n', '--numeric-sort'):
                numeric = True
                i += 1
            elif args[i] in ('-u', '--unique'):
                unique = True
                i += 1
            else:
                i += 1

        lines = []
        input_stream = stdin or sys.stdin
        try:
            for line in input_stream:
                lines.append(line.rstrip('\n'))
        except Exception as e:
            print(f"sort: {e}", file=sys.stderr)
            return 1

        if numeric:
            try:
                lines.sort(key=lambda x: float(x), reverse=reverse)
            except ValueError:
                lines.sort(reverse=reverse)
        else:
            lines.sort(reverse=reverse)

        if unique:
            seen = set()
            unique_lines = []
            for line in lines:
                if line not in seen:
                    seen.add(line)
                    unique_lines.append(line)
            lines = unique_lines

        for line in lines:
            print(line)

        return 0

    def help(self) -> str:
        return "sort - sort lines of text files"


class UniqCommand:
    """Filter adjacent matching lines from input (uniq)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        count = False
        i = 0
        while i < len(args):
            if args[i] in ('-c', '--count'):
                count = True
                i += 1
            else:
                i += 1

        lines = []
        input_stream = stdin or sys.stdin
        try:
            for line in input_stream:
                lines.append(line.rstrip('\n'))
        except Exception as e:
            print(f"uniq: {e}", file=sys.stderr)
            return 1

        if not lines:
            return 0

        prev = lines[0]
        count_val = 1
        for line in lines[1:]:
            if line == prev:
                count_val += 1
            else:
                if count:
                    print(f"{count_val:7d} {prev}")
                else:
                    print(prev)
                prev = line
                count_val = 1
        if count:
            print(f"{count_val:7d} {prev}")
        else:
            print(prev)

        return 0

    def help(self) -> str:
        return "uniq - filter adjacent matching lines from input"


class TrCommand:
    """Translate or delete characters (tr)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        delete = False
        i = 0
        while i < len(args):
            if args[i] in ('-d', '--delete'):
                delete = True
                i += 1
            elif args[i] in ('-s', '--squeeze-repeats'):
                i += 1
            else:
                break

        if delete:
            if i >= len(args):
                print("tr: missing operand", file=sys.stderr)
                return 1
            chars_to_delete = args[i]
            input_stream = stdin or sys.stdin
            try:
                for line in input_stream:
                    for char in line:
                        if char not in chars_to_delete:
                            sys.stdout.write(char)
            except Exception as e:
                print(f"tr: {e}", file=sys.stderr)
                return 1
        else:
            if i + 1 >= len(args):
                print("tr: missing operand", file=sys.stderr)
                return 1
            from_chars = args[i]
            to_chars = args[i + 1]

            trans_table = {}
            for j, char in enumerate(from_chars):
                if j < len(to_chars):
                    trans_table[char] = to_chars[j]
                else:
                    trans_table[char] = ''

            input_stream = stdin or sys.stdin
            try:
                for line in input_stream:
                    translated = ''.join(trans_table.get(char, char) for char in line)
                    sys.stdout.write(translated)
            except Exception as e:
                print(f"tr: {e}", file=sys.stderr)
                return 1

        return 0

    def help(self) -> str:
        return "tr - translate or delete characters"


class XargsCommand:
    """Build and execute command lines from standard input (xargs)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args:
            print("xargs: missing command", file=sys.stderr)
            return 1

        cmd = args[0]
        cmd_args = args[1:]

        input_stream = stdin or sys.stdin
        try:
            for line in input_stream:
                line = line.rstrip('\n')
                if line:
                    full_args = cmd_args + [line]
                    try:
                        module = __import__("bin.shell", fromlist=["ShCommand"])
                        sh_cmd = module.ShCommand()
                        exit_code = sh_cmd.execute([cmd] + full_args, None, None)
                        if exit_code != 0:
                            return exit_code
                    except Exception:
                        print(f"xargs: {cmd}: not found", file=sys.stderr)
                        return 127
        except Exception as e:
            print(f"xargs: {e}", file=sys.stderr)
            return 1

        return 0

    def help(self) -> str:
        return "xargs - build and execute command lines from standard input"


class WhichCommand:
    """Locate a command (which)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args:
            return 0

        found_all = True
        for cmd in args:
            module = __import__("bin.bin_manager", fromlist=["COMMAND_REGISTRY"])
            registry = module.COMMAND_REGISTRY
            if cmd in registry:
                module_name, class_name = registry[cmd]
                print(f"bin/{module_name}.py")
            else:
                print(f"which: no {cmd} in PATH", file=sys.stderr)
                found_all = False

        return 0 if found_all else 1

    def help(self) -> str:
        return "which - locate a command"


class IdCommand:
    """Print real and effective user and group IDs (id)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        try:
            import os
            uid = os.getuid() if hasattr(os, 'getuid') else 0
            gid = os.getgid() if hasattr(os, 'getgid') else 0
            euid = os.geteuid() if hasattr(os, 'geteuid') else 0
            egid = os.getegid() if hasattr(os, 'getegid') else 0

            print(f"uid={uid}(root) gid={gid}(root) euid={euid}(root) egid={egid}(root)")
        except Exception:
            print("uid=0(root) gid=0(root)")

        return 0

    def help(self) -> str:
        return "id - print real and effective user and group IDs"


class WhoamiCommand:
    """Print effective user name (whoami)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        try:
            import os
            name = os.getenv('USER', 'root')
            print(name)
        except Exception:
            print("root")
        return 0

    def help(self) -> str:
        return "whoami - print effective user name"


class GroupsCommand:
    """Print group memberships for a user (groups)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        username = args[0] if args else "root"
        print(f"{username} : {username}")
        return 0

    def help(self) -> str:
        return "groups - print group memberships for a user"


class BasenameCommand:
    """Strip directory and suffix from filenames (basename)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if len(args) < 1:
            print("basename: missing operand", file=sys.stderr)
            return 1

        name = args[0]
        suffix = args[1] if len(args) > 1 else None

        name = name.rstrip('/')
        name = os.path.basename(name)

        if suffix and name.endswith(suffix):
            name = name[:-len(suffix)]

        print(name)
        return 0

    def help(self) -> str:
        return "basename - strip directory and suffix from filenames"


class DirnameCommand:
    """Print last component's directory part (dirname)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if len(args) < 1:
            print("dirname: missing operand", file=sys.stderr)
            return 1

        name = args[0]
        dirname = os.path.dirname(name)
        if not dirname:
            dirname = '.'
        print(dirname)
        return 0

    def help(self) -> str:
        return "dirname - print last component's directory part"


class ReadlinkCommand:
    """Print value of a symbolic link (readlink)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if len(args) < 1:
            print("readlink: missing operand", file=sys.stderr)
            return 1

        target = args[0]
        canonicalize = '-f' in args or '--canonicalize' in args

        try:
            if canonicalize:
                result = os.path.realpath(target)
            else:
                result = os.readlink(target) if os.path.islink(target) else target
            print(result)
        except OSError as e:
            print(f"readlink: {e}", file=sys.stderr)
            return 1

        return 0

    def help(self) -> str:
        return "readlink - print value of a symbolic link or canonical file name"


class RealpathCommand:
    """Print the resolved file name (realpath)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if len(args) < 1:
            print("realpath: missing operand", file=sys.stderr)
            return 1

        for path in args:
            try:
                result = os.path.realpath(path)
                print(result)
            except OSError as e:
                print(f"realpath: {e}", file=sys.stderr)
                return 1

        return 0

    def help(self) -> str:
        return "realpath - print the resolved file name"


class TouchCommand:
    """Change file timestamps (touch)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        create_only = False
        files = []
        i = 0
        while i < len(args):
            if args[i] in ('-c', '--no-create'):
                create_only = True
                i += 1
            elif args[i] in ('-a',):
                i += 1
            elif args[i] in ('-m',):
                i += 1
            elif args[i] in ('-t',):
                i += 2
            else:
                files.append(args[i])
                i += 1

        if not files:
            print("touch: missing file operand", file=sys.stderr)
            return 1

        for filepath in files:
            try:
                if os.path.exists(filepath):
                    os.utime(filepath, None)
                elif not create_only:
                    with open(filepath, 'a'):
                        os.utime(filepath, None)
            except Exception as e:
                print(f"touch: {filepath}: {e}", file=sys.stderr)
                return 1

        return 0

    def help(self) -> str:
        return "touch - change file timestamps"


class ChrootCommand:
    """Run command with a different root directory (chroot)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if len(args) < 1:
            print("chroot: missing operand", file=sys.stderr)
            return 1

        new_root = args[0]
        cmd = args[1] if len(args) > 1 else '/bin/sh'
        cmd_args = args[2:] if len(args) > 2 else []

        print(f"chroot: new root: {new_root} (stub)", file=sys.stderr)

        if not os.path.isdir(new_root):
            print(f"chroot: cannot change root to '{new_root}': No such file or directory", file=sys.stderr)
            return 1

        print(f"chroot: running '{cmd}' (stub - would chroot)", file=sys.stderr)
        return 0

    def help(self) -> str:
        return "chroot - run command with a different root directory"


class ReniceCommand:
    """Alter scheduling priority of running processes (renice)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if len(args) < 1:
            print("renice: missing operand", file=sys.stderr)
            return 1

        priority = 0
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                priority = int(args[i + 1])
                i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                priority = int(args[i][1:])
                i += 1
            elif args[i].lstrip('-').isdigit():
                pids = []
                while i < len(args) and args[i].lstrip('-').isdigit():
                    pids.append(args[i])
                    i += 1
                for pid in pids:
                    print(f"renice: {pid}: old priority {priority}, new priority {priority} (stub)")
                return 0
            else:
                i += 1

        print(f"renice: priority set to {priority} (stub)")
        return 0

    def help(self) -> str:
        return "renice - alter scheduling priority of running processes"


class TimeoutCommand:
    """Run a command with a time limit (timeout)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args:
            print("timeout: missing operand", file=sys.stderr)
            return 1

        duration = 10
        i = 0
        if args[0].endswith('s'):
            duration = int(args[0][:-1])
            i = 1
        elif args[0].endswith('m'):
            duration = int(args[0][:-1]) * 60
            i = 1
        elif args[0].endswith('h'):
            duration = int(args[0][:-1]) * 3600
            i = 1
        elif args[0].lstrip('-').isdigit():
            duration = int(args[0])
            i = 1

        if i >= len(args):
            print("timeout: missing command", file=sys.stderr)
            return 1

        cmd = args[i]
        cmd_args = args[i + 1:]

        print(f"timeout: {duration}s limit (stub - would enforce timeout)", file=sys.stderr)

        try:
            module = __import__("bin.shell", fromlist=["ShCommand"])
            sh_cmd = module.ShCommand()
            return sh_cmd.execute([cmd] + cmd_args, stdin, stdout)
        except Exception:
            print(f"timeout: command '{cmd}' not found", file=sys.stderr)
            return 127

    def help(self) -> str:
        return "timeout - run a command with a time limit"


# ─── Text Processing ─────────────────────────────────────────────────────────

class GrepCommand:
    """Print lines that match patterns (grep)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("grep: missing pattern", file=sys.stderr)
            print("Usage: grep [OPTIONS] PATTERN [FILE...]", file=sys.stderr)
            return 1

        ignore_case = "-i" in args
        line_numbers = "-n" in args
        count_only = "-c" in args
        recursive = "-r" in args
        invert = "-v" in args

        # Extract pattern (first non-flag argument)
        pattern = None
        files = []
        i = 0
        while i < len(args):
            if args[i].startswith("-"):
                i += 1
            elif pattern is None:
                pattern = args[i]
                i += 1
            else:
                files.append(args[i])
                i += 1

        if not pattern:
            print("grep: missing pattern", file=sys.stderr)
            return 1

        import re
        try:
            flags = re.IGNORECASE if ignore_case else 0
            regex = re.compile(pattern, flags)
        except re.error as e:
            print(f"grep: invalid pattern: {e}", file=sys.stderr)
            return 2

        match_count = 0
        try:
            if files:
                for fname in files:
                    try:
                        with open(fname, 'r') as f:
                            for lineno, line in enumerate(f, 1):
                                matched = bool(regex.search(line.rstrip("\n")))
                                if matched and not invert:
                                    match_count += 1
                                    if count_only:
                                        continue
                                    prefix = f"{lineno}:" if line_numbers else ""
                                    if len(files) > 1:
                                        print(f"{fname}:{prefix}{line.rstrip()}")
                                    else:
                                        print(f"{prefix}{line.rstrip()}")
                                elif not matched and invert:
                                    match_count += 1
                                    if not count_only:
                                        prefix = f"{lineno}:" if line_numbers else ""
                                        if len(files) > 1:
                                            print(f"{fname}:{prefix}{line.rstrip()}")
                                        else:
                                            print(f"{prefix}{line.rstrip()}")
                    except FileNotFoundError:
                        print(f"grep: {fname}: No such file or directory", file=sys.stderr)
                        return 2
                if count_only:
                    print(str(match_count))
            else:
                input_stream = stdin or []
                for lineno, line in enumerate(input_stream, 1):
                    matched = bool(regex.search(line.rstrip("\n")))
                    if (matched and not invert) or (not matched and invert):
                        match_count += 1
                        if not count_only:
                            prefix = f"{lineno}:" if line_numbers else ""
                            print(f"{prefix}{line.rstrip()}")
                if count_only:
                    print(str(match_count))
        except Exception as e:
            print(f"grep: {e}", file=sys.stderr)
            return 1

        return 0 if match_count > 0 else 1

    def help(self) -> str:
        return "grep - print lines matching a pattern"


class LessCommand:
    """Display paginated text (less)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        lines = []
        try:
            if args:
                with open(args[0], 'r') as f:
                    lines = f.readlines()
            elif stdin:
                lines = stdin.readlines()
            else:
                return 0

            page_size = 24
            for i, line in enumerate(lines):
                print(line.rstrip())
                if (i + 1) % page_size == 0 and i + 1 < len(lines):
                    print("--More-- (press q to quit)", end="\r")
                    try:
                        inp = input()
                        if inp.lower() == "q":
                            break
                    except EOFError:
                        break
        except FileNotFoundError:
            print(f"less: {args[0]}: No such file or directory", file=sys.stderr)
            return 1

        return 0

    def help(self) -> str:
        return "less - view a file page by page"


class FindCommand:
    """Search for files in a directory hierarchy (find)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        start_dir = "."
        name_pattern = None
        type_filter = None
        exec_cmd = None

        i = 0
        while i < len(args):
            if args[i] == "-name" and i + 1 < len(args):
                name_pattern = args[i + 1]
                i += 2
            elif args[i] == "-type" and i + 1 < len(args):
                type_filter = args[i + 1]
                i += 2
            elif args[i] == "-exec" and i + 1 < len(args):
                exec_cmd = args[i + 1]
                i += 2
            elif args[i] == "-maxdepth" and i + 1 < len(args):
                i += 2  # skip depth value
            else:
                start_dir = args[i]
                i += 1

        import glob
        import fnmatch

        found = []
        try:
            for root, dirs, files in os.walk(start_dir):
                all_items = dirs + files
                for item in all_items:
                    full_path = os.path.join(root, item)
                    if name_pattern and not fnmatch.fnmatch(item, name_pattern):
                        continue
                    if type_filter == "f" and not os.path.isfile(full_path):
                        continue
                    if type_filter == "d" and not os.path.isdir(full_path):
                        continue
                    found.append(full_path)
        except PermissionError:
            pass

        for path in found:
            print(path)

        return 0 if found else 0

    def help(self) -> str:
        return "find - search for files in a directory hierarchy"


class AwkCommand:
    """Pattern scanning and processing language (awk)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("awk: missing program", file=sys.stderr)
            print("Usage: awk 'program' [file...]", file=sys.stderr)
            return 1

        program = args[0]
        files = args[1:] if len(args) > 1 else []

        # Simple awk: just print lines (stub implementation)
        try:
            input_lines = []
            if files:
                for f in files:
                    try:
                        with open(f, 'r') as fh:
                            input_lines.extend(fh.readlines())
                    except FileNotFoundError:
                        print(f"awk: {f}: No such file or directory", file=sys.stderr)
            elif stdin:
                input_lines = stdin.readlines()
            else:
                return 0

            for line in input_lines:
                # Simple stub: just print the line
                print(line.rstrip())
        except Exception as e:
            print(f"awk: {e}", file=sys.stderr)
            return 1

        return 0

    def help(self) -> str:
        return "awk - pattern scanning and processing language"


class DiffCommand:
    """Compare files line by line (diff)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        unified = "-u" in args
        context = "-c" in args

        files = [a for a in args if not a.startswith("-")]
        if len(files) < 2:
            print("diff: missing operand", file=sys.stderr)
            print("Usage: diff [-u] [-c] FILE1 FILE2", file=sys.stderr)
            return 1

        try:
            with open(files[0], 'r') as f1:
                lines1 = f1.readlines()
            with open(files[1], 'r') as f2:
                lines2 = f2.readlines()

            if lines1 == lines2:
                return 0

            # Simple diff output
            for i, (l1, l2) in enumerate(zip(lines1, lines2)):
                if l1 != l2:
                    print(f"{i + 1}c{i + 1}")
                    print(f"< {l1.rstrip()}")
                    print(f"---")
                    print(f"> {l2.rstrip()}")

            if len(lines1) != len(lines2):
                print(f"{len(lines1)}c{len(lines2)}")

        except FileNotFoundError as e:
            print(f"diff: {e}", file=sys.stderr)
            return 2

        return 1

    def help(self) -> str:
        return "diff - compare files line by line"


class DuCommand:
    """Estimate disk usage of files (du)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        human_readable = "-h" in args
        total = "-s" in args
        dirs = [a for a in args if not a.startswith("-")] or ["."]

        try:
            for d in dirs:
                total_size = 0
                if os.path.isdir(d):
                    for root, subdirs, files in os.walk(d):
                        for f in files:
                            fp = os.path.join(root, f)
                            if os.path.exists(fp):
                                total_size += os.path.getsize(fp)
                elif os.path.isfile(d):
                    total_size = os.path.getsize(d)

                if human_readable:
                    if total_size >= 1024 * 1024:
                        size_str = f"{total_size / (1024 * 1024):.1f}M"
                    elif total_size >= 1024:
                        size_str = f"{total_size / 1024:.1f}K"
                    else:
                        size_str = f"{total_size}"
                else:
                    size_str = str(total_size // 1024)

                print(f"{size_str}\t{d}")
        except Exception as e:
            print(f"du: {e}", file=sys.stderr)
            return 1

        return 0

    def help(self) -> str:
        return "du - estimate disk space usage"


class FileCommand:
    """Determine file type (file)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if not args:
            print("file: missing operand", file=sys.stderr)
            return 1

        for path in args:
            try:
                if not os.path.exists(path):
                    print(f"{path}: cannot open (No such file or directory)")
                    continue

                if os.path.isdir(path):
                    print(f"{path}: directory")
                    continue

                # Try to detect by reading first bytes
                with open(path, 'rb') as f:
                    header = f.read(16)

                if header.startswith(b'\x7fELF'):
                    print(f"{path}: ELF executable")
                elif header.startswith(b'#!'):
                    shebang = header.split(b'\n')[0].decode('utf-8', errors='replace')
                    print(f"{path}: script, {shebang}")
                elif header.startswith(b'PK'):
                    print(f"{path}: Zip archive data")
                elif header.startswith(b'%PDF'):
                    print(f"{path}: PDF document")
                elif header.startswith(b'\xff\xd8\xff'):
                    print(f"{path}: JPEG image data")
                elif header.startswith(b'\x89PNG'):
                    print(f"{path}: PNG image data")
                elif header.startswith(b'GIF8'):
                    print(f"{path}: GIF image data")
                else:
                    # Try text vs binary
                    try:
                        with open(path, 'r') as f:
                            f.read(512)
                        print(f"{path}: ASCII text")
                    except UnicodeDecodeError:
                        print(f"{path}: data")
            except Exception as e:
                print(f"{path}: error: {e}")

        return 0

    def help(self) -> str:
        return "file - determine file type"


class StatCommand:
    """Display file or filesystem status (stat)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        files = [a for a in args if not a.startswith("-")]
        if not files:
            print("stat: missing operand", file=sys.stderr)
            return 1

        for path in files:
            try:
                st = os.stat(path)
                print(f"  File: {path}")
                print(f"  Size: {st.st_size:<20} Blocks: {st.st_blocks:<10} IO Block: {st.st_blksize}")
                print(f"Access: (0{oct(st.st_mode)[-3:]})  Uid: ({st.st_uid}/{st.st_gid})  Gid: ({st.st_uid}/{st.st_gid})")
                print(f"Access: {time.ctime(st.st_atime)}")
                print(f"Modify: {time.ctime(st.st_mtime)}")
                print(f"Change: {time.ctime(st.st_ctime)}")
                print(f" Birth: -")
            except FileNotFoundError:
                print(f"stat: cannot stat '{path}': No such file or directory", file=sys.stderr)
                return 1

        return 0

    def help(self) -> str:
        return "stat - display file or filesystem status"


# ─── System Information ──────────────────────────────────────────────────────

class FreeCommand:
    """Display amount of free and used memory (free)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        human = "-h" in args or "-m" in args or "-g" in args

        # Stub system memory info
        total_mem = 16384 * 1024  # 16 GB in KB
        used_mem = 8192 * 1024
        free_mem = total_mem - used_mem
        shared = 256 * 1024
        buffers = 1024 * 1024
        cached = 2048 * 1024
        available = free_mem + cached

        swap_total = 4096 * 1024
        swap_used = 0
        swap_free = swap_total

        def fmt(val):
            if not human:
                return str(val // 1024)
            if val >= 1024 * 1024:
                return f"{val / (1024 * 1024):.1f}Gi"
            return f"{val // 1024}Mi"

        print(f"              total        used        free      shared  buff/cache   available")
        print(f"Mem:          {fmt(total_mem):>8}    {fmt(used_mem):>8}    {fmt(free_mem):>8}    {fmt(shared):>8}    {fmt(buffers + cached):>8}    {fmt(available):>8}")
        print(f"Swap:         {fmt(swap_total):>8}    {fmt(swap_used):>8}    {fmt(swap_free):>8}")

        return 0

    def help(self) -> str:
        return "free - display memory usage"


class WCommand:
    """Show who is logged on and what they are doing (w)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        print(f"USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT")

        # Simulated users
        users = [
            ("root", "pts/0", "192.168.1.100", "09:30", "0.00s", "0.01s", "0.00s", "bash"),
            ("admin", "pts/1", "192.168.1.101", "10:15", "5:30", "0.02s", "0.01s", "vim config.conf"),
        ]

        for user in users:
            print(f"{user[0]:<8} {user[1]:<8} {user[2]:<16} {user[3]:<7} {user[4]:<6} {user[5]:<5} {user[6]:<5} {user[7]}")

        return 0

    def help(self) -> str:
        return "w - show who is logged on and what they are doing"


class UptimeCommand:
    """Show how long the system has been running (uptime)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        import random
        days = random.randint(1, 365)
        hours = random.randint(0, 23)
        mins = random.randint(0, 59)
        users = random.randint(1, 5)
        load1 = random.uniform(0.1, 2.0)
        load2 = random.uniform(0.1, 2.0)
        load3 = random.uniform(0.1, 2.0)

        now = time.strftime("%H:%M:%S")
        print(f" {now} up {days} days, {hours:02d}:{mins:02d},  {users} user{'s' if users != 1 else ''},  load average: {load1:.2f}, {load2:.2f}, {load3:.2f}")

        return 0

    def help(self) -> str:
        return "uptime - show how long the system has been running"


# ─── Process Management ──────────────────────────────────────────────────────

class PkillCommand:
    """Kill processes by name (pkill)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        exact = "-x" in args
        signal = "-9" if "-9" in args else None

        patterns = [a for a in args if not a.startswith("-")]
        if not patterns:
            print("pkill: missing pattern", file=sys.stderr)
            return 1

        pattern = patterns[0]
        print(f"pkill: killing processes matching '{pattern}' (stub)")

        return 0

    def help(self) -> str:
        return "pkill - kill processes by name"


class PgrepCommand:
    """List processes by name (pgrep)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        full = "-f" in args
        exact = "-x" in args
        count = "-c" in args

        patterns = [a for a in args if not a.startswith("-")]
        if not patterns:
            print("pgrep: missing pattern", file=sys.stderr)
            return 1

        # Stub: simulate finding processes
        import random
        pattern = patterns[0]

        if count:
            print(str(random.randint(1, 5)))
            return 0

        # Simulate some PIDs
        pids = sorted([random.randint(1000, 9999) for _ in range(random.randint(1, 3))])
        for pid in pids:
            print(pid)

        return 0 if pids else 1

    def help(self) -> str:
        return "pgrep - look up processes by name"


# ─── User/Group Management ───────────────────────────────────────────────────

class UseraddCommand:
    """Create a new user (useradd)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args or args[0].startswith("-"):
            print("useradd: missing operand", file=sys.stderr)
            return 1

        username = args[0]
        create_home = "-m" in args
        shell = "/bin/bash"
        uid = None

        i = 0
        while i < len(args):
            if args[i] == "-s" and i + 1 < len(args):
                shell = args[i + 1]
                i += 2
            elif args[i] == "-u" and i + 1 < len(args):
                uid = args[i + 1]
                i += 2
            else:
                i += 1

        print(f"[*] useradd: creating user '{username}'")
        print(f"    Shell: {shell}")
        if create_home:
            print(f"    Home: /home/{username} (created)")
        if uid:
            print(f"    UID: {uid}")

        return 0

    def help(self) -> str:
        return "useradd - create a new user"


class UsermodCommand:
    """Modify a user account (usermod)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args or args[0].startswith("-"):
            print("usermod: missing operand", file=sys.stderr)
            return 1

        username = args[0]
        print(f"[*] usermod: modifying user '{username}' (stub)")

        return 0

    def help(self) -> str:
        return "usermod - modify a user account"


class UserdelCommand:
    """Delete a user account (userdel)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        remove_home = "-r" in args
        users = [a for a in args if not a.startswith("-")]

        if not users:
            print("userdel: missing operand", file=sys.stderr)
            return 1

        for user in users:
            print(f"[*] userdel: removing user '{user}'")
            if remove_home:
                print(f"    Home directory /home/{user} removed")

        return 0

    def help(self) -> str:
        return "userdel - delete a user account"


class GroupaddCommand:
    """Create a new group (groupadd)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args or args[0].startswith("-"):
            print("groupadd: missing operand", file=sys.stderr)
            return 1

        group = args[0]
        print(f"[*] groupadd: creating group '{group}'")

        return 0

    def help(self) -> str:
        return "groupadd - create a new group"


class GroupdelCommand:
    """Delete a group (groupdel)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args or args[0].startswith("-"):
            print("groupdel: missing operand", file=sys.stderr)
            return 1

        group = args[0]
        print(f"[*] groupdel: deleting group '{group}'")

        return 0

    def help(self) -> str:
        return "groupdel - delete a group"


class GroupmodCommand:
    """Modify a group definition (groupmod)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args or args[0].startswith("-"):
            print("groupmod: missing operand", file=sys.stderr)
            return 1

        group = args[0]
        print(f"[*] groupmod: modifying group '{group}' (stub)")

        return 0

    def help(self) -> str:
        return "groupmod - modify a group definition"


class ChfnCommand:
    """Change real user name and information (chfn)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args or args[0].startswith("-"):
            print("chfn: missing operand", file=sys.stderr)
            return 1

        user = args[0]
        print(f"[*] chfn: changing finger info for '{user}' (stub)")

        return 0

    def help(self) -> str:
        return "chfn - change real user name and information"


class ChshCommand:
    """Change login shell (chsh)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        shell = "/bin/bash"
        users = []
        i = 0
        while i < len(args):
            if args[i] == "-s" and i + 1 < len(args):
                shell = args[i + 1]
                i += 2
            elif not args[i].startswith("-"):
                users.append(args[i])
                i += 1
            else:
                i += 1

        if not users:
            print("chsh: missing operand", file=sys.stderr)
            return 1

        for user in users:
            print(f"[*] chsh: changing shell for '{user}' to '{shell}'")

        return 0

    def help(self) -> str:
        return "chsh - change login shell"


class ChageCommand:
    """Change user password expiry information (chage)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args or args[0].startswith("-"):
            print("chage: missing operand", file=sys.stderr)
            return 1

        user = args[0]
        print(f"[*] chage: modifying password age for '{user}' (stub)")

        return 0

    def help(self) -> str:
        return "chage - change user password expiry information"


class GpasswdCommand:
    """Administer /etc/group (gpasswd)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args:
            print("gpasswd: missing operand", file=sys.stderr)
            return 1

        if args[0] == "-a" and len(args) >= 3:
            print(f"[*] gpasswd: adding user '{args[1]}' to group '{args[2]}'")
        elif args[0] == "-d" and len(args) >= 3:
            print(f"[*] gpasswd: deleting user '{args[1]}' from group '{args[2]}'")
        else:
            print(f"[*] gpasswd: managing group (stub)")

        return 0

    def help(self) -> str:
        return "gpasswd - administer /etc/group"


class NewgrpCommand:
    """Log in to a new group (newgrp)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args:
            print("newgrp: missing group", file=sys.stderr)
            return 1

        group = args[0]
        print(f"[*] newgrp: switching to group '{group}' (stub)")

        return 0

    def help(self) -> str:
        return "newgrp - log in to a new group"


# ─── Session & Terminal ──────────────────────────────────────────────────────

class MesgCommand:
    """Display or control write access to the terminal (mesg)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args:
            print("is y")  # default
            return 0

        if args[0] == "y":
            print("mesg: write access enabled")
        elif args[0] == "n":
            print("mesg: write access disabled")
        else:
            print(f"mesg: {args[0]}")

        return 0

    def help(self) -> str:
        return "mesg - display or control write access to the terminal"


class LastCommand:
    """Show listing of last logged in users (last)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        print("wtmp begins Mon Jan  1 00:00:00 2024")
        entries = [
            ("admin", "pts/0", "192.168.1.100", "Mon Jan  1 09:30", "still logged in"),
            ("root", "pts/1", "192.168.1.101", "Mon Jan  1 08:00", "still logged in"),
            ("admin", "pts/0", "192.168.1.100", "Sun Dec 31 22:15", "gone - no logout"),
        ]

        for entry in entries:
            print(f"{entry[0]:<10} {entry[1]:<12} {entry[2]:<16} {entry[3]:<20} {entry[4]}")

        return 0

    def help(self) -> str:
        return "last - show listing of last logged in users"


class LastlogCommand:
    """Reports the most recent login of all users or a given user (lastlog)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        print(f"Username         Port     From             Latest")
        entries = [
            ("root", "pts/1", "192.168.1.101", "Mon Jan  1 08:00:00 +0000"),
            ("admin", "pts/0", "192.168.1.100", "Mon Jan  1 09:30:00 +0000"),
            ("nobody", "**Never logged in**", "", ""),
        ]

        for entry in entries:
            print(f"{entry[0]:<16} {entry[1]:<8} {entry[2]:<16} {entry[3]}")

        return 0

    def help(self) -> str:
        return "lastlog - reports the most recent login of all users"


# ─── File Patching & Searching ───────────────────────────────────────────────

class PatchCommand:
    """Apply a diff file to produce a patch (patch)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args:
            print("patch: missing input file", file=sys.stderr)
            return 1

        print(f"patch: processing '{args[0]}' (stub)")

        return 0

    def help(self) -> str:
        return "patch - apply a diff file to produce a patch"


class LocateCommand:
    """List files in databases that match a pattern (locate)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args:
            print("locate: missing pattern", file=sys.stderr)
            return 1

        pattern = args[-1]
        print(f"locate: searching for '{pattern}' in mlocate.db (stub)")

        # Simulated results
        print(f"/etc/passwd")
        print(f"/home/admin/.bashrc")
        print(f"/usr/bin/{pattern}")

        return 0

    def help(self) -> str:
        return "locate - list files in databases that match a pattern"


class UpdatedbCommand:
    """Update a database for locate (updatedb)."""

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        print("updatedb: scanning filesystem (stub)")

        return 0

    def help(self) -> str:
        return "updatedb - update a database for locate"
