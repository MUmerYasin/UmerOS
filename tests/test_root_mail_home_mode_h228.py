"""H228 -- root's home must be created 0700, not left at the umask default.

The row says ``root/mail.py:207`` ``RootMailForwarder.ensure`` does
``self.home.mkdir(parents=True, exist_ok=True)`` and only chmods ``.forward``
to 0600, so "if ``ensure()`` runs on a missing home (e.g. before
``RootHomeManager.ensure()``), the ``/root`` parent is left
world-readable/executable".

Drift-recon (session 214): premise **TRUE**; the ``mkdir`` was at **line 220**,
not 207.  ``Path.mkdir()`` with no ``mode=`` creates the directory at
``0o777 & ~umask`` -- 0755 under the usual umask -- so the admin home was
world-readable *and* world-executable.  Two adjacent details surfaced:

* the ``.forward`` chmod block was dead code dressed up as portability
  (``os_chmod = getattr(self.path, "chmod", None)`` is always a bound method,
  so the ``import os`` branch never ran, and the ``import stat`` above it was
  unused);
* ``.forward`` was created under the default umask and chmod-ed afterwards,
  leaving a window in which a file naming an off-host delivery address was
  world-readable.

Fix: ``HOME_MODE = 0o700`` / ``FORWARD_MODE = 0o600`` constants; ``ensure()``
now calls ``_ensure_home()`` (mkdir with ``mode=HOME_MODE`` then an explicit
``chmod``, because ``mkdir``'s mode is filtered through the umask, and an
existing directory is tightened too -- matching ``RootHomeManager.ensure``)
and ``_write_forward()`` (``os.open`` with the final mode, re-chmod-ed for the
pre-existing-file case).
"""

from __future__ import annotations

import ast
import os
import stat
import sys
from pathlib import Path

import pytest

MAIL_PATH = Path(__file__).resolve().parent.parent / "root" / "mail.py"

POSIX = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows has no POSIX permission bits (chmod only toggles read-only)",
)


def _src() -> str:
    return MAIL_PATH.read_text(encoding="utf-8")


def _mod():
    root = str(MAIL_PATH.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from root import mail

    return mail


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


# ---------------------------------------------------------------------------
# Source invariants
# ---------------------------------------------------------------------------

class TestSourceInvariants:
    def test_mode_constants(self):
        mail = _mod()
        assert mail.HOME_MODE == 0o700
        assert mail.FORWARD_MODE == 0o600

    def test_no_unmoded_mkdir(self):
        """Every mkdir in this module must carry an explicit mode."""
        tree = ast.parse(_src())
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name == "mkdir" and not any(kw.arg == "mode" for kw in node.keywords):
                    offenders.append(node.lineno)
        assert not offenders, f"mkdir without mode= at lines {offenders}"

    def test_mkdir_uses_the_home_mode_constant(self):
        """Platform-independent pin: the mode argument is ``HOME_MODE``.

        The behavioural mode checks below are POSIX-only, so this AST check is
        what actually guarantees the 0700 intent on Windows CI too.
        """
        tree = ast.parse(_src())
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name != "mkdir":
                    continue
                for kw in node.keywords:
                    if kw.arg == "mode":
                        found.append(ast.unparse(kw.value))
        assert found == ["HOME_MODE"], f"mkdir mode arguments: {found}"

    def test_forward_is_opened_with_forward_mode(self):
        """``os.open`` must be given ``FORWARD_MODE`` as its third argument."""
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
        assert opens[0][-1] == "FORWARD_MODE", f"os.open args: {opens[0]}"

    def test_helpers_exist(self):
        mail = _mod()
        assert hasattr(mail.RootMailForwarder, "_ensure_home")
        assert hasattr(mail.RootMailForwarder, "_write_forward")

    def test_home_is_chmodded_to_home_mode(self):
        assert "os.chmod(self.home, HOME_MODE)" in _src()

    def test_dead_chmod_dance_is_gone(self):
        src = _src()
        assert "os_chmod = getattr" not in src, "the never-taken branch survived"

    def test_module_imports_os(self):
        tree = ast.parse(_src())
        names = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                names += [a.name for a in node.names]
        assert "os" in names, "os must be imported at module level"


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------

class TestHomeMode:
    def test_missing_home_is_created(self, tmp_path):
        mail = _mod()
        home = tmp_path / "root"
        assert not home.exists()
        mail.RootMailForwarder(home=str(home)).ensure("admin@example.com")
        assert home.is_dir()

    @POSIX
    def test_missing_home_is_created_0700(self, tmp_path):
        """The decisive check: default umask would have produced 0755."""
        mail = _mod()
        home = tmp_path / "root"
        mail.RootMailForwarder(home=str(home)).ensure("admin@example.com")
        assert _mode(home) == 0o700, (
            f"root home created with {oct(_mode(home))}, expected 0o700"
        )

    @POSIX
    def test_existing_world_readable_home_is_tightened(self, tmp_path):
        mail = _mod()
        home = tmp_path / "root"
        home.mkdir()
        home.chmod(0o755)
        mail.RootMailForwarder(home=str(home)).ensure("admin@example.com")
        assert _mode(home) == 0o700

    @POSIX
    def test_forward_file_is_0600(self, tmp_path):
        mail = _mod()
        home = tmp_path / "root"
        fm = mail.RootMailForwarder(home=str(home))
        fm.ensure("admin@example.com", comment="ops")
        assert _mode(fm.path) == 0o600

    @POSIX
    def test_rewrite_keeps_0600(self, tmp_path):
        """A pre-existing 0644 .forward must not stay world-readable."""
        mail = _mod()
        home = tmp_path / "root"
        home.mkdir()
        stale = home / mail.FORWARD_FILENAME
        stale.write_text("old@example.com\n", encoding="utf-8")
        stale.chmod(0o644)
        fm = mail.RootMailForwarder(home=str(home))
        fm.ensure("admin@example.com")
        assert _mode(fm.path) == 0o600

    def test_content_is_written(self, tmp_path):
        mail = _mod()
        home = tmp_path / "root"
        fm = mail.RootMailForwarder(home=str(home))
        report = fm.ensure("admin@example.com", comment="test")
        assert report.exists
        assert report.forwards_to == "admin@example.com"
        assert fm.path.read_text(encoding="utf-8") == "# test\nadmin@example.com\n"

    def test_rewrite_replaces_previous_entry(self, tmp_path):
        mail = _mod()
        home = tmp_path / "root"
        fm = mail.RootMailForwarder(home=str(home))
        fm.ensure("first@example.com")
        fm.ensure("second@example.com")
        assert fm.audit().forwards_to == "second@example.com"
        assert "first@example.com" not in fm.path.read_text(encoding="utf-8")

    def test_empty_address_still_rejected(self, tmp_path):
        mail = _mod()
        fm = mail.RootMailForwarder(home=str(tmp_path / "root"))
        with pytest.raises(ValueError):
            fm.ensure("")

    def test_loop_still_detected(self, tmp_path):
        mail = _mod()
        fm = mail.RootMailForwarder(home=str(tmp_path / "root"))
        fm.ensure("root")
        assert any("loop" in i for i in fm.audit().issues)
