"""dotfile names must not be able to escape root's home.

The row says ``root/dotfiles.py:232,240-283`` ``register_template``/``ensure``:
"``register_template(name, content)`` stores an arbitrary name and ``ensure()``
writes ``self.home / name`` (L245 ``path = self.home / name``); a name
containing ``/`` or ``..`` escapes the home directory (e.g.
``../../../etc/passwd``).  Requires caller cooperation (public API) so low risk,
but unvalidated."

Drift-recon (session 217): premise **TRUE** -- ``register_template`` was at
**250**, ``ensure`` at **257-296**, and the vulnerable ``self.home / name`` at
**258**.  The row missed a **second** write primitive with the same shape:
``ensure_private_file(name, content)`` at **313** also did ``self.home / name``
on a caller-supplied name, so the traversal was reachable through two public
methods rather than one.

Fix: module-level ``_SAFE_NAME_RE`` (``^[.\\w][\\w.-]*\\Z``) plus
``validate_name()``, applied in ``register_template``, ``set_mode_override``,
``ensure`` and ``ensure_private_file``; and ``_dotfile_path()``, which resolves
the candidate and refuses anything that is not a direct child of the home --
catching the remaining escape the regex cannot see, a **symlink** at
``home/name`` pointing outside, which ``write_text`` would happily follow.

``\\Z`` rather than the row's ``$``: ``$`` also matches before a trailing
newline, so ``"x\\n"`` would have slipped through.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

DOTFILES_PATH = Path(__file__).resolve().parent.parent / "root" / "dotfiles.py"


def _src() -> str:
    return DOTFILES_PATH.read_text(encoding="utf-8")


def _mod():
    root = str(DOTFILES_PATH.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from root import dotfiles

    return dotfiles


def _make_symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - Windows
        pytest.skip(f"cannot create symlinks here: {exc}")
    if not link.is_symlink():  # pragma: no cover - defensive
        pytest.skip("symlink was not created")


# ---------------------------------------------------------------------------
# validate_name -- the unit table
# ---------------------------------------------------------------------------

class TestValidateName:
    @pytest.mark.parametrize(
        "name",
        [".bashrc", ".profile", "authorized_keys", ".config", "x", ".a-b_c.d"],
    )
    def test_accepts_single_components(self, name):
        assert _mod().validate_name(name) == name

    @pytest.mark.parametrize(
        "name",
        [
            "",
            ".",
            "..",
            "a/b",
            "a\\b",
            "../x",
            "a..b",
            "a b",
            "a\n",
            "-x",
            "/abs",
            "sub/dir/file",
        ],
    )
    def test_rejects_escapes_and_junk(self, name):
        with pytest.raises(ValueError):
            _mod().validate_name(name)

    def test_rejects_non_string(self):
        with pytest.raises(ValueError):
            _mod().validate_name(None)


# ---------------------------------------------------------------------------
# Source invariants
# ---------------------------------------------------------------------------

class TestSourceInvariants:
    def test_helper_is_module_level(self):
        assert callable(_mod().validate_name)

    def test_registration_validates(self):
        tree = ast.parse(_src())
        for func_name in ("register_template", "set_mode_override"):
            func = next(
                n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == func_name
            )
            calls = [
                n for n in ast.walk(func)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "validate_name"
            ]
            assert calls, f"{func_name} must call validate_name()"

    def test_both_writers_validate(self):
        tree = ast.parse(_src())
        for func_name in ("ensure", "ensure_private_file"):
            func = next(
                n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == func_name
            )
            names = [
                (n.func.id if isinstance(n.func, ast.Name) else n.func.attr)
                for n in ast.walk(func)
                if isinstance(n, ast.Call)
                and isinstance(n.func, (ast.Name, ast.Attribute))
            ]
            assert "validate_name" in names, f"{func_name} must call validate_name()"
            assert "_dotfile_path" in names, f"{func_name} must use _dotfile_path()"

    def test_home_join_only_happens_in_the_guard(self):
        """``self.home / name`` may appear only inside ``_dotfile_path``."""
        tree = ast.parse(_src())
        offenders = []
        for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(func):
                if (
                    isinstance(node, ast.BinOp)
                    and isinstance(node.op, ast.Div)
                    and isinstance(node.left, ast.Attribute)
                    and node.left.attr == "home"
                    and isinstance(node.right, ast.Name)
                    and node.right.id == "name"
                ):
                    if func.name != "_dotfile_path":
                        offenders.append(f"{func.name}:{node.lineno}")
        assert not offenders, f"unguarded home join in {offenders}"

    def test_containment_check_present(self):
        src = _src()
        assert "resolves outside" in src
        assert "target_resolved.parent != home_resolved" in src


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------

class TestTraversalRefused:
    def test_register_rejects_traversal(self):
        dotfiles = _mod()
        mgr = dotfiles.RootDotfilesManager(home="__nope__")
        for name in ("../evil", "../../etc/passwd", "sub/evil", "a\\b"):
            with pytest.raises(ValueError):
                mgr.register_template(name, "x")

    def test_mode_override_rejects_traversal(self):
        mgr = _mod().RootDotfilesManager(home="__nope__")
        with pytest.raises(ValueError):
            mgr.set_mode_override("../evil", 0o600)

    def test_ensure_rejects_unnamed_traversal(self, tmp_path):
        mgr = _mod().RootDotfilesManager(home=str(tmp_path / "root"))
        with pytest.raises(ValueError):
            mgr.ensure("../../escaped", force=True)
        assert not (tmp_path.parent / "escaped").exists()

    def test_ensure_private_file_rejects_traversal(self, tmp_path):
        """The row missed this second write primitive."""
        mgr = _mod().RootDotfilesManager(home=str(tmp_path / "root"))
        with pytest.raises(ValueError):
            mgr.ensure_private_file("../../escaped", "pwned")
        assert not (tmp_path.parent / "escaped").exists()

    def test_symlink_inside_home_cannot_redirect(self, tmp_path):
        """A symlink passes the regex -- the resolve check must catch it."""
        dotfiles = _mod()
        home = tmp_path / "root"
        home.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("original\n", encoding="utf-8")
        _make_symlink(home / ".bashrc", outside)

        mgr = dotfiles.RootDotfilesManager(home=str(home))
        with pytest.raises(ValueError) as excinfo:
            mgr.ensure(".bashrc", force=True)
        assert "resolves outside" in str(excinfo.value)
        assert outside.read_text(encoding="utf-8") == "original\n"


class TestHappyPath:
    def test_ensure_materialises_a_dotfile(self, tmp_path):
        home = tmp_path / "root"
        home.mkdir()
        mgr = _mod().RootDotfilesManager(home=str(home))
        result = mgr.ensure(".bashrc")
        assert result.created
        assert Path(result.path).is_file()
        assert Path(result.path).parent == tmp_path / "root"

    def test_ensure_all_still_works(self, tmp_path):
        dotfiles = _mod()
        home = tmp_path / "root"
        home.mkdir()
        report = dotfiles.RootDotfilesManager(home=str(home)).ensure_all()
        assert report.issues == []
        names = {r.name for r in report.results}
        assert names == set(dotfiles.DEFAULT_TEMPLATES)
        for name in names:
            assert (home / name).is_file()

    def test_private_file_is_created(self, tmp_path):
        home = tmp_path / "root"
        home.mkdir()
        mgr = _mod().RootDotfilesManager(home=str(home))
        result = mgr.ensure_private_file(".bash_history")
        assert result.created
        assert Path(result.path).name == ".bash_history"
        assert Path(result.path).parent == tmp_path / "root"

    def test_custom_template_roundtrip(self, tmp_path):
        home = tmp_path / "root"
        home.mkdir()
        mgr = _mod().RootDotfilesManager(home=str(home))
        mgr.register_template(".custom", "hello\n")
        result = mgr.ensure(".custom")
        assert Path(result.path).read_text(encoding="utf-8") == "hello\n"
