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
Regression tests for H84 (home/* path traversal).

H84 was a *systemic* CWE-22 in the `home/` package: almost every manager built
`self.home_path / username` (and `message.id` / `name` / `subdir` / `filename`)
and then `mkdir`/`write_text`/`unlink`/`rmtree`'d it with no check that the name
was a single safe path segment. `username = "../etc"` escaped `/home`.

The fix routes every caller-supplied name through the canonical shared guard
``core.path_guard.safe_child`` / ``safe_join`` (fail-closed: ``PathTraversalError``
-- a ``ValueError`` subclass -- is raised *before* any disk mutation).
"""

import importlib.util
import os
import sys

import pytest

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from core.capability_gate import gate  # noqa: E402
from core.path_guard import PathTraversalError  # noqa: E402


def _load(mod_name, relpath):
    """Load a home/ module by FILE PATH under a collision-free name.

    The repo also has `bin/home.py` and `root/home.py`; some tests insert
    `bin/`/`root/` on sys.path and `import home`, which would cache
    ``sys.modules['home']`` as a *module* (not the package). Loading the files
    directly keeps this suite isolated from collection order.
    """
    spec = importlib.util.spec_from_file_location(mod_name, os.path.join(_PROJ, relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


hm_mod = _load("umeros_home_manager_t", "home/home_manager.py")
hd_mod = _load("umeros_home_dirs_t", "home/home_dirs.py")
hl_mod = _load("umeros_home_local_t", "home/home_local.py")
hml_mod = _load("umeros_home_mail_t", "home/home_mail.py")
hq_mod = _load("umeros_home_quota_t", "home/home_quota.py")
hssh_mod = _load("umeros_home_ssh_t", "home/home_ssh.py")
df_mod = _load("umeros_home_dotfiles_t", "home/dotfiles.py")
up_mod = _load("umeros_home_profile_t", "home/user_profile.py")
hb_mod = _load("umeros_home_backup_t", "home/home_backup.py")

EVIL = ["../etc", "../../root", "..", "a/../b", "/etc/passwd", "a\\b", "sub/../../x"]


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture(autouse=True)
def _gate_state():
    """The capability gate is process-global; restore it after every test.

    H85 added ``gate.require(CAP_HOME_ADMIN)`` to the privileged home mutations
    exercised below, so this suite must never observe a strict/wired posture
    leaked from another test.
    """
    was_strict = gate.strict
    gate.set_strict(False)
    gate.unwire()
    yield
    gate.set_strict(was_strict)
    gate.unwire()


# --------------------------------------------------------------------------- #
# HomeManager                                                                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", EVIL)
def test_home_manager_create_home_rejects_traversal(home, bad):
    mgr = hm_mod.HomeManager(home_path=str(home))
    with pytest.raises(PathTraversalError):
        mgr.create_home(bad)


def test_home_manager_get_home_path_rejects(home):
    mgr = hm_mod.HomeManager(home_path=str(home))
    with pytest.raises(PathTraversalError):
        mgr.get_home_path("../etc")


def test_home_manager_create_home_refusal_writes_nothing(home):
    mgr = hm_mod.HomeManager(home_path=str(home))
    with pytest.raises(PathTraversalError):
        mgr.create_home("../escape")
    # nothing outside the managed root was created
    assert sorted(p.name for p in home.iterdir()) == []


def test_home_manager_happy_path_still_works(home):
    mgr = hm_mod.HomeManager(home_path=str(home))
    entry = mgr.create_home("alice")
    assert (home / "alice").is_dir()
    assert (home / "alice" / "Desktop").is_dir()
    assert entry.username == "alice"
    assert mgr.get_home_path("alice") == (home / "alice").resolve()


# --------------------------------------------------------------------------- #
# HomeDirsManager                                                              #
# --------------------------------------------------------------------------- #
def test_home_dirs_setup_and_remove_reject(home):
    mgr = hd_mod.HomeDirsManager(home_path=str(home))
    with pytest.raises(PathTraversalError):
        mgr.setup_user_dirs("../evil")
    with pytest.raises(PathTraversalError):
        mgr.remove_user_dirs("../evil")


def test_home_dirs_get_xdg_dir_rejects(home):
    mgr = hd_mod.HomeDirsManager(home_path=str(home))
    mgr.setup_user_dirs("alice")
    assert mgr.get_xdg_dir("alice", "Desktop") is not None
    with pytest.raises(PathTraversalError):
        mgr.get_xdg_dir("alice", "../../evil")


# --------------------------------------------------------------------------- #
# HomeLocalManager                                                             #
# --------------------------------------------------------------------------- #
def test_home_local_rejects(home, tmp_path):
    mgr = hl_mod.HomeLocalManager(home_path=str(home))
    with pytest.raises(PathTraversalError):
        mgr.setup_local("../evil")
    with pytest.raises(PathTraversalError):
        mgr.get_local_path("../evil", "bin")
    with pytest.raises(PathTraversalError):
        mgr.get_local_path("alice", "../../evil")
    with pytest.raises(PathTraversalError):
        mgr.remove_local("../evil", "bin")

    src = tmp_path / "tool.bin"
    src.write_text("x")
    with pytest.raises(PathTraversalError):
        mgr.install_binary("alice", str(src), name="../../evil")
    with pytest.raises(PathTraversalError):
        mgr.install_data("alice", str(src), subdir="../../evil")


def test_home_local_happy_path(home, tmp_path):
    mgr = hl_mod.HomeLocalManager(home_path=str(home))
    created = mgr.setup_local("alice")
    assert "bin" in created
    src = tmp_path / "tool.bin"
    src.write_text("x")
    dest = mgr.install_binary("alice", str(src), name="mytool")
    assert dest is not None and os.path.basename(dest) == "mytool"


# --------------------------------------------------------------------------- #
# HomeMailManager                                                              #
# --------------------------------------------------------------------------- #
def test_home_mail_rejects(home):
    mgr = hml_mod.HomeMailManager(home_path=str(home))
    with pytest.raises(PathTraversalError):
        mgr.setup_maildir("../evil")
    with pytest.raises(PathTraversalError):
        mgr.get_maildir_path("../evil")
    with pytest.raises(PathTraversalError):
        mgr.get_spool_path("../evil")


def test_home_mail_deliver_rejects_evil_message_id(home):
    mgr = hml_mod.HomeMailManager(home_path=str(home))
    msg = hml_mod.MailMessage(
        id="../../evil", from_addr="a@b", to_addr="c@d", subject="s", body="b"
    )
    with pytest.raises(PathTraversalError):
        mgr.deliver("alice", msg)


def test_home_mail_happy_path(home):
    mgr = hml_mod.HomeMailManager(home_path=str(home))
    mgr.setup_maildir("alice")
    assert (home / "alice" / "Maildir" / "new").is_dir()
    msg = hml_mod.MailMessage(
        id="msg1", from_addr="a@b", to_addr="c@d", subject="hi", body="hello"
    )
    assert mgr.deliver("alice", msg) is True
    assert (home / "alice" / "Maildir" / "new" / "msg1").exists()
    assert mgr.mark_read("alice", "msg1") is True
    assert (home / "alice" / "Maildir" / "cur" / "msg1").exists()


# --------------------------------------------------------------------------- #
# HomeQuotaManager                                                             #
# --------------------------------------------------------------------------- #
def test_home_quota_scan_rejects(home):
    mgr = hq_mod.HomeQuotaManager(home_path=str(home))
    with pytest.raises(PathTraversalError):
        mgr.scan_usage("../evil")


# --------------------------------------------------------------------------- #
# HomeSSHManager                                                               #
# --------------------------------------------------------------------------- #
def test_home_ssh_rejects(home):
    mgr = hssh_mod.HomeSSHManager(home_path=str(home))
    with pytest.raises(PathTraversalError):
        mgr.setup_ssh("../evil")
    with pytest.raises(PathTraversalError):
        mgr.generate_key("../evil")
    with pytest.raises(PathTraversalError):
        mgr.add_authorized_key("../evil", "ssh-rsa AAAA")


def test_home_ssh_happy_path(home):
    mgr = hssh_mod.HomeSSHManager(home_path=str(home))
    mgr.setup_ssh("alice")
    key = mgr.generate_key("alice")
    assert key is not None
    assert (home / "alice" / ".ssh" / "id_rsa").exists()


# --------------------------------------------------------------------------- #
# DotfilesManager                                                              #
# --------------------------------------------------------------------------- #
def test_dotfiles_rejects(home):
    mgr = df_mod.DotfilesManager(home_path=str(home))
    with pytest.raises(PathTraversalError):
        mgr.install_dotfiles("../evil")
    with pytest.raises(PathTraversalError):
        mgr.create_custom("../evil", ".bashrc", "x")
    with pytest.raises(PathTraversalError):
        mgr.remove_dotfile("alice", "../../evil")


def test_dotfiles_happy_path(home):
    mgr = df_mod.DotfilesManager(home_path=str(home))
    installed = mgr.install_dotfiles("alice")
    assert ".bashrc" in installed
    assert (home / "alice" / ".bashrc").exists()


# --------------------------------------------------------------------------- #
# UserProfileManager                                                           #
# --------------------------------------------------------------------------- #
def test_user_profile_rejects(home):
    mgr = up_mod.UserProfileManager(home_path=str(home))
    with pytest.raises(PathTraversalError):
        mgr.create_profile("../evil")


def test_user_profile_happy_path(home):
    mgr = up_mod.UserProfileManager(home_path=str(home))
    prof = mgr.create_profile("alice")
    assert prof.home == str((home / "alice").resolve())
    assert (home / "alice" / ".profile").exists()


# --------------------------------------------------------------------------- #
# HomeBackupManager                                                            #
# --------------------------------------------------------------------------- #
def test_home_backup_create_rejects_traversal(home, tmp_path):
    back = tmp_path / "back"
    back.mkdir()
    mgr = hb_mod.HomeBackupManager(home_path=str(home), backup_path=str(back))
    assert mgr.create_backup("../evil") is None
    assert mgr.create_backup("..") is None
    assert list(back.iterdir()) == []


# --------------------------------------------------------------------------- #
# Contract with bin/home.py (CLI catches ValueError)                           #
# --------------------------------------------------------------------------- #
def test_path_traversal_error_is_valueerror():
    # bin/home.py wraps manager calls in `except (ImportError, OSError, ValueError)`,
    # so the fail-closed refusal is reported gracefully instead of crashing.
    assert issubclass(PathTraversalError, ValueError)
