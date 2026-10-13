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
Regression tests for H85 (home/* capability gating).

H85 was "privileged `/home` mutation / no capability gate": creating or removing
a home, generating SSH keys, appending to `authorized_keys`, writing
`/var/spool/mail/<user>`, and creating a home backup all ran with **no
CapabilityManager check** -- so any in-process code could mutate another user's
home/SSH/mail.

The fix routes every privileged mutation through the process-global
``core.capability_gate.gate`` with ``CAP_HOME_ADMIN`` ("home.admin"):
  * wired manager  -> fail-closed (``PermissionError`` unless the principal holds it),
  * strict, unwired -> fail-closed,
  * unwired, default -> permissive with a warning (existing tooling keeps working).

``PermissionError`` is an ``OSError`` subclass, so `bin/home.py`'s CLI still
refuses gracefully.
"""

import importlib.util
import os
import sys

import pytest

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from core.capability_gate import CAP_HOME_ADMIN, gate  # noqa: E402


def _load(mod_name, relpath):
    spec = importlib.util.spec_from_file_location(mod_name, os.path.join(_PROJ, relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


hm_mod = _load("umeros_h85_home_manager", "home/home_manager.py")
hssh_mod = _load("umeros_h85_home_ssh", "home/home_ssh.py")
hml_mod = _load("umeros_h85_home_mail", "home/home_mail.py")
hb_mod = _load("umeros_h85_home_backup", "home/home_backup.py")


class _FakeManager:
    """Minimal wired trust source: grants only the capabilities in ``allow``."""

    def __init__(self, allow=()):
        self.allow = set(allow)

    def query(self, pid, cap):  # noqa: D401 - manager protocol
        return cap in self.allow


# A syntactically valid ed25519 public key (so the gate is what refuses,
# not the H87 format validator). Generated once at import time.
def _make_real_pubkey() -> str:
    import tempfile
    _m = hssh_mod.HomeSSHManager(home_path=tempfile.mkdtemp())
    _m.setup_ssh("alice")
    return _m.generate_key("alice", "ed25519").public_key


_REAL_PUBKEY = _make_real_pubkey()


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture(autouse=True)
def _gate_state():
    was_strict = gate.strict
    gate.set_strict(False)
    gate.unwire()
    yield
    gate.set_strict(was_strict)
    gate.unwire()


def test_cap_home_admin_constant():
    assert CAP_HOME_ADMIN == "home.admin"


# --------------------------------------------------------------------------- #
# HomeManager: create_home / remove_home                                       #
# --------------------------------------------------------------------------- #
def test_create_home_permissive_when_unwired(home):
    mgr = hm_mod.HomeManager(home_path=str(home))
    assert mgr.create_home("alice").username == "alice"
    assert (home / "alice").is_dir()


def test_create_home_fail_closed_in_strict_mode(home):
    gate.set_strict(True)
    mgr = hm_mod.HomeManager(home_path=str(home))
    with pytest.raises(PermissionError):
        mgr.create_home("alice")
    assert not (home / "alice").exists()


def test_create_home_denied_when_manager_lacks_cap(home):
    gate.wire(_FakeManager(allow=()))  # wired, but no home.admin
    mgr = hm_mod.HomeManager(home_path=str(home))
    with pytest.raises(PermissionError):
        mgr.create_home("alice")
    assert not (home / "alice").exists()


def test_create_home_allowed_when_manager_grants_cap(home):
    gate.wire(_FakeManager(allow=(CAP_HOME_ADMIN,)))
    mgr = hm_mod.HomeManager(home_path=str(home))
    assert mgr.create_home("alice").username == "alice"
    assert (home / "alice").is_dir()


def test_remove_home_is_gated(home):
    mgr = hm_mod.HomeManager(home_path=str(home))
    mgr.create_home("alice")  # permissive
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        mgr.remove_home("alice")
    assert (home / "alice").is_dir()  # not removed


# --------------------------------------------------------------------------- #
# HomeSSHManager: generate_key / add_authorized_key / write_config             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("method,args", [
    ("generate_key", ("alice",)),
    ("add_authorized_key", ("alice", _REAL_PUBKEY)),
    ("remove_authorized_key", ("alice", _REAL_PUBKEY)),
    ("write_config", ("alice", "Host *\n  ForwardAgent no\n")),
])
def test_ssh_privileged_ops_gated(home, method, args):
    gate.set_strict(True)
    mgr = hssh_mod.HomeSSHManager(home_path=str(home))
    with pytest.raises(PermissionError):
        getattr(mgr, method)(*args)


def test_ssh_ops_allowed_when_wired_with_cap(home):
    gate.wire(_FakeManager(allow=(CAP_HOME_ADMIN,)))
    mgr = hssh_mod.HomeSSHManager(home_path=str(home))
    key = mgr.generate_key("alice")
    assert key is not None
    assert mgr.add_authorized_key("alice", key.public_key) is True
    assert mgr.write_config("alice", "Host *\n") is True


# --------------------------------------------------------------------------- #
# HomeMailManager: deliver / setup_spool                                       #
# --------------------------------------------------------------------------- #
def test_mail_deliver_gated(home):
    gate.set_strict(True)
    mgr = hml_mod.HomeMailManager(home_path=str(home))
    msg = hml_mod.MailMessage(id="m1", from_addr="a@b", to_addr="c@d", subject="s", body="b")
    with pytest.raises(PermissionError):
        mgr.deliver("alice", msg)


def test_mail_setup_spool_gated(home):
    gate.set_strict(True)
    mgr = hml_mod.HomeMailManager(home_path=str(home))
    with pytest.raises(PermissionError):
        mgr.setup_spool("alice")


def test_mail_deliver_allowed_when_wired_with_cap(home):
    gate.wire(_FakeManager(allow=(CAP_HOME_ADMIN,)))
    mgr = hml_mod.HomeMailManager(home_path=str(home))
    msg = hml_mod.MailMessage(id="m1", from_addr="a@b", to_addr="c@d", subject="s", body="b")
    assert mgr.deliver("alice", msg) is True
    assert (home / "alice" / "Maildir" / "new" / "m1").exists()


# --------------------------------------------------------------------------- #
# HomeBackupManager: create_backup (restore was already gated by H83)          #
# --------------------------------------------------------------------------- #
def test_backup_create_gated(home, tmp_path):
    back = tmp_path / "back"
    back.mkdir()
    gate.set_strict(True)
    mgr = hb_mod.HomeBackupManager(home_path=str(home), backup_path=str(back))
    with pytest.raises(PermissionError):
        mgr.create_backup("alice")


def test_backup_create_allowed_when_wired_with_cap(home, tmp_path):
    back = tmp_path / "back"
    back.mkdir()
    (home / "alice").mkdir()
    gate.wire(_FakeManager(allow=(CAP_HOME_ADMIN,)))
    mgr = hb_mod.HomeBackupManager(home_path=str(home), backup_path=str(back))
    assert mgr.create_backup("alice") is not None


# --------------------------------------------------------------------------- #
# Read-only paths must stay UNGATED (strict mode must not break inspection)    #
# --------------------------------------------------------------------------- #
def test_read_paths_not_gated(home):
    # build some state permissively first
    hm = hm_mod.HomeManager(home_path=str(home))
    hm.create_home("alice")
    ssh = hssh_mod.HomeSSHManager(home_path=str(home))
    ssh.setup_ssh("alice")
    ssh.generate_key("alice")
    mail = hml_mod.HomeMailManager(home_path=str(home))
    mail.setup_maildir("alice")

    gate.set_strict(True)  # no read below may raise

    assert hm.get_home("alice") is not None
    assert hm.list_users() == ["alice"]
    assert hm.list_dotfiles("alice") == []
    assert ssh.list_keys("alice") == ["rsa"]
    assert ssh.get_config("alice") == ""
    assert ssh.list_authorized_keys("alice") == []
    assert mail.list_new("alice") == []
    assert mail.get_maildir_path("alice").name == "Maildir"


# --------------------------------------------------------------------------- #
# CLI contract (bin/home.py catches OSError)                                   #
# --------------------------------------------------------------------------- #
def test_permission_error_is_oserror():
    # bin/home.py wraps manager calls in `except (ImportError, OSError, ValueError)`,
    # so a fail-closed capability refusal is reported gracefully, not a crash.
    assert issubclass(PermissionError, OSError)
