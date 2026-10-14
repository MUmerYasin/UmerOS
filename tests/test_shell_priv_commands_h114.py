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

"""tests — capability gating of privileged shell command handlers.

`kill`/`killall`/`pkill`/`shutdown`/`modprobe`/`mount`/`insmod` used to run
with no capability check (they relied on an unenforced `current_user`), and
`chmod`/`chown` were un-gated no-op prints. They are now capability-gated:

  * process/system/module/mount ops  -> CAP_SYS_ADMIN
  * permission changes               -> CAP_FS_PERMS

Semantics match the shared gate: wired manager -> fail-closed; strict &
unwired -> fail-closed; unwired default -> permissive (backward compatible).
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
    CAP_FS_PERMS,
    CAP_SYS_ADMIN,
    ChmodCommand,
    ChownCommand,
    CommandContext,
    InsmodCommand,
    KillallCommand,
    KillCommand,
    ModprobeCommand,
    MountCommand,
    PkillCommand,
    ShutdownCommand,
    get_registry,
)

PRIV_SYS = [KillCommand, KillallCommand, PkillCommand, ShutdownCommand,
            ModprobeCommand, MountCommand, InsmodCommand]
PRIV_PERMS = [ChmodCommand, ChownCommand]


class _FakeManager:
    """Minimal wired trust source: grants only the capabilities in ``allow``."""

    def __init__(self, allow=()):
        self.allow = set(allow)

    def query(self, pid, cap):
        return cap in self.allow


class _Task:
    def __init__(self, name):
        self.name = name


class _FakeScheduler:
    def __init__(self):
        self._tasks = {101: _Task("umer-worker"), 102: _Task("other")}
        self.terminated = []

    def terminate(self, pid):
        self.terminated.append(pid)
        self._tasks.pop(pid, None)


class _FakeVFS:
    def read_file(self, path):
        return "qfs_root / qfs rw,relatime 0 0"


class _FakeShell:
    def __init__(self):
        self.current_user = "umer"


class _FakeKernel:
    def __init__(self):
        self.scheduler = _FakeScheduler()
        self.vfs = _FakeVFS()
        self.shutdown_called = False

    def request_shutdown(self):
        self.shutdown_called = True


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
    kernel = _FakeKernel()
    return CommandContext(kernel, _FakeShell()), kernel


# ── constants / registry / wiring ─────────────────────────────────────────
def test_cap_constants():
    assert CAP_SYS_ADMIN == "sys.admin"
    assert CAP_FS_PERMS == "fs.perms"


def test_registry_contains_privileged_commands():
    reg = get_registry()
    for name in ("kill", "killall", "pkill", "shutdown", "modprobe",
                 "mount", "insmod", "chmod", "chown"):
        assert name in reg, f"{name} missing from registry"


def test_docstring_documents_gating():
    doc = sc.__doc__ or ""
    # NB: the cosmetic "[FIX Hxxx]" tag can be stripped by external
    # tooling, so assert on the substantive documented content.
    assert "CAP_SYS_ADMIN" in doc and "CAP_FS_PERMS" in doc


# ── permissive when unwired (backward compatible) ─────────────────────────
def test_kill_permissive_when_unwired():
    ctx, kernel = _ctx()
    out = KillCommand().execute(ctx, ["101"])
    assert "Sent SIGTERM to process 101" in out
    assert kernel.scheduler.terminated == [101]


def test_killall_permissive_when_unwired():
    ctx, kernel = _ctx()
    out = KillallCommand().execute(ctx, ["umer-worker"])
    assert "Terminated 1 process(es)" in out
    assert kernel.scheduler.terminated == [101]


def test_shutdown_permissive_when_unwired():
    ctx, kernel = _ctx()
    out = ShutdownCommand().execute(ctx, [])
    assert "shutting down" in out
    assert kernel.shutdown_called is True


def test_modprobe_permissive_when_unwired():
    ctx, _ = _ctx()
    assert "loaded into kernel" in ModprobeCommand().execute(ctx, ["foo"])


def test_mount_permissive_when_unwired():
    ctx, _ = _ctx()
    assert MountCommand().execute(ctx, []) == "qfs_root / qfs rw,relatime 0 0"


def test_chmod_chown_permissive_when_unwired():
    ctx, _ = _ctx()
    assert "changed permissions" in ChmodCommand().execute(ctx, ["755", "f"])
    assert "changed ownership" in ChownCommand().execute(ctx, ["umer", "f"])


def test_insmod_permissive_when_unwired():
    ctx, _ = _ctx()
    assert "inserted module" in InsmodCommand().execute(ctx, ["m.ko"])


# ── fail-closed in strict mode ────────────────────────────────────────────
@pytest.mark.parametrize("cls", PRIV_SYS + PRIV_PERMS)
def test_denied_in_strict_mode(cls):
    ctx, _ = _ctx()
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        cls().execute(ctx, ["x", "y"])


def test_kill_denied_strict_does_not_terminate():
    ctx, kernel = _ctx()
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        KillCommand().execute(ctx, ["101"])
    assert kernel.scheduler.terminated == []


def test_shutdown_denied_strict_does_not_shutdown():
    ctx, kernel = _ctx()
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        ShutdownCommand().execute(ctx, [])
    assert kernel.shutdown_called is False


def test_pkill_denied_transitively_via_killall():
    """pkill delegates to killall, so it inherits the gate."""
    ctx, kernel = _ctx()
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        PkillCommand().execute(ctx, ["umer-worker"])
    assert kernel.scheduler.terminated == []


# ── wired manager: denied / allowed (per capability) ──────────────────────
@pytest.mark.parametrize("cls", PRIV_SYS)
def test_sys_commands_denied_when_wired_without_cap(cls):
    ctx, _ = _ctx()
    gate.wire(_FakeManager(allow=()))
    with pytest.raises(PermissionError):
        cls().execute(ctx, ["x", "y"])


@pytest.mark.parametrize("cls", PRIV_SYS)
def test_sys_commands_allowed_when_wired_with_sys_admin(cls):
    ctx, _ = _ctx()
    gate.wire(_FakeManager(allow={CAP_SYS_ADMIN}))
    cls().execute(ctx, ["x", "y"])  # must not raise


@pytest.mark.parametrize("cls", PRIV_PERMS)
def test_perm_commands_denied_with_only_sys_admin(cls):
    """chmod/chown need CAP_FS_PERMS specifically, not CAP_SYS_ADMIN."""
    ctx, _ = _ctx()
    gate.wire(_FakeManager(allow={CAP_SYS_ADMIN}))
    with pytest.raises(PermissionError):
        cls().execute(ctx, ["umer", "f"])


@pytest.mark.parametrize("cls", PRIV_PERMS)
def test_perm_commands_allowed_with_fs_perms(cls):
    ctx, _ = _ctx()
    gate.wire(_FakeManager(allow={CAP_FS_PERMS}))
    cls().execute(ctx, ["umer", "f"])  # must not raise


# ── source invariants ─────────────────────────────────────────────────────
def test_source_has_gates_and_import():
    src = (ROOT / "kernel" / "shell_commands.py").read_text(encoding="utf-8")
    assert "from core.capability_gate import gate, CAP_SYS_ADMIN, CAP_FS_PERMS" in src
    assert src.count("gate.require(CAP_SYS_ADMIN)") >= 6
    assert src.count("gate.require(CAP_FS_PERMS)") >= 2
