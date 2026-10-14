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

"""tests — sudo/su capability gating (kernel/shell_commands.py).

`SudoCommand`/`SuCommand` used to mutate `ctx.shell.current_user` with no
authentication or capability check — trivial in-shell privilege escalation.
They are now gated behind `CAP_SYS_ADMIN`:
  * wired manager  -> fail-closed (PermissionError unless the principal holds it),
  * strict, unwired -> fail-closed,
  * unwired, default -> permissive (existing tooling keeps working).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.capability_gate import gate  # noqa: E402
from kernel import shell_commands as sc  # noqa: E402
from kernel.shell_commands import (  # noqa: E402
    CAP_SYS_ADMIN,
    CommandContext,
    ShellCommand,
    SuCommand,
    SudoCommand,
    get_registry,
)


class _FakeManager:
    """Minimal wired trust source: grants only the capabilities in ``allow``."""

    def __init__(self, allow=()):
        self.allow = set(allow)

    def query(self, pid, cap):
        return cap in self.allow


class _EchoCommand(ShellCommand):
    name = "echo"
    help_text = "echo args"
    category = "Test"

    def execute(self, ctx, args):
        return " ".join(args)


class _FakeShell:
    def __init__(self):
        self.current_user = "umer"
        self.registry = {"echo": _EchoCommand()}


class _FakeKernel:
    pass


@pytest.fixture(autouse=True)
def _gate_state():
    strict = gate.strict
    try:
        gate.unwire()
    except Exception:
        pass
    gate.set_strict(False)
    yield
    gate.set_strict(strict)
    try:
        gate.unwire()
    except Exception:
        pass


def _ctx():
    shell = _FakeShell()
    return CommandContext(_FakeKernel(), shell), shell


# ── constants / wiring ────────────────────────────────────────────────────
def test_cap_constant():
    assert CAP_SYS_ADMIN == "sys.admin"


def test_registry_contains_sudo_su():
    reg = get_registry()
    assert "sudo" in reg and "su" in reg


def test_module_is_experimental():
    doc = sc.__doc__ or ""
    assert "[EXPERIMENTAL]" in doc
    assert "CAP_SYS_ADMIN" in doc


# ── permissive when unwired (backward compatible) ─────────────────────────
def test_sudo_permissive_when_unwired():
    ctx, shell = _ctx()
    out = SudoCommand().execute(ctx, ["echo", "hi"])
    assert out == "hi"
    assert shell.current_user == "umer"  # restored after the call


def test_su_permissive_when_unwired():
    ctx, shell = _ctx()
    out = SuCommand().execute(ctx, ["root"])
    assert "Switched to user root" in out
    assert shell.current_user == "root"


def test_sudo_restores_original_user():
    ctx, shell = _ctx()
    SudoCommand().execute(ctx, ["echo", "x"])
    assert shell.current_user == "umer"


# ── fail-closed in strict mode ────────────────────────────────────────────
def test_sudo_denied_in_strict_mode():
    ctx, _ = _ctx()
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        SudoCommand().execute(ctx, ["echo", "hi"])


def test_su_denied_in_strict_mode():
    ctx, _ = _ctx()
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        SuCommand().execute(ctx, ["root"])


# ── wired manager: denied / allowed ───────────────────────────────────────
def test_sudo_denied_when_wired_without_cap():
    ctx, shell = _ctx()
    gate.wire(_FakeManager(allow=()))  # grants nothing
    with pytest.raises(PermissionError):
        SudoCommand().execute(ctx, ["echo", "hi"])
    assert shell.current_user == "umer"  # unchanged


def test_su_denied_when_wired_without_cap():
    ctx, shell = _ctx()
    gate.wire(_FakeManager(allow=()))
    with pytest.raises(PermissionError):
        SuCommand().execute(ctx, ["root"])
    assert shell.current_user == "umer"


def test_sudo_allowed_when_wired_with_cap():
    ctx, shell = _ctx()
    gate.wire(_FakeManager(allow={CAP_SYS_ADMIN}))
    out = SudoCommand().execute(ctx, ["echo", "ok"])
    assert out == "ok"


def test_su_allowed_when_wired_with_cap():
    ctx, shell = _ctx()
    gate.wire(_FakeManager(allow={CAP_SYS_ADMIN}))
    out = SuCommand().execute(ctx, ["root"])
    assert "Switched to user root" in out
    assert shell.current_user == "root"


# ── behavior preserved ────────────────────────────────────────────────────
def test_sudo_runs_subcommand_as_root():
    """While the subcommand runs, current_user must be 'root'."""

    class _Whoami(ShellCommand):
        name = "whoami"
        category = "Test"

        def execute(self, ctx, args):
            return ctx.shell.current_user

    ctx, shell = _ctx()
    shell.registry["whoami"] = _Whoami()
    out = SudoCommand().execute(ctx, ["whoami"])
    assert out == "root"
    assert shell.current_user == "umer"  # restored


def test_sudo_unknown_subcommand():
    ctx, _ = _ctx()
    out = SudoCommand().execute(ctx, ["nope"])
    assert "command not found" in out


def test_sudo_no_args_usage():
    ctx, _ = _ctx()
    assert "usage: sudo" in SudoCommand().execute(ctx, [])


def test_su_strips_dash():
    ctx, shell = _ctx()
    SuCommand().execute(ctx, ["-umer"])
    assert shell.current_user == "umer"


def test_su_defaults_to_root():
    ctx, shell = _ctx()
    SuCommand().execute(ctx, [])
    assert shell.current_user == "root"


# ── source invariants ─────────────────────────────────────────────────────
def test_source_gates_both_commands():
    src = (ROOT / "kernel" / "shell_commands.py").read_text(encoding="utf-8")
    assert src.count("gate.require(CAP_SYS_ADMIN)") >= 2
    assert "from core.capability_gate import gate, CAP_SYS_ADMIN" in src
