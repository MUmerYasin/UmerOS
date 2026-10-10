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


# ── New: /var/mail (FHS 3.0 top-level mail spool) ────────────────

@pytest.fixture
def mail_mgr(var_root):
    from var import MailManager
    return MailManager(var_path=var_root)


def test_mailbox_append_read(mail_mgr):
    assert mail_mgr.write_mailbox("alice", "hello") is True
    assert mail_mgr.write_mailbox("alice", "second message") is True
    content = mail_mgr.read_mailbox("alice")
    assert "hello" in content and "second message" in content


def test_mailbox_stats(mail_mgr):
    mail_mgr.write_mailbox("bob", "x" * 10)
    stats = mail_mgr.mailbox_stats("bob")
    assert stats.exists is True
    assert stats.size == 11  # "x"*10 + newline
    assert stats.lines == 1


def test_mailbox_search(mail_mgr):
    mail_mgr.write_mailbox("carol", "lunch at noon")
    mail_mgr.write_mailbox("carol", "dinner at eight")
    hits = mail_mgr.search_mailbox("carol", "NOON")
    assert len(hits) == 1 and "lunch" in hits[0]


def test_mailbox_clear_and_delete(mail_mgr):
    mail_mgr.write_mailbox("dave", "gone soon")
    assert mail_mgr.clear_mailbox("dave") is True
    assert mail_mgr.read_mailbox("dave") == ""
    assert mail_mgr.delete_mailbox("dave") is True
    assert mail_mgr.mailbox_stats("dave").exists is False


def test_mailbox_rejects_traversal(mail_mgr, var_root):
    assert mail_mgr.write_mailbox("../../etc/shadow", "x") is False
    assert mail_mgr.read_mailbox("../../etc/shadow") == ""
    escaped = Path(var_root).parent / "etc" / "shadow"
    assert not escaped.exists(), "mail traversal escaped /var/mail!"


# ── New: /var/cache (FHS 3.0 application caches) ─────────────────

@pytest.fixture
def cache_mgr(var_root):
    from var import CacheManager
    return CacheManager(var_path=var_root, max_bytes=1024 * 1024)


def test_cache_put_get_text(cache_mgr):
    assert cache_mgr.put("app/config", "value") is True
    assert cache_mgr.get("app/config") == "value"


def test_cache_put_get_bytes(cache_mgr):
    payload = b"\x00\x01\x02\xff"
    assert cache_mgr.put("app/blob", payload) is True
    assert cache_mgr.get("app/blob") == payload


def test_cache_nested_key(cache_mgr):
    assert cache_mgr.put("app/thumbnails/foo", "thumb") is True
    assert cache_mgr.get("app/thumbnails/foo") == "thumb"
    assert "app/thumbnails/foo" in cache_mgr.keys()


def test_cache_ttl_expiry(cache_mgr):
    assert cache_mgr.put("short-lived", "x", ttl=0) is True
    assert cache_mgr.get("short-lived") is None


def test_cache_cleanup_expired(cache_mgr):
    cache_mgr.put("gone", "x", ttl=0)
    assert cache_mgr.cleanup_expired() >= 1
    assert cache_mgr.get("gone") is None


def test_cache_eviction_keeps_newest(cache_mgr):
    assert cache_mgr.put("a", "x" * 100) is True
    size_a = cache_mgr.stats()["total_bytes"]
    # Budget that fits exactly one entry -> the oldest is evicted.
    cache_mgr.max_bytes = size_a + 1
    assert cache_mgr.put("b", "y" * 100) is True
    assert cache_mgr.get("a") is None
    assert cache_mgr.get("b") == "y" * 100


def test_cache_miss_and_stats(cache_mgr):
    assert cache_mgr.get("missing") is None
    stats = cache_mgr.stats()
    assert stats["misses"] >= 1
    assert stats["entries"] == 0


def test_cache_delete_and_clear(cache_mgr):
    cache_mgr.put("k1", "v1")
    cache_mgr.put("k2", "v2")
    assert cache_mgr.delete("k1") is True
    assert cache_mgr.get("k1") is None
    assert cache_mgr.clear() >= 1
    assert cache_mgr.stats()["entries"] == 0


def test_cache_rejects_traversal(cache_mgr, var_root):
    assert cache_mgr.put("../../etc/cron.d/x", "pwn") is False
    escaped = Path(var_root).parent / "etc" / "cron.d" / "x"
    assert not escaped.exists(), "cache traversal escaped /var/cache!"


# ── LogManager improvements ────────────────────────────────────────

def test_write_log_persists_level(log_mgr):
    assert log_mgr.write_log("app.log", "something broke",
                             level="err") is True
    lines = log_mgr.read_log("app.log")
    entry = log_mgr.parse_log_entry(lines[-1])
    assert entry is not None
    assert entry.severity == "err"
    assert entry.message == "something broke"


def test_compress_old_logs_keeps_active_log(log_mgr):
    assert log_mgr.write_log("app.log", "active line") is True
    assert log_mgr.compress_old_logs() == []
    # The active log must still be readable (not compressed away).
    assert any("active line" in line
               for line in log_mgr.read_log("app.log"))


def test_rotate_then_compress_old_logs(log_mgr):
    assert log_mgr.write_log("app.log", "rotate me") is True
    assert log_mgr.rotate_log("app.log", max_size=0) is True
    compressed = log_mgr.compress_old_logs()
    # Exactly the rotated copy is compressed...
    assert len(compressed) == 1
    gz = Path(log_mgr.log_path) / (compressed[0] + ".gz")
    assert gz.exists()
    # ...and the active log recreated by rotate() survives.
    assert (Path(log_mgr.log_path) / "app.log").exists()


def test_get_log_stats_counts_all_lines(log_mgr):
    for i in range(120):
        assert log_mgr.write_log("big.log", f"line {i}") is True
    stats = log_mgr.get_log_stats("big.log")
    assert stats["total_lines"] == 120


def test_safe_join_from_var_package(var_root):
    from var import safe_join
    root = (Path(var_root) / "cache").resolve()
    nested = safe_join(Path(var_root) / "cache", "app", "sub", "file.txt")
    assert nested == (root / "app" / "sub" / "file.txt") \
        or root in nested.parents
    for bad in ("../x", "a/../../b"):
        with pytest.raises(PathTraversalError):
            safe_join(Path(var_root) / "cache", bad)
    # A leading separator is tolerated (stays contained), not an escape.
    contained = safe_join(Path(var_root) / "cache", "/abs")
    assert root in contained.parents or contained == root
