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
pytest suite for H72 — `etc/pam_config.py` fail-closed weak-auth guard.

 the weak-auth detector was non-blocking (fail-open):
``INSECURE_PATTERNS`` flagged ``pam_permit.so`` / ``nullok`` but nothing
rejected the write, so ``add_auth_rule`` still persisted an authentication-bypass
PAM stack. The fix consumes ``INSECURE_PATTERNS`` for real, gates
``set_service`` / ``set_pam_conf`` behind ``CAP_FS_ADMIN`` (fail-closed when a
CapabilityManager is wired), and refuses *critical* weak-auth rules unless
explicitly overridden via ``allow_weak=True`` or the capability-gated
``UMEROS_ALLOW_WEAK_PAM=1`` flag.
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
    package imports ~95 sibling modules, so we isolate the one under test)."""
    path = os.path.join(_PROJ, "etc", rel)
    spec = importlib.util.spec_from_file_location(f"umeros_etc_{name}_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_pam = _load("pam_config", "pam_config.py")
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


def _mgr(tmp_path):
    d = tmp_path / "pam.d"
    d.mkdir()
    return _pam.PAMConfigManager(
        pam_d_dir=str(d),
        pam_conf=str(tmp_path / "pam.conf"),
        security_dir=str(tmp_path / "security"),
    )


def _service_file(m):
    return os.path.join(m.pam_d_dir, "sshd")


# ── write guard: fail-closed on critical weak-auth rules ────────────────────

def test_permit_sufficient_auth_rule_refused(tmp_path):
    m = _mgr(tmp_path)
    with pytest.raises(PermissionError):
        m.add_auth_rule("sshd", "pam_permit.so", "sufficient")
    assert not os.path.exists(_service_file(m))


def test_nullok_auth_rule_refused(tmp_path):
    m = _mgr(tmp_path)
    with pytest.raises(PermissionError):
        m.add_auth_rule("sshd", "pam_unix.so", "required", args="nullok")
    assert not os.path.exists(_service_file(m))


def test_pam_permit_password_rule_refused(tmp_path):
    m = _mgr(tmp_path)
    with pytest.raises(PermissionError):
        m.add_password_rule("passwd", "pam_permit.so")
    assert not os.path.exists(os.path.join(m.pam_d_dir, "passwd"))


def test_safe_rule_written(tmp_path):
    m = _mgr(tmp_path)
    res = m.add_auth_rule("sshd", "pam_unix.so", "required")
    assert res["success"] is True
    with open(_service_file(m), encoding="utf-8") as fh:
        assert "auth required pam_unix.so" in fh.read()


def test_medium_risk_rule_is_advisory_not_blocking(tmp_path):
    # `auth required pam_deny.so` is a normal end-of-stack control, NOT a bypass
    m = _mgr(tmp_path)
    res = m.add_auth_rule("sshd", "pam_deny.so", "required")
    assert res["success"] is True


# ── documented, capability-gated override ───────────────────────────────────

def test_env_override_allows_weak_rule(tmp_path, monkeypatch):
    monkeypatch.setenv("UMEROS_ALLOW_WEAK_PAM", "1")
    m = _mgr(tmp_path)
    res = m.add_auth_rule("sshd", "pam_permit.so", "sufficient")
    assert res["success"] is True
    assert os.path.exists(_service_file(m))


def test_explicit_allow_weak_param(tmp_path):
    m = _mgr(tmp_path)
    entries = [{
        "is_comment": False, "is_blank": False, "type": "auth",
        "control": "sufficient", "module": "pam_permit.so", "args": "",
        "raw": "auth sufficient pam_permit.so",
    }]
    res = m.set_service("sshd", entries, allow_weak=True)
    assert res["success"] is True


# ── capability gate (fail-closed when a trust source is wired) ──────────────

def test_strict_gate_denies_write(tmp_path):
    m = _mgr(tmp_path)
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        m.add_auth_rule("sshd", "pam_unix.so", "required")


def test_wired_denying_manager_denies_write(tmp_path):
    class _Deny:
        def query(self, pid, cap):
            return False

    m = _mgr(tmp_path)
    gate.wire(_Deny())
    try:
        with pytest.raises(PermissionError):
            m.add_auth_rule("sshd", "pam_unix.so", "required")
    finally:
        gate.unwire()


def test_wired_allowing_manager_permits_write(tmp_path):
    class _Allow:
        def query(self, pid, cap):
            return cap == CAP_FS_ADMIN

    m = _mgr(tmp_path)
    gate.wire(_Allow())
    try:
        assert m.add_auth_rule("sshd", "pam_unix.so", "required")["success"] is True
    finally:
        gate.unwire()


# ── detector is now blocking and uses INSECURE_PATTERNS ─────────────────────

def test_validate_service_flags_weak_rule_as_issue(tmp_path):
    m = _mgr(tmp_path)
    with open(_service_file(m), "w", encoding="utf-8") as fh:
        fh.write("auth sufficient pam_permit.so\n")
    report = m.validate_service("sshd")
    assert report["valid"] is False
    assert any("pam_permit" in i for i in report["issues"])


def test_insecure_patterns_is_no_longer_dead_code():
    src = open(os.path.join(_PROJ, "etc", "pam_config.py"), encoding="utf-8").read()
    assert "_weak_auth_findings" in src
    # the constant is now consumed by the detector + write guard
    assert src.count("INSECURE_PATTERNS") >= 2
