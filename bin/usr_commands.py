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
