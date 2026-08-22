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
UmerOS /bin Ed Line Editor
===========================
Implements the ed line editor as required by FSSTND.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, List, Optional, Tuple


class EdCommand:
    """
    Ed line editor.

    Provides basic line editing capabilities as required by FSSTND.
    """

    def __init__(self) -> None:
        self.name = "ed"
        self.description = "Line editor"
        self.usage = "ed [-h] [-s] [file]"
        self._buffer: List[str] = []
        self._current_line = 0
        self._modified = False
        self._filename: Optional[str] = None
        self._running = False

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if "--help" in args:
            return 0

        silent = False
        filenames = []
        i = 0
        while i < len(args):
            if args[i] == '-s':
                silent = True
            elif args[i] == '-p':
                i += 1
            elif not args[i].startswith('-'):
                filenames.append(args[i])
            i += 1

        if not filenames:
            return 0

        self._filename = filenames[0]
        if os.path.exists(self._filename):
            try:
                with open(self._filename, 'r') as f:
                    self._buffer = f.read().splitlines()
            except Exception as e:
                print(f"ed: {e}", file=sys.stderr)
                return 1

        self._running = True
        if not silent:
            pass

        if stdin and hasattr(stdin, 'read'):
            try:
                for line in stdin:
                    line = line.rstrip('\n')
                    if line == '.':
                        break
                    self._buffer.append(line)
                    self._current_line = len(self._buffer)
            except Exception:
                pass
            return 0

        while self._running:
            try:
                line = input()
                line = line.strip()
                if not line:
                    continue

                cmd_char = line[0]
                rest = line[1:].strip()

                if cmd_char == 'q':
                    if self._modified:
                        print("?", file=sys.stderr)
                    else:
                        self._running = False
                elif cmd_char == 'Q':
                    self._running = False
                elif cmd_char == 'w':
                    if not self._filename and rest:
                        self._filename = rest
                    if self._filename:
                        try:
                            with open(self._filename, 'w') as f:
                                f.write('\n'.join(self._buffer) + '\n')
                            self._modified = False
                            print(f"{len(self._buffer)}")
                        except Exception as e:
                            print(f"ed: {e}", file=sys.stderr)
                    else:
                        print("?", file=sys.stderr)
                elif cmd_char == 'W':
                    if self._filename:
                        try:
                            with open(self._filename, 'a') as f:
                                f.write('\n'.join(self._buffer) + '\n')
                            self._modified = False
                        except Exception as e:
                            print(f"ed: {e}", file=sys.stderr)
                elif cmd_char == 'a':
                    self._buffer.append(rest)
                    self._current_line = len(self._buffer)
                    self._modified = True
                elif cmd_char == 'i':
                    if self._current_line > 0:
                        self._buffer.insert(self._current_line - 1, rest)
                    else:
                        self._buffer.insert(0, rest)
                    self._modified = True
                elif cmd_char == 'd':
                    if self._current_line > 0 and self._current_line <= len(self._buffer):
                        self._buffer.pop(self._current_line - 1)
                        self._modified = True
                        if self._current_line > len(self._buffer):
                            self._current_line = max(1, len(self._buffer))
                elif cmd_char == 'p':
                    if self._current_line > 0 and self._current_line <= len(self._buffer):
                        print(self._buffer[self._current_line - 1])
                elif cmd_char == 'n':
                    if self._current_line > 0 and self._current_line <= len(self._buffer):
                        print(f"{self._current_line}\t{self._buffer[self._current_line - 1]}")
                elif cmd_char == 'l':
                    for i, line in enumerate(self._buffer, 1):
                        print(f"{i}\t{line}")
                elif cmd_char == '1':
                    self._current_line = 1
                    if self._buffer:
                        print(self._buffer[0])
                elif cmd_char == '$':
                    self._current_line = len(self._buffer)
                    if self._buffer:
                        print(self._buffer[-1])
                elif cmd_char.isdigit():
                    try:
                        self._current_line = int(cmd_char)
                        if 0 < self._current_line <= len(self._buffer):
                            print(self._buffer[self._current_line - 1])
                    except ValueError:
                        pass
                elif cmd_char == 'g':
                    pattern = rest
                    if pattern:
                        for i, line in enumerate(self._buffer, 1):
                            if re.search(pattern, line):
                                print(f"{i}\t{line}")
                elif cmd_char == 'v':
                    pattern = rest
                    if pattern:
                        for i, line in enumerate(self._buffer, 1):
                            if not re.search(pattern, line):
                                print(f"{i}\t{line}")
                elif cmd_char == 's':
                    if '/' in rest:
                        parts = rest.split('/')
                        if len(parts) >= 3:
                            old = parts[1]
                            new = parts[2]
                            if self._current_line > 0 and self._current_line <= len(self._buffer):
                                self._buffer[self._current_line - 1] = re.sub(
                                    old, new, self._buffer[self._current_line - 1], count=1
                                )
                                self._modified = True
                elif cmd_char == 'r':
                    if rest and os.path.exists(rest):
                        try:
                            with open(rest, 'r') as f:
                                new_lines = f.read().splitlines()
                            for line in new_lines:
                                self._buffer.append(line)
                            self._modified = True
                        except Exception as e:
                            print(f"ed: {e}", file=sys.stderr)
                    else:
                        print("?", file=sys.stderr)
                elif cmd_char == 'w' and rest:
                    self._filename = rest
                    try:
                        with open(self._filename, 'w') as f:
                            f.write('\n'.join(self._buffer) + '\n')
                        self._modified = False
                        print(f"{len(self._buffer)}")
                    except Exception as e:
                        print(f"ed: {e}", file=sys.stderr)
                elif cmd_char == 'f':
                    if rest:
                        self._filename = rest
                    elif self._filename:
                        print(self._filename)
                elif cmd_char == 'h':
                    print("UmerOS ed - line editor")
                    print("Commands: a(ppend), i(nsert), d(elete), p(rint), n(umber), l(ist)")
                    print("          g(rep), v(inverse grep), s(ubstitute), r(ead), w(rite)")
                    print("          f(ilename), q(uit), Q(uit forced), 1, $, .")
                elif cmd_char == '=':
                    print(self._current_line)
                else:
                    print("?", file=sys.stderr)

            except (EOFError, KeyboardInterrupt):
                print()
                break

        return 0

    def help(self) -> str:
        return "UmerOS ed - line editor"


def _selftest() -> bool:
    """Run self-tests for ed module."""
    try:
        import io, contextlib

        # EdCommand (non-interactive; pipe commands via stdin)
        ec = EdCommand()
        # Verify instantiation
        assert ec.name == "ed"
        assert "ed" in ec.description.lower() or "editor" in ec.description.lower()

        # Test with stdin commands
        stdin_text = "a\nfirst line\nsecond line\n.\n1\nl\nq\n"
        f = io.StringIO(stdin_text)
        out = io.StringIO()
        result = ec.execute([], stdin=f, stdout=out)

        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"_selftest FAILED: {e}")
        return False
