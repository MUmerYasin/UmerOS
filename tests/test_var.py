"""
pytest test suite for UmerOS /var managers.

Covers:
  * normal LIVE behaviour of VarDirectoryManager / SpoolManager / LogManager
    against a temporary root (mirrors the existing ``test_srv.py`` fixture style)
  * SECURITY REGRESSION TESTS for H303 (CWE-22 path traversal). The headline
    case is ``SpoolManager.set_cron_user("../../etc/cron.d/x", jobs)`` which,
    before the fix, let a caller plant a *root-executed* cron job (cron RCE).
    After the fix the attempt must be refused and nothing may be written
    outside the manager-owned root.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from var import (  # noqa: E402
    VarDirectoryManager,
    SpoolManager,
    LogManager,
    PathTraversalError,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def var_root():
    """A throwaway /var root so LIVE managers never touch the real system."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "var"
        root.mkdir()
        yield str(root)


@pytest.fixture
def dir_mgr(var_root):
    return VarDirectoryManager(var_path=var_root)


@pytest.fixture
def spool_mgr(var_root):
    return SpoolManager(var_path=var_root)


@pytest.fixture
def log_mgr(var_root):
    return LogManager(var_path=var_root)


# ── Normal behaviour ─────────────────────────────────────────────────────────

def test_create_local_directory(dir_mgr, var_root):
    assert dir_mgr.create_local_directory("cache") is True
    assert (Path(var_root) / "local" / "cache").is_dir()


def test_acquire_and_release_lock(dir_mgr):
    assert dir_mgr.acquire_lock("myapp") is True
    assert dir_mgr.check_lock("myapp") is True
    assert dir_mgr.release_lock("myapp") is True
    assert dir_mgr.check_lock("myapp") is False


def test_pid_file_roundtrip(dir_mgr):
    assert dir_mgr.create_pid_file("service.pid", pid=4242) is True
    assert dir_mgr.read_pid_file("service.pid") == 4242
    assert dir_mgr.remove_pid_file("service.pid") is True


def test_mailbox_write_read(spool_mgr):
    assert spool_mgr.write_mailbox("alice", "hello") is True
    assert "hello" in spool_mgr.read_mailbox("alice")


def test_set_get_cron_user(spool_mgr):
    assert spool_mgr.set_cron_user("bob", "* * * * * /bin/true") is True
    assert "bin/true" in spool_mgr.get_cron_user("bob")


def test_write_and_read_log(log_mgr):
    assert log_mgr.write_log("app.log", "booted") is True
    assert any("booted" in line for line in log_mgr.read_log("app.log"))


# ── SECURITY: H303 path-traversal / cron-RCE regression ──────────────────────

def test_set_cron_user_cannot_escape_root(spool_mgr, var_root):
    """H303 headline: a traversal username must NOT write outside /var/spool."""
    evil = "../../etc/cron.d/x"
    result = spool_mgr.set_cron_user(evil, "* * * * * /bin/pwn")
    # Operation refused (fail-closed).
    assert result is False
    # Nothing was written outside the managed spool root.
    escaped = Path(var_root).parent / "etc" / "cron.d" / "x"
    assert not escaped.exists(), "CRITICAL: cron RCE path-traversal succeeded!"


def test_set_cron_user_rejects_absolute(spool_mgr):
    assert spool_mgr.set_cron_user("/etc/cron.d/x", "* * * * * /bin/pwn") is False


def test_write_log_cannot_escape_root(log_mgr, var_root):
    """H303: write_log with a traversal filename must not append outside /var/log."""
    result = log_mgr.write_log("../../etc/cron.d/x", "pwn", facility="auth")
    assert result is False
    escaped = Path(var_root).parent / "etc" / "cron.d" / "x"
    assert not escaped.exists(), "CRITICAL: arbitrary append path-traversal succeeded!"


def test_create_local_directory_rejects_traversal(dir_mgr):
    assert dir_mgr.create_local_directory("../escape") is False
    assert dir_mgr.create_local_directory("a/../../b") is False


def test_remove_local_item_rejects_traversal(dir_mgr):
    assert dir_mgr.remove_local_item("../../etc/passwd") is False


def test_read_mailbox_rejects_traversal(spool_mgr):
    assert spool_mgr.read_mailbox("../../etc/shadow") == ""


def test_safe_child_helper_refuses_escapes(var_root):
    """Direct unit test of the guard used by every manager."""
    from var._path_guard import safe_child
    root = (Path(var_root) / "local").resolve()
    # Valid single segment resolves inside root (compare resolved paths to
    # avoid Windows 8.3 short-name vs long-name mismatches).
    cand = safe_child(Path(var_root) / "local", "ok").resolve()
    assert cand == (root / "ok") or root in cand.parents
    # Every escape attempt raises.
    for bad in ("../x", "../../etc", "/abs", "a/../b", "..", ""):
        with pytest.raises(PathTraversalError):
            safe_child(Path(var_root) / "local", bad)
