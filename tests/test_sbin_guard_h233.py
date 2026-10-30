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

"""H233 -- capability-gate + audit every ``/sbin`` command, not just the façade.

The row says ``SbinManager.execute()`` "and each command ``execute()``" run
privileged-simulated ops with "no ``CapabilityManager`` gate and no audit
logging".

Drift-recon (session 219): **half stale, half true** --

* **Stale** on the manager: ``SbinManager.execute`` already called
  ``gate.require(CAP_SYS_ADMIN)`` (landed with the cap-gate cluster; the comment
  above it cites this row by number).  ``tests/test_cap_gate.py::
  test_sbin_execute_gated`` already pinned it.
* **True** on the commands: that gate sat on the **façade only**.  Every command
  class is a public ``SbinCommand`` subclass, so ``HaltCommand().execute()`` --
  or any ``import sbin.boot`` -- reached the privileged path ungated.  There are
  **7 duplicated ``SbinCommand`` base classes** (one per module) and all **45**
  commands define their own ``execute()``, so the bypass was wide open.
* **True** on auditing: ``sbin/`` had no audit log at all.  Only
  ``sbin/__init__.py`` imported ``logging``, and it never logged a command.

Fix: a single shared guard (``sbin/command_guard.py``) installed through
``__init_subclass__`` on each base class, so the wrapper exists before any
caller can reach ``execute()`` -- including commands written later.  This file
pins both halves plus the audit trail.
"""

from __future__ import annotations

import ast
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
if str(PROJ) not in sys.path:
    sys.path.insert(0, str(PROJ))

from core.capability_gate import (  # noqa: E402
    CapabilityGate,
    CAP_SYS_ADMIN,
)
from kernel.capability_manager import CapabilityManager  # noqa: E402

import sbin.command_guard as guard_mod  # noqa: E402
from sbin.sbin_manager import SBIN_COMMAND_REGISTRY, SbinManager  # noqa: E402

SBIN = PROJ / "sbin"

#: One module per duplicated ``SbinCommand`` base class.
BASE_MODULES = [
    "boot",
    "filesystem",
    "maintenance",
    "modules",
    "mount",
    "network",
    "system",
]

#: A representative command from each module -- all must be gated directly.
MODULE_COMMANDS = [
    ("sbin.boot", "HaltCommand"),
    ("sbin.filesystem", "MkfsCommand"),
    ("sbin.maintenance", "MktempCommand"),
    ("sbin.modules", "InsmodCommand"),
    ("sbin.mount", "MountCommand"),
    ("sbin.network", "IfconfigCommand"),
    ("sbin.system", "SysctlCommand"),
]

AUDIT_LOGGER = "UmerOS.Sbin.Audit"


def _make_wired_gate(pid: int, caps) -> CapabilityGate:
    """Build a gate wired to a real CapabilityManager granting ``caps`` to ``pid``."""
    cm = CapabilityManager()
    cm.register(pid)
    for cap in caps:
        cm.grant(pid, cap)
    g = CapabilityGate()
    g.wire(cm)
    return g


@pytest.fixture
def denied():
    """Wire a gate that denies ``sys.admin`` to this process."""
    prev = guard_mod.gate
    guard_mod.gate = _make_wired_gate(pid=os.getpid(), caps=[])
    try:
        yield guard_mod.gate
    finally:
        guard_mod.gate = prev


@pytest.fixture
def allowed():
    """Wire a gate that grants ``sys.admin`` to this process."""
    prev = guard_mod.gate
    guard_mod.gate = _make_wired_gate(pid=os.getpid(), caps=[CAP_SYS_ADMIN])
    try:
        yield guard_mod.gate
    finally:
        guard_mod.gate = prev


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Structural invariants: the hook is on every duplicated base class
# ---------------------------------------------------------------------------

class TestBaseClassHook:
    @pytest.mark.parametrize("mod", BASE_MODULES)
    def test_base_declares_init_subclass(self, mod):
        tree = ast.parse(_src(SBIN / f"{mod}.py"))
        bases = [
            n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "SbinCommand"
        ]
        assert len(bases) == 1, f"{mod}.py must define exactly one SbinCommand"
        assigns = {
            target.id: ast.unparse(value)
            for node in bases[0].body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            for value in [node.value]
        }
        assert assigns.get("__init_subclass__") == "install_guard", (
            f"{mod}.py SbinCommand must set `__init_subclass__ = install_guard`"
        )

    @pytest.mark.parametrize("mod", BASE_MODULES)
    def test_base_imports_the_guard(self, mod):
        src = _src(SBIN / f"{mod}.py")
        assert "from .command_guard import install_guard" in src, (
            f"{mod}.py must import install_guard from the shared guard module"
        )

    def test_guard_module_surface(self):
        for name in ("install_guard", "argv_summary", "audit", "_guarded_execute"):
            assert hasattr(guard_mod, name), f"command_guard is missing {name}"
        assert guard_mod.CAPABILITY == CAP_SYS_ADMIN

    def test_manager_still_gates_and_audits(self):
        """The façade gate must not regress; it now audits too."""
        tree = ast.parse(_src(SBIN / "sbin_manager.py"))
        mgr = next(
            n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "SbinManager"
        )
        execute = next(
            f for f in mgr.body
            if isinstance(f, ast.FunctionDef) and f.name == "execute"
        )
        src = ast.get_source_segment(_src(SBIN / "sbin_manager.py"), execute)
        assert "gate.require(CAP_SYS_ADMIN)" in src
        assert "audit(" in src, "SbinManager.execute must emit an audit record"
        assert "AUDIT" not in src  # records come from the guard's audit() helper


# ---------------------------------------------------------------------------
# The bypass is closed: a direct command call is gated
# ---------------------------------------------------------------------------

class TestDirectCallIsGated:
    @pytest.mark.parametrize("mod_name,cls_name", MODULE_COMMANDS)
    def test_direct_execute_raises_when_denied(self, denied, mod_name, cls_name):
        """The decisive test: no SbinManager in the call path at all."""
        cls = getattr(importlib.import_module(mod_name), cls_name)
        with pytest.raises(PermissionError):
            cls().execute([])

    def test_manager_path_still_raises_when_denied(self):
        prev = guard_mod.gate
        import sbin.sbin_manager as mgr_mod

        prev_mgr_gate = mgr_mod.gate
        mgr_mod.gate = _make_wired_gate(pid=os.getpid(), caps=[])
        try:
            with pytest.raises(PermissionError):
                SbinManager().execute("reboot")
        finally:
            mgr_mod.gate = prev_mgr_gate
            guard_mod.gate = prev

    def test_direct_execute_runs_when_capability_held(self, allowed):
        from sbin.boot import HaltCommand

        assert HaltCommand().execute([]) == 0

    def test_all_registered_commands_are_wrapped(self):
        """Every one of the registry's command classes carries the wrapper."""
        unwrapped = []
        for name, cls in sorted(SBIN_COMMAND_REGISTRY.items()):
            func = cls.__dict__.get("execute")
            if func is None or not getattr(func, "__sbin_guarded__", False):
                unwrapped.append(name)
        assert unwrapped == [], f"commands with an unguarded execute(): {unwrapped}"

    def test_every_command_class_in_the_folder_defines_execute(self):
        """A subclass that inherits a bare `execute` would escape the hook."""
        offenders = []
        for path in sorted(SBIN.glob("*.py")):
            tree = ast.parse(_src(path))
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                bases = [ast.unparse(b) for b in node.bases]
                if "SbinCommand" not in bases:
                    continue
                if not any(
                    isinstance(f, ast.FunctionDef) and f.name == "execute"
                    for f in node.body
                ):
                    offenders.append(f"{path.name}.{node.name}")
        assert offenders == [], (
            f"command classes without their own execute(): {offenders}"
        )


# ---------------------------------------------------------------------------
# Opt-out + idempotency of the hook
# ---------------------------------------------------------------------------

class TestHookSemantics:
    def test_capability_none_opts_out_of_the_gate(self, denied):
        from sbin.boot import SbinCommand

        class ReadOnlyProbe(SbinCommand):
            name = "readonly-probe"
            capability = None

            def execute(self, args=None):
                return 0

        assert ReadOnlyProbe().execute([]) == 0

    def test_default_capability_is_sys_admin(self, denied):
        from sbin.boot import SbinCommand

        class GatedProbe(SbinCommand):
            name = "gated-probe"

            def execute(self, args=None):
                return 0

        with pytest.raises(PermissionError):
            GatedProbe().execute([])

    def test_hook_is_idempotent(self):
        from sbin.boot import SbinCommand

        class OnceProbe(SbinCommand):
            name = "once-probe"

            def execute(self, args=None):
                return 0

        first = OnceProbe.__dict__["execute"]
        guard_mod.install_guard(OnceProbe)
        assert OnceProbe.__dict__["execute"] is first, (
            "install_guard must not double-wrap an already guarded execute()"
        )

    def test_permissive_mode_does_not_spam_the_gate_warning(self, caplog):
        """An unwired, non-strict gate must not warn once per command.

        `gate.require` allows-with-a-warning in permissive mode, so calling it
        from the guard would emit one warning per command -- 63 lines for a
        single `maintenance.py` `_selftest` run, which buries the output it is
        meant to accompany.  Enforcement is unchanged (the call is skipped only
        when it could not deny); the audit record still fires.
        """
        from sbin.boot import HaltCommand

        prev = guard_mod.gate
        permissive = CapabilityGate()
        permissive.set_strict(False)
        guard_mod.gate = permissive
        try:
            caplog.set_level(logging.WARNING, logger="UmerOS.CapabilityGate")
            for _ in range(5):
                HaltCommand().execute([])
        finally:
            guard_mod.gate = prev
        assert "PERMISSIVE" not in caplog.text, (
            "the guard must not emit a permissive warning per command invocation"
        )

    def test_strict_mode_without_manager_still_denies(self, caplog):
        """Fail-closed posture survives the anti-spam short-circuit."""
        from sbin.boot import HaltCommand

        prev = guard_mod.gate
        strict = CapabilityGate()
        strict.set_strict(True)
        guard_mod.gate = strict
        try:
            with pytest.raises(PermissionError):
                HaltCommand().execute([])
        finally:
            guard_mod.gate = prev


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    def test_successful_run_emits_start_and_end(self, allowed, caplog):
        from sbin.boot import HaltCommand

        caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)
        HaltCommand().execute([])
        text = caplog.text
        assert "AUDIT START halt" in text
        assert "AUDIT END halt" in text
        assert "exit=0" in text

    def test_denial_emits_a_deny_record(self, denied, caplog):
        from sbin.boot import HaltCommand

        caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)
        with pytest.raises(PermissionError):
            HaltCommand().execute([])
        assert "AUDIT DENY halt" in caplog.text
        assert "sys.admin" in caplog.text

    def test_argument_vector_is_summarised_not_dumped(self, allowed, caplog):
        from sbin.boot import HaltCommand

        caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)
        HaltCommand().execute(["-n", "-f"])
        assert "argv='-n -f'" in caplog.text

    def test_manager_dispatch_is_audited(self, allowed, caplog):
        import sbin.sbin_manager as mgr_mod

        prev = mgr_mod.gate
        mgr_mod.gate = guard_mod.gate
        try:
            caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)
            SbinManager().execute("no-such-command")
        finally:
            mgr_mod.gate = prev
        assert "AUDIT DISPATCH no-such-command" in caplog.text
        assert "AUDIT NOT-FOUND no-such-command" in caplog.text


# ---------------------------------------------------------------------------
# argv_summary bounds
# ---------------------------------------------------------------------------

class TestArgvSummary:
    def test_none_and_empty(self):
        assert guard_mod.argv_summary(None) == "(none)"
        assert guard_mod.argv_summary([]) == "(none)"

    def test_short_list_verbatim(self):
        assert guard_mod.argv_summary(["-l", "/dev/sda"]) == "-l /dev/sda"

    def test_long_list_is_elided_with_a_count(self):
        args = [f"a{i}" for i in range(12)]
        out = guard_mod.argv_summary(args)
        assert out.endswith("(+4 more)"), out
        assert out.count(" ") <= guard_mod.MAX_ARGV_LOGGED + 2

    def test_long_argument_is_truncated(self):
        out = guard_mod.argv_summary(["x" * 500])
        assert len(out) <= guard_mod.MAX_ARG_CHARS
        assert out.endswith("...")

    def test_non_string_arguments_are_coerced(self):
        assert guard_mod.argv_summary([1, 2]) == "1 2"
