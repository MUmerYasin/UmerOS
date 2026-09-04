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
UmerOS /bin Boolean & Shell Commands
=====================================
Boolean operations and shell primitives: true, false, sh

Essential commands for scripting and control flow.
true/false are used in shell scripts for conditional logic.
sh is the POSIX shell required in /bin.
"""

from __future__ import annotations

import os
import sys
from typing import List


# ─── true Command ────────────────────────────────────────────────────────────

class TrueCommand:
    """
    true - do nothing, successfully.

    Usage: true [ignored argument...]

    Exit code: Always 0
    Exit status: success (true)

    In shell scripts, true is used for infinite loops:
        while true; do echo "loop"; done

    Or for conditional logic:
        if true; then echo "always true"; fi

    The command accepts and ignores any arguments.
    """

    def execute(self, args: List[str] | None = None) -> int:
        """Execute true - always returns 0."""
        return 0


# ─── false Command ───────────────────────────────────────────────────────────

class FalseCommand:
    """
    false - do nothing, unsuccessfully.

    Usage: false [ignored argument...]

    Exit code: Always 1
    Exit status: failure (false)

    In shell scripts, false is used for:
        if false; then echo "never"; fi

    Or to create a failing command:
        false || echo "this runs because false failed"

    The command accepts and ignores any arguments.
    """

    def execute(self, args: List[str] | None = None) -> int:
        """Execute false - always returns 1."""
        return 1


# ─── test/[ Command ──────────────────────────────────────────────────────────

class BracketTestCommand:
    """
    [ - evaluate conditional expression (POSIX.2 required).

    Usage: [ EXPRESSION ]
           [[ EXPRESSION ]]

    This is the bracket form of the test command, required by POSIX.2.
    Must end with a closing ] as the last argument.

    Exit codes:
      0 - expression is true
      1 - expression is false
      2 - error (missing ] or invalid expression)
    """

    def execute(self, args: List[str] | None = None) -> int:
        if not args:
            # [RECONCILE] A bare `[` with no arguments has no closing `]`,
            # which is a syntax error -> exit 2 (per the documented contract
            # and POSIX.2), NOT exit 1 (which means "expression is false").
            # The module self-test asserts `BracketTestCommand().execute() == 2`.
            print("[: missing `]'", file=sys.stderr)
            return 2

        # Check for closing bracket
        if args[-1] != "]":
            print("[: missing `]'", file=sys.stderr)
            return 2

        # Strip the [ and ] to get the expression
        expr_args = args[:-1]  # remove closing ]
        if not expr_args:
            return 1  # empty expression is false

        # Delegate to TestCommand logic
        test_cmd = TestCommand()
        return test_cmd.execute(expr_args)


class TestCommand:
    """
    test / [ - evaluate conditional expression.

    Usage: test EXPRESSION
           [ EXPRESSION ]

    Expression types:
      String tests:
        -s FILE    True if file exists and has size > 0
        -z STRING  True if string is empty
        -n STRING  True if string is non-empty
        STRING     True if string is non-empty
        s1 = s2    True if strings are equal
        s1 != s2   True if strings are not equal

      Integer tests:
        n1 -eq n2  True if integers are equal
        n1 -ne n2  True if not equal
        n1 -lt n2  True if n1 < n2
        n1 -le n2  True if n1 <= n2
        n1 -gt n2  True if n1 > n2
        n1 -ge n2  True if n1 >= n2

      File tests:
        -e FILE    True if file exists
        -f FILE    True if regular file
        -d FILE    True if directory
        -r FILE    True if readable
        -w FILE    True if writable
        -x FILE    True if executable
        -L FILE    True if symlink
        -b FILE    True if block device
        -c FILE    True if character device
        -p FILE    True if named pipe (FIFO)
        -S FILE    True if socket
        -s FILE    True if file exists and size > 0

      Logical operators:
        ! EXPR     Negation
        e1 -a e2   AND
        e1 -o e2   OR
        ( e1 )     Grouping

    Return codes:
      0  Expression true
      1  Expression false
      2  Error
    """

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []
        if not args:
            return 1

        # Handle [ command (requires closing ])
        if args[0] == "[":
            if args[-1] != "]":
                print("[: missing ']'", file=sys.stderr)
                return 2
            args = args[1:-1]

        if not args:
            return 1

        return self._evaluate(args)

    def _evaluate(self, args: List[str]) -> int:
        """Evaluate expression."""
        if len(args) == 1:
            v = args[0]
            if v in ("false", "0"):
                return 1
            if v in ("true",):
                return 0
            return 0 if v else 1

        # Handle ( ... )
        if args[0] == "(":
            return self._evaluate_parens(args)

        # Handle negation
        if args[0] == "!":
            result = self._evaluate(args[1:])
            return 1 if result == 0 else 0

        # Handle -a and -o (low precedence)
        for i, a in enumerate(args):
            if a == "-o":
                left = self._evaluate(args[:i])
                right = self._evaluate(args[i + 1:])
                return 0 if (left == 0 or right == 0) else 1

        for i, a in enumerate(args):
            if a == "-a":
                left = self._evaluate(args[:i])
                right = self._evaluate(args[i + 1:])
                return 0 if (left == 0 and right == 0) else 1

        # Unary operators
        if len(args) == 2:
            return self._eval_unary(args[0], args[1])

        # Binary operators
        if len(args) == 3:
            return self._eval_binary(args[0], args[1], args[2])

        return 0

    def _eval_unary(self, op: str, arg: str) -> int:
        """Evaluate unary operator."""
        try:
            if op == "-e":
                return 0 if os.path.exists(arg) else 1
            elif op == "-f":
                return 0 if os.path.isfile(arg) else 1
            elif op == "-d":
                return 0 if os.path.isdir(arg) else 1
            elif op == "-r":
                return 0 if os.access(arg, os.R_OK) else 1
            elif op == "-w":
                return 0 if os.access(arg, os.W_OK) else 1
            elif op == "-x":
                return 0 if os.access(arg, os.X_OK) else 1
            elif op == "-L":
                return 0 if os.path.islink(arg) else 1
            elif op == "-b":
                try:
                    return 0 if stat.S_ISBLK(os.stat(arg).st_mode) else 1
                except OSError:
                    return 1
            elif op == "-c":
                try:
                    return 0 if stat.S_ISCHR(os.stat(arg).st_mode) else 1
                except OSError:
                    return 1
            elif op == "-p":
                try:
                    return 0 if stat.S_ISFIFO(os.stat(arg).st_mode) else 1
                except OSError:
                    return 1
            elif op == "-S":
                try:
                    return 0 if stat.S_ISSOCK(os.stat(arg).st_mode) else 1
                except OSError:
                    return 1
            elif op == "-s":
                try:
                    return 0 if os.path.getsize(arg) > 0 else 1
                except OSError:
                    return 1
            elif op == "-z":
                return 0 if len(arg) == 0 else 1
            elif op == "-n":
                return 0 if len(arg) > 0 else 1
        except (OSError, ValueError):
            return 1
        return 2

    def _eval_binary(self, left: str, op: str, right: str) -> int:
        """Evaluate binary operator."""
        try:
            if op == "=":
                return 0 if left == right else 1
            elif op == "!=":
                return 0 if left != right else 1
            elif op == "-eq":
                return 0 if int(left) == int(right) else 1
            elif op == "-ne":
                return 0 if int(left) != int(right) else 1
            elif op == "-lt":
                return 0 if int(left) < int(right) else 1
            elif op == "-le":
                return 0 if int(left) <= int(right) else 1
            elif op == "-gt":
                return 0 if int(left) > int(right) else 1
            elif op == "-ge":
                return 0 if int(left) >= int(right) else 1
        except (ValueError, TypeError):
            return 2
        return 2

    def _evaluate_parens(self, args: List[str]) -> int:
        """Evaluate parenthesized expression."""
        if args[0] == "(" and args[-1] == ")":
            return self._evaluate(args[1:-1])
        return 2


# ─── yes Command ─────────────────────────────────────────────────────────────

class YesCommand:
    """
    yes - output a string repeatedly until killed.

    Usage: yes [STRING]

    Output: STRING repeated until process is terminated.
    Default string: "y"

    Used for answering yes/no prompts automatically:
        yes | command_requiring_confirmation
    """

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []
        string = " ".join(args) if args else "y"

        try:
            while True:
                print(string)
        except (BrokenPipeError, KeyboardInterrupt):
            return 0
        return 0


# ─── printenv Command ────────────────────────────────────────────────────────

class PrintenvCommand:
    """
    printenv - print all or part of environment.

    Usage: printenv [VARIABLE...]

    If no arguments given, prints all environment variables.
    If VARIABLE given, prints its value.
    Exit code: 0 if variable exists, 1 otherwise.
    """

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []
        env = os.environ

        if not args:
            for key in sorted(env.keys()):
                print(f"{key}={env[key]}")
            return 0

        ret = 0
        for var in args:
            val = env.get(var)
            if val is not None:
                print(val)
            else:
                ret = 1
        return ret


# ─── env Command ─────────────────────────────────────────────────────────────

class EnvCommand:
    """
    env - run a program in a modified environment.

    Usage: env [-i] [-u variable] [name=value]... [command [args...]]
      -i: Clear entire environment
      -u variable: Remove variable from environment
      name=value: Set environment variable

    Examples:
        env PATH=/usr/bin command
        env -i HOME=/root /bin/sh
        env -u LD_LIBRARY_PATH command
    """

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []
        if "--help" in args:
            return 0
        env = dict(os.environ)
        clear_all = False
        unset_vars: List[str] = []
        cmd_args: List[str] = []

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-i":
                clear_all = True
            elif arg == "-u" and i + 1 < len(args):
                i += 1
                unset_vars.append(args[i])
            elif "=" in arg:
                key, _, value = arg.partition("=")
                cmd_args.append(f"{key}={value}")
            else:
                cmd_args.append(arg)
            i += 1

        if clear_all:
            env = {}

        for var in unset_vars:
            env.pop(var, None)

        # Parse environment from cmd_args
        real_args: List[str] = []
        for item in cmd_args:
            if "=" in item and not real_args:
                key, _, value = item.partition("=")
                env[key] = value
            else:
                real_args.append(item)

        if not real_args:
            for key in sorted(env.keys()):
                print(f"{key}={env[key]}")
            return 0

        # Execute command with modified environment
        # [FIX H5] Arbitrary host command execution is a privileged operation.
        # Gate it behind CAP_SYS_ADMIN so the env-host-exec path is sandboxed by
        # the zero-trust capability gate (args stay list-form, no shell=True;
        # on a Windows host this is the control that prevents an escape). The
        # require() is OUTSIDE the try so a denied call fails closed instead of
        # being swallowed by the OSError handler below.
        import subprocess
        from core.capability_gate import gate, CAP_SYS_ADMIN
        gate.require(CAP_SYS_ADMIN)
        try:
            result = subprocess.run(real_args, env=env)
            return result.returncode
        except FileNotFoundError:
            print(f"env: '{real_args[0]}': No such file or directory",
                  file=sys.stderr)
            return 127
        except OSError as e:
            print(f"env: {e}", file=sys.stderr)
            return 126


def _selftest() -> bool:
    """Run self-tests for boolean_ops module."""
    try:
        # TrueCommand
        tc = TrueCommand()
        assert tc.execute() == 0
        assert tc.execute(["ignored"]) == 0

        # FalseCommand
        fc = FalseCommand()
        assert fc.execute() == 1
        assert fc.execute(["ignored"]) == 1

        # TestCommand
        tcmd = TestCommand()
        assert tcmd.execute() == 1
        assert tcmd.execute(["-n", "hello"]) == 0
        assert tcmd.execute(["-z", ""]) == 0
        assert tcmd.execute(["-z", "x"]) == 1
        assert tcmd.execute(["1", "-eq", "1"]) == 0
        assert tcmd.execute(["1", "-ne", "2"]) == 0
        assert tcmd.execute(["1", "-gt", "2"]) == 1
        assert tcmd.execute(["2", "-gt", "1"]) == 0
        assert tcmd.execute(["2", "-lt", "1"]) == 1
        assert tcmd.execute(["1", "-le", "1"]) == 0
        assert tcmd.execute(["1", "-ge", "1"]) == 0

        # BracketTestCommand
        btc = BracketTestCommand()
        assert btc.execute() == 2
        assert btc.execute(["-n", "hello", "]"]) == 0
        assert btc.execute(["-z", "", "]"]) == 0
        assert btc.execute(["1", "-eq", "1", "]"]) == 0
        assert btc.execute(["hello"]) == 2  # missing ]

        # YesCommand (skip execute — infinite loop on Windows)
        yc = YesCommand()
        assert hasattr(yc, 'execute')

        # PrintenvCommand
        pec = PrintenvCommand()
        assert pec.execute() == 0
        assert pec.execute(["PATH"]) == 0 or pec.execute(["PATH"]) == 1
        assert pec.execute(["NONEXISTENT_VAR_UMEROS"]) == 1

        # EnvCommand
        ec = EnvCommand()
        assert ec.execute() == 0

        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"_selftest FAILED: {e}")
        return False
