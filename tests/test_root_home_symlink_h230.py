""" ``RootHomeManager.ensure`` must not chmod through a symlink.

The row says ``root/home.py:384-393`` ``ensure()`` does
``if not root.exists(): root.mkdir(...)`` then
``os.chmod(path, expected_mode)``; "``os.chmod`` follows the symlink and changes
the *target's* perms.  The CLI ``ensure [path]`` (``__main__.py``) accepts an
arbitrary user-supplied path, so an attacker who can influence the arg could
redirect the chmod at a symlink target."

Drift-recon (session 216): premise **TRUE** -- ``ensure`` was at **389-427**,
the chmod at **424**.  ``Path.exists()`` follows links too, so a symlink to an
existing directory made ``ensure`` skip ``mkdir`` entirely and chmod the
*target*: pointing the path at ``/home/alice`` would silently set ``/home/alice``
to 0700.  A **dangling** symlink was worse than the row says -- ``exists()`` is
``False`` for it, so the code took the ``mkdir`` branch and raised
``FileExistsError``.

Fix: ``ensure()`` refuses a symlinked path with ``ValueError`` before touching
anything (``os.lchmod`` would act on the link itself but does not exist on
Linux, so refusal is the portable answer); parent components may still be links,
since ``/var`` -> ``/private/var`` is normal on macOS.  ``_cmd_ensure`` catches
``ValueError``/``OSError`` and reports "ensure failed: ..." with exit status 1
instead of tracebacking at the operator.
"""

from __future__ import annotations

import ast
import os
import stat
import sys
from pathlib import Path

import pytest

HOME_PATH = Path(__file__).resolve().parent.parent / "root" / "home.py"
MAIN_PATH = Path(__file__).resolve().parent.parent / "root" / "__main__.py"

POSIX = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows has no POSIX permission bits",
)


def _src() -> str:
    return HOME_PATH.read_text(encoding="utf-8")


def _home_mod():
    root = str(HOME_PATH.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from root import home

    return home


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _make_symlink(link: Path, target: Path) -> None:
    """Create ``link -> target`` or skip when the platform forbids it."""
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - Windows
        pytest.skip(f"cannot create symlinks here: {exc}")
    if not link.is_symlink():  # pragma: no cover - defensive
        pytest.skip("symlink was not created")


# ---------------------------------------------------------------------------
# Source invariants
# ---------------------------------------------------------------------------

class TestSourceInvariants:
    def test_symlink_guard_present(self):
        assert "root.is_symlink()" in _src()

    def test_guard_raises_value_error(self):
        tree = ast.parse(_src())
        ensure = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "ensure"
        )
        raises = [
            n for n in ast.walk(ensure)
            if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
            and getattr(n.exc.func, "id", "") == "ValueError"
        ]
        assert raises, "ensure() must raise ValueError for a symlinked path"

    def test_guard_runs_before_chmod(self):
        """The check must precede the chmod, not follow it."""
        src = _src()
        guard = src.index("root.is_symlink()")
        chmod = src.index("os.chmod(path, self.expected_mode)")
        assert guard < chmod

    def test_cli_reports_instead_of_crashing(self):
        src = MAIN_PATH.read_text(encoding="utf-8")
        assert "except (ValueError, OSError) as exc:" in src
        assert "ensure failed:" in src
        assert "return 1" in src


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------

class TestSymlinkRefused:
    @POSIX
    def test_symlink_target_is_not_chmodded(self, tmp_path):
        """The decisive check: the link's target keeps its own mode."""
        home = _home_mod()
        target = tmp_path / "elsewhere"
        target.mkdir()
        target.chmod(0o755)
        link = tmp_path / "root"
        _make_symlink(link, target)

        with pytest.raises(ValueError) as excinfo:
            home.RootHomeManager(default_path=str(link)).ensure(path=str(link))

        assert "symbolic link" in str(excinfo.value)
        assert _mode(target) == 0o755, (
            f"the link target was chmod-ed to {oct(_mode(target))}"
        )

    def test_dangling_symlink_is_refused(self, tmp_path):
        """exists() is False for a dangling link -- it used to hit mkdir."""
        home = _home_mod()
        link = tmp_path / "root"
        _make_symlink(link, tmp_path / "does-not-exist")
        with pytest.raises(ValueError):
            home.RootHomeManager(default_path=str(link)).ensure(path=str(link))
        assert link.is_symlink(), "the link must be left in place"

    def test_guard_prevents_any_chmod(self, tmp_path, monkeypatch):
        """Platform-independent pin: when the path looks like a link, nothing runs.

        Windows cannot always create symlinks without elevation, so the real
        link cases above may skip there.  This drives the guard directly and
        asserts the directory is untouched.
        """
        home = _home_mod()
        target = tmp_path / "root"
        target.mkdir()
        before = target.stat().st_mode

        real_is_symlink = Path.is_symlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda self: True if str(self) == str(target) else real_is_symlink(self),
        )
        with pytest.raises(ValueError) as excinfo:
            home.RootHomeManager(default_path=str(target)).ensure(path=str(target))
        assert "symbolic link" in str(excinfo.value)
        assert target.stat().st_mode == before, "the directory was touched anyway"

    def test_plain_missing_dir_is_created(self, tmp_path):
        home = _home_mod()
        target = tmp_path / "root"
        info = home.RootHomeManager(default_path=str(target)).ensure(path=str(target))
        assert target.is_dir()
        assert info.path == str(target)

    @POSIX
    def test_created_dir_ends_at_0700(self, tmp_path):
        home = _home_mod()
        target = tmp_path / "root"
        home.RootHomeManager(default_path=str(target)).ensure(path=str(target))
        assert _mode(target) == 0o700

    @POSIX
    def test_existing_wide_dir_is_tightened(self, tmp_path):
        home = _home_mod()
        target = tmp_path / "root"
        target.mkdir()
        target.chmod(0o755)
        home.RootHomeManager(default_path=str(target)).ensure(path=str(target))
        assert _mode(target) == 0o700

    def test_idempotent(self, tmp_path):
        home = _home_mod()
        target = tmp_path / "root"
        mgr = home.RootHomeManager(default_path=str(target))
        first = mgr.ensure(path=str(target))
        second = mgr.ensure(path=str(target))
        assert first.path == second.path
        assert target.is_dir()


class TestCli:
    def test_symlinked_path_exits_nonzero_with_message(self, tmp_path, capsys):
        from root.__main__ import main

        target = tmp_path / "elsewhere"
        target.mkdir()
        link = tmp_path / "root"
        _make_symlink(link, target)

        rc = main(["ensure", str(link)])
        captured = capsys.readouterr()
        assert rc == 1
        assert "ensure failed:" in captured.err
        assert "symbolic link" in captured.err
        assert "Traceback" not in captured.err

    def test_bad_parent_exits_nonzero(self, tmp_path, capsys):
        """An unwritable/uncreatable path is a caller error, not a crash."""
        from root.__main__ import main

        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        rc = main(["ensure", str(blocker / "child")])
        captured = capsys.readouterr()
        assert rc == 1
        assert "ensure failed:" in captured.err
