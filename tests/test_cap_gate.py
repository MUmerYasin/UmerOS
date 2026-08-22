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
pytest suite for the zero-trust capability gate (core/capability_gate.py) and
its integration into the cap-gate remediation cluster (H227, H233, H267, H273,
H281, H283, H296, H304).

Proves:
  * When a real CapabilityManager is wired, `gate.require` enforces fail-closed
    (denies a PID that lacks the capability, allows one that holds it).
  * When no manager is wired, the gate is permissive (warning) by default, and
    switches to fail-closed under `set_strict(True)`.
  * The wired modules (srv backup/permissions, tmp reaper/permissions, root
    passwd, sbin execute) raise PermissionError when the required capability is
    denied by the wired manager.
"""

import importlib
import os
import sys

from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from core.capability_gate import (  # noqa: E402
    CapabilityGate,
    CAP_BACKUP,
    CAP_FS_ADMIN,
    CAP_FS_PERMS,
    CAP_REAPER,
    CAP_SYS_ADMIN,
)
from kernel.capability_manager import CapabilityManager  # noqa: E402


def _make_wired_gate(pid: int, caps) -> CapabilityGate:
    """Build a gate wired to a real CapabilityManager that grants `caps` to `pid`."""
    cm = CapabilityManager()
    cm.register(pid)
    for c in caps:
        cm.grant(pid, c)
    g = CapabilityGate()
    g.wire(cm)
    return g


# ── Core gate behaviour ────────────────────────────────────────────────────

def test_require_denies_when_capability_missing():
    g = _make_wired_gate(pid=4242, caps=[CAP_FS_PERMS])  # has perms, NOT backup
    with pytest.raises(PermissionError):
        g.require(CAP_BACKUP, pid=4242)


def test_require_allows_when_capability_held():
    g = _make_wired_gate(pid=4242, caps=[CAP_BACKUP])
    g.require(CAP_BACKUP, pid=4242)  # must not raise


def test_permissive_by_default_without_manager():
    g = CapabilityGate()  # no manager wired
    g.set_strict(False)
    g.require(CAP_SYS_ADMIN)  # must not raise (permissive)


def test_strict_denies_without_manager():
    g = CapabilityGate()
    g.set_strict(True)
    with pytest.raises(PermissionError):
        g.require(CAP_SYS_ADMIN)


def test_query_reflects_manager():
    g = _make_wired_gate(pid=99, caps=[CAP_REAPER])
    assert g.query(CAP_REAPER, pid=99) is True
    assert g.query(CAP_BACKUP, pid=99) is False


# ── Module integration (fail-closed when the process lacks the cap) ─────────

def test_srv_backup_restore_gated():
    from srv.backup import SrvBackupManager

    g = _make_wired_gate(pid=os.getpid(), caps=[])  # current process lacks backup
    # Patch the module-level gate so the call is enforced.
    import srv.backup as mod
    mod.gate = g
    mgr = SrvBackupManager(backup_dir="__nope_backup__", srv_root="__nope_srv__")
    with pytest.raises(PermissionError):
        mgr.restore_backup("does_not_exist.tar.gz")
    mod.gate = CapabilityGate()  # restore benign default


def test_tmp_reaper_gated():
    from tmp.reaper import TmpReaper

    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import tmp.reaper as mod
    mod.gate = g
    reaper = TmpReaper(tmp_root="__nope_tmp__")
    with pytest.raises(PermissionError):
        reaper.clean_by_age()
    mod.gate = CapabilityGate()


def test_root_passwd_write_gated():
    from root.passwd import PasswdManager, PasswdEntry

    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import root.passwd as mod
    mod.gate = g
    mgr = PasswdManager(path=os.path.join("__nope_etc__", "passwd"))
    with pytest.raises(PermissionError):
        mgr.write([PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash")])
    mod.gate = CapabilityGate()


def test_sbin_execute_gated():
    from sbin.sbin_manager import SbinManager

    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import sbin.sbin_manager as mod
    mod.gate = g
    mgr = SbinManager()
    with pytest.raises(PermissionError):
        mgr.execute("reboot")
    mod.gate = CapabilityGate()


# ── H296 (/usr privileged FS) + H304 (/var managers) integration ─────────────


def test_require_allows_fs_admin_when_held():
    """Gate-level positive path: holding CAP_FS_ADMIN must pass require()."""
    g = _make_wired_gate(pid=os.getpid(), caps=[CAP_FS_ADMIN])
    g.require(CAP_FS_ADMIN)  # current process holds fs.admin -> must not raise


@pytest.mark.parametrize(
    "mod_name,cls_name,method,args",
    [
        # H296 — /usr privileged FS managers. Constructed via __new__ so the
        # class-level BASE_DIR.mkdir() in __init__ never touches the real FS
        # (the gate is the first statement, so no instance state is needed).
        ("usr.sendmail_manager", "SendmailManager", "create_sendmail_symlink", ("/tmp/mta",)),
        ("usr.misc_data_manager", "MiscDataManager", "create_misc_file", ("ascii",)),
        ("usr.bsd_compat_manager", "BSDCompatManager", "add_header", ("foo.h",)),
        ("usr.games_data_manager", "GamesDataManager", "add_game_data", ("chess", "data.txt")),
        ("usr.xml_manager", "XMLManager", "add_directory", ("docbook",)),
        # H304 — /var privileged FHS managers, constructed with a temp var_path
        # so the (post-gate) write lands in a throwaway directory.
        ("var.directory_manager", "VarDirectoryManager", "create_local_directory", ("local_sub",)),
        ("var.spool_manager", "SpoolManager", "write_mailbox", ("alice", "hi")),
        ("var.log_manager", "LogManager", "write_log", ("syslog", "hello")),
    ],
)
def test_fs_admin_gated_modules_deny(mod_name, cls_name, method, args, tmp_path):
    """Every privileged /usr and /var FS entry point must raise PermissionError
    when the current process lacks CAP_FS_ADMIN under a wired CapabilityManager.

    This proves the cap-gate is enforced at the integration seam (not merely at
    the unit level): with a real manager denying the caller, the privileged op is
    blocked before any filesystem mutation.
    """
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    g = _make_wired_gate(pid=os.getpid(), caps=[])  # current pid lacks fs.admin
    prev = mod.gate
    mod.gate = g
    try:
        if mod_name.startswith("var."):
            inst = cls(var_path=str(tmp_path))
        else:
            # Bypass __init__ (which would mkdir the real /usr BASE_DIR) — the
            # gate is the first statement, so no instance state is needed.
            inst = cls.__new__(cls)
        with pytest.raises(PermissionError):
            getattr(inst, method)(*args)
    finally:
        mod.gate = prev  # restore benign permissive default


def test_var_spool_allows_when_fs_admin_held(tmp_path):
    """Positive integration path: with CAP_FS_ADMIN held, the privileged op
    proceeds and actually writes (proves the gate does not block legitimate,
    authorized callers)."""
    from var.spool_manager import SpoolManager

    g = _make_wired_gate(pid=os.getpid(), caps=[CAP_FS_ADMIN])
    import var.spool_manager as mod
    prev = mod.gate
    mod.gate = g
    try:
        mgr = SpoolManager(var_path=str(tmp_path))
        assert mgr.write_mailbox("alice", "hello") is True
        assert (tmp_path / "spool" / "mail" / "alice").read_text(encoding="utf-8").startswith("hello")
    finally:
        mod.gate = prev
