"""H229 -- the ``/etc/passwd`` backup must not be world-readable.

The row says ``root/passwd.py:136`` ``PasswdManager.write`` does
``bak.write_bytes(self.path.read_bytes())``, which "writes the backup with the
process umask (potentially world-readable), exposing ``/etc/passwd`` contents
(names/shells/GECOS; not hashes, since shadow)".

Drift-recon (session 215): premise **TRUE** -- the two lines were at **141-142**,
not 136, but the defect was exactly as described: ``Path.write_bytes`` creates
the file at ``0o666 & ~umask``, i.e. 0644 under the usual umask, so
``/etc/passwd.bak`` sat world-readable next to a file that is world-readable by
design.

Fix: ``BACKUP_MODE = 0o600`` / ``PASSWD_MODE = 0o644`` constants;
``write()`` delegates to ``_write_backup()``, which opens the copy with
``os.open(..., BACKUP_MODE)`` and re-chmods it (``os.open``'s mode only applies
on creation, so a pre-existing wide ``.bak`` is tightened too).  The backup
stays beside its source -- a restore is then a rename, and the conventional
``/etc/passwd.bak`` path keeps it auditable -- so the file mode, not the
directory, is the control.  The silent ``except OSError: pass`` around the
passwd chmod now logs, because a silently failed chmod on an account database
is worth knowing about.
"""

from __future__ import annotations

import ast
import os
import stat
import sys
from pathlib import Path

import pytest

PASSWD_PATH = Path(__file__).resolve().parent.parent / "root" / "passwd.py"

POSIX = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows has no POSIX permission bits (chmod only toggles read-only)",
)

ROOT_LINE = "root:x:0:0:root:/root:/bin/bash"
NOBODY_LINE = "nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin"


def _src() -> str:
    return PASSWD_PATH.read_text(encoding="utf-8")


def _mod():
    root = str(PASSWD_PATH.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from root import passwd

    return passwd


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _entries():
    passwd = _mod()
    return [
        passwd.PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash"),
        passwd.PasswdEntry("nobody", "x", 65534, 65534, "nobody", "/nonexistent",
                           "/usr/sbin/nologin"),
    ]


# ---------------------------------------------------------------------------
# Source invariants
# ---------------------------------------------------------------------------

class TestSourceInvariants:
    def test_mode_constants(self):
        passwd = _mod()
        assert passwd.BACKUP_MODE == 0o600
        assert passwd.PASSWD_MODE == 0o644

    def test_helper_exists(self):
        assert hasattr(_mod().PasswdManager, "_write_backup")

    def test_old_umask_write_is_gone(self):
        """AST, not a text grep: the docstring legitimately names write_bytes."""
        tree = ast.parse(_src())
        calls = [
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "write_bytes"
        ]
        assert calls == [], f"write_bytes still called at lines {calls}"

    def test_backup_fd_is_binary(self):
        """O_BINARY keeps Windows from rewriting the payload's newlines."""
        assert 'getattr(os, "O_BINARY", 0)' in _src()

    def test_backup_opened_with_backup_mode(self):
        """AST pin: ``os.open`` must be given ``BACKUP_MODE`` (works on Windows)."""
        tree = ast.parse(_src())
        opens = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "open"
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
            ):
                opens.append([ast.unparse(a) for a in node.args])
        assert len(opens) == 1, f"expected one os.open call, found {opens}"
        assert opens[0][-1] == "BACKUP_MODE", f"os.open args: {opens[0]}"

    def test_passwd_mode_is_used_not_hardcoded(self):
        src = _src()
        assert "self.path.chmod(PASSWD_MODE)" in src
        assert "self.path.chmod(0o644)" not in src

    def test_chmod_failure_is_logged(self):
        """A silently failed chmod on the account database is not acceptable."""
        assert "could not chmod %s to %s" in _src()

    def test_capability_gate_still_required(self):
        """H227 must not regress: the write stays gated."""
        assert "gate.require(CAP_SYS_ADMIN)" in _src()


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------

class TestBackupMode:
    def test_backup_is_created(self, tmp_path):
        passwd = _mod()
        path = tmp_path / "passwd"
        path.write_text(ROOT_LINE + "\n", encoding="utf-8")
        mgr = passwd.PasswdManager(path=str(path))
        mgr.write(_entries())
        bak = tmp_path / "passwd.bak"
        assert bak.is_file()
        assert bak.read_text(encoding="utf-8") == ROOT_LINE + "\n"

    @POSIX
    def test_backup_is_0600(self, tmp_path):
        """The decisive check: the old code left this at 0644."""
        passwd = _mod()
        path = tmp_path / "passwd"
        path.write_text(ROOT_LINE + "\n", encoding="utf-8")
        passwd.PasswdManager(path=str(path)).write(_entries())
        bak = tmp_path / "passwd.bak"
        assert _mode(bak) == 0o600, f"backup mode is {oct(_mode(bak))}, expected 0o600"

    @POSIX
    def test_existing_wide_backup_is_tightened(self, tmp_path):
        passwd = _mod()
        path = tmp_path / "passwd"
        path.write_text(ROOT_LINE + "\n", encoding="utf-8")
        stale = tmp_path / "passwd.bak"
        stale.write_text("stale\n", encoding="utf-8")
        stale.chmod(0o644)
        passwd.PasswdManager(path=str(path)).write(_entries())
        assert _mode(stale) == 0o600
        assert stale.read_text(encoding="utf-8") == ROOT_LINE + "\n"

    @POSIX
    def test_passwd_file_ends_at_0644(self, tmp_path):
        passwd = _mod()
        path = tmp_path / "passwd"
        path.write_text(ROOT_LINE + "\n", encoding="utf-8")
        passwd.PasswdManager(path=str(path)).write(_entries())
        assert _mode(path) == 0o644

    def test_no_backup_when_file_missing(self, tmp_path):
        passwd = _mod()
        path = tmp_path / "passwd"
        passwd.PasswdManager(path=str(path)).write(_entries())
        assert path.is_file()
        assert not (tmp_path / "passwd.bak").exists()

    def test_backup_is_byte_identical(self, tmp_path):
        """A backup that rewrites newlines is not a backup.

        ``os.write`` runs in text mode on Windows, which turned a CRLF source
        into ``\\r\\r\\n`` until ``O_BINARY`` was added.
        """
        passwd = _mod()
        path = tmp_path / "passwd"
        original = (ROOT_LINE + "\r\n" + NOBODY_LINE + "\r\n").encode("utf-8")
        path.write_bytes(original)
        passwd.PasswdManager(path=str(path)).write(_entries())
        bak = tmp_path / "passwd.bak"
        assert bak.read_bytes() == original

    def test_backup_can_be_disabled(self, tmp_path):
        passwd = _mod()
        path = tmp_path / "passwd"
        path.write_text(ROOT_LINE + "\n", encoding="utf-8")
        passwd.PasswdManager(path=str(path)).write(_entries(), backup=False)
        assert not (tmp_path / "passwd.bak").exists()
        assert len(passwd.PasswdManager(path=str(path)).read()) == 2

    def test_roundtrip_still_works(self, tmp_path):
        passwd = _mod()
        path = tmp_path / "passwd"
        mgr = passwd.PasswdManager(path=str(path))
        mgr.write(_entries())
        assert [e.name for e in mgr.read()] == ["root", "nobody"]
        assert mgr.find(name="nobody") is not None

    def test_backup_path_is_sibling_with_bak_suffix(self, tmp_path):
        passwd = _mod()
        path = tmp_path / "passwd"
        path.write_text(ROOT_LINE + "\n", encoding="utf-8")
        mgr = passwd.PasswdManager(path=str(path))
        assert mgr._write_backup() == path.with_suffix(".bak")
