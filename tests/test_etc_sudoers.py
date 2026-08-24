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
Regression tests for H73 (etc/ privileged writers).

H73 was the absence of any capability gate on privileged /etc writes, plus no
validation that a sudoers rule does not grant a blanket ``NOPASSWD: ALL``
privilege-escalation grant. The fix gates ``SudoersManager``,
``CriticalFilesManager``, and ``PasswdGroupManager`` behind ``CAP_FS_ADMIN``
(fail-closed when a CapabilityManager is wired, permissive standalone), rejects
blanket NOPASSWD sudoers grants, and refuses to write into the real host /etc
unless the caller explicitly opts in via ``allow_host_etc=True``.
"""

import importlib.util
import os
import sys

import pytest

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)


def _load(name, rel):
    """Load an etc/ module by file path under a unique module name (the `etc`
    package imports ~95 sibling modules, so we isolate the three under test)."""
    path = os.path.join(_PROJ, "etc", rel)
    spec = importlib.util.spec_from_file_location(f"umeros_etc_{name}_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_sudoers = _load("sudoers", "sudoers.py")
_critical = _load("critical", "critical_files.py")
_passwd = _load("passwd", "passwd_group.py")
from core.capability_gate import gate, CAP_FS_ADMIN  # noqa: E402


@pytest.fixture(autouse=True)
def _gate_state():
    """The capability gate is process-global; restore it after every test."""
    was_strict = gate.strict
    gate.set_strict(False)
    gate.unwire()
    yield
    gate.set_strict(was_strict)
    gate.unwire()


# ── SudoersManager ─────────────────────────────────────────────────────────

def test_sudoers_scoped_rule_written(tmp_path):
    sp = str(tmp_path / "sudoers")
    m = _sudoers.SudoersManager(sudoers_path=sp)
    m.add_rule(_sudoers.SudoRule(user="alice", command="/usr/bin/ls"))
    assert os.path.exists(sp)
    assert "alice /usr/bin/ls" in open(sp).read()


def test_sudoers_blanket_nopasswd_rejected(tmp_path):
    m = _sudoers.SudoersManager(sudoers_path=str(tmp_path / "sudoers"))
    # ALL users, ALL commands, NOPASSWD -> blanket escalation
    with pytest.raises(ValueError):
        m.add_rule(_sudoers.SudoRule(user="ALL", command="ALL", nopasswd=True))
    # specific user but ALL commands, NOPASSWD -> still blanket escalation
    with pytest.raises(ValueError):
        m.add_rule(_sudoers.SudoRule(user="alice", command="ALL", nopasswd=True))


def test_sudoers_scoped_nopasswd_allowed(tmp_path):
    m = _sudoers.SudoersManager(sudoers_path=str(tmp_path / "sudoers"))
    # specific user + specific command + NOPASSWD is a scoped grant (permitted)
    m.add_rule(_sudoers.SudoRule(
        user="jenkins", command="/usr/bin/systemctl restart app", nopasswd=True))
    assert "jenkins NOPASSWD: /usr/bin/systemctl restart app" in open(m.sudoers_path).read()


def test_sudoers_host_etc_refused():
    # default constructor targets real host /etc and must refuse (fail-closed)
    with pytest.raises(ValueError):
        _sudoers.SudoersManager()


def test_sudoers_host_etc_allowed_with_opt_in(tmp_path):
    sp = str(tmp_path / "sudoers")
    m = _sudoers.SudoersManager(sudoers_path=sp, allow_host_etc=True)
    m.add_rule(_sudoers.SudoRule(user="bob"))
    assert os.path.exists(sp)


def test_sudoers_fail_closed_strict_mode_denies(tmp_path):
    m = _sudoers.SudoersManager(sudoers_path=str(tmp_path / "sudoers"))
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        m.add_rule(_sudoers.SudoRule(user="bob"))


# ── CriticalFilesManager ───────────────────────────────────────────────────

def test_critical_files_initialize_writes_temp(tmp_path):
    os.makedirs(str(tmp_path / "etc"), exist_ok=True)
    cf = _critical.CriticalFilesManager(etc_path=str(tmp_path / "etc"))
    assert cf.initialize() is True
    sudoers = (tmp_path / "etc" / "sudoers").read_text(encoding="utf-8")
    # the previously-hardcoded blanket NOPASSWD grant must be gone
    assert "NOPASSWD: ALL" not in sudoers
    assert "umer    ALL=(ALL:ALL) ALL" in sudoers


def test_critical_files_host_etc_refused():
    assert _critical.CriticalFilesManager().initialize() is False


def test_critical_files_fail_closed_strict_mode_denies(tmp_path):
    cf = _critical.CriticalFilesManager(etc_path=str(tmp_path / "etc2"))
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        cf.initialize()


# ── PasswdGroupManager ─────────────────────────────────────────────────────

def test_passwd_group_add_user_writes(tmp_path):
    os.makedirs(str(tmp_path / "etc"), exist_ok=True)
    pg = _passwd.PasswdGroupManager(etc_path=str(tmp_path / "etc"))
    assert pg.add_user("carol") is True
    assert (tmp_path / "etc" / "passwd").exists()


def test_passwd_group_host_etc_refused():
    assert _passwd.PasswdGroupManager().add_user("dave") is False


def test_passwd_group_fail_closed_strict_mode_denies(tmp_path):
    pg = _passwd.PasswdGroupManager(etc_path=str(tmp_path / "etc3"))
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        pg.add_user("eve")
