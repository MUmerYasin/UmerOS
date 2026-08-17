"""
UmerOS /bin C Shell Interface
=============================
Implements the C Shell (csh) as required by FSSTND.
"""

from __future__ import annotations

import os
import sys
from typing import Any, List, Optional, Tuple


class CshCommand:
    """
    C Shell interface (csh).

    Provides a command-line interpreter with C-like syntax.
    In UmerOS, this is a minimal stub implementing basic shell features.
    """

    def __init__(self) -> None:
        self.name = "csh"
        self.description = "C shell command interpreter"
        self.usage = "csh [-c command] [-h] [-v] [-x]"
        self._running = False

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if len(args) > 0 and args[0] in ("-c", "--command"):
            if len(args) < 2:
                print("csh: -c requires an argument", file=sys.stderr)
                return 1
            command = args[1]
            return self._execute_string(command, stdin, stdout)

        if len(args) > 0 and args[0] not in ("-", "--"):
            script_path = args[0]
            script_args = args[1:] if len(args) > 1 else []
            return self._execute_file(script_path, script_args, stdin, stdout)

        return self._interactive_mode(stdin, stdout)

    def _interactive_mode(self, stdin: Any = None, stdout: Any = None) -> int:
        self._running = True
        print("UmerOS csh (stub) - type 'exit' to quit")
        while self._running:
            try:
                line = input("csh% ").strip()
                if not line:
                    continue
                if line in ("exit", "quit"):
                    break
                exit_code = self._execute_string(line, stdin, stdout)
                if exit_code != 0:
                    pass
            except (EOFError, KeyboardInterrupt):
                print()
                break
        return 0

    def _execute_string(self, command: str, stdin: Any = None, stdout: Any = None) -> int:
        tokens = command.split()
        if not tokens:
            return 0

        cmd = tokens[0]
        cmd_args = tokens[1:]

        builtins = {
            "exit": lambda a: self._builtin_exit(a),
            "cd": lambda a: self._builtin_cd(a),
            "pwd": lambda a: self._builtin_pwd(a),
            "echo": lambda a: self._builtin_echo(a),
            "set": lambda a: 0,
            "unset": lambda a: 0,
            "alias": lambda a: 0,
            "unalias": lambda a: 0,
            "history": lambda a: 0,
            "source": lambda a: self._builtin_source(a),
        }

        if cmd in builtins:
            return builtins[cmd](cmd_args)

        try:
            module = __import__("bin.shell", fromlist=["ShCommand"])
            sh_cmd = module.ShCommand()
            return sh_cmd.execute(tokens, stdin, stdout)
        except Exception:
            print(f"{cmd}: Command not found.", file=sys.stderr)
            return 1

    def _execute_file(self, script_path: str, args: List[str], stdin: Any = None, stdout: Any = None) -> int:
        if not os.path.exists(script_path):
            print(f"csh: Can't open {script_path}", file=sys.stderr)
            return 1

        try:
            with open(script_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    exit_code = self._execute_string(line, stdin, stdout)
                    if exit_code != 0:
                        return exit_code
            return 0
        except Exception as e:
            print(f"csh: {e}", file=sys.stderr)
            return 1

    def _builtin_exit(self, args: List[str]) -> int:
        self._running = False
        return 0

    def _builtin_cd(self, args: List[str]) -> int:
        target = args[0] if args else os.path.expanduser("~")
        try:
            os.chdir(target)
            return 0
        except OSError as e:
            print(f"csh: {e}", file=sys.stderr)
            return 1

    def _builtin_pwd(self, args: List[str]) -> int:
        print(os.getcwd())
        return 0

    def _builtin_echo(self, args: List[str]) -> int:
        print(' '.join(args))
        return 0

    def _builtin_source(self, args: List[str]) -> int:
        if not args:
            print("csh: source requires a filename", file=sys.stderr)
            return 1
        return self._execute_file(args[0], [], None, None)

    def help(self) -> str:
        return "UmerOS C Shell (csh) - C-like command interpreter"


def _selftest() -> bool:
    """Run self-tests for csh module."""
    try:
        # CshCommand (non-interactive tests only)
        cs = CshCommand()
        assert cs.name == "csh"
        assert cs.execute(["-c", "exit"]) == 0
        assert cs.execute(["-c", "echo hello"]) == 0

        # Test exit code from command
        assert cs.execute(["-c", "nonexistent_cmd_xyz"]) != 0

        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"_selftest FAILED: {e}")
        return False
