"""
 ``OptPackage`` hardcoded the real ``/etc/opt`` and ``/var/opt``.

``_setup_paths()`` built ``etc_path``/``var_path`` from fixed literals, so the
``opt_root`` override was honoured for the package tree but *not* for its etc/var
trees: a demo or test running against a temp root still resolved its package's
configuration and variable-data directories to the real system paths.  The
higher-level ``OptManager`` even accepted ``etc_opt_root``/``var_opt_root``
arguments — it simply never forwarded them to the package layer.

These tests pin that the roots are now constructor-injectable and threaded all
the way through, that the production defaults are unchanged, and that the
CWE-22 containment around name/provider still fails closed.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.path_guard import PathTraversalError, safe_child  # noqa: E402
from opt.manager import OptManager as HighLevelOptManager  # noqa: E402
from opt.package import OptManager as PackageOptManager  # noqa: E402
from opt.package import OptPackage  # noqa: E402


def _same(actual: Path, expected: Path) -> bool:
    """Compare paths, ignoring Windows 8.3 short-name differences."""
    return Path(str(actual)).resolve() == Path(str(expected)).resolve()


def _eq(actual: Path, expected: Path) -> None:
    assert _same(actual, expected), f"{actual!r} != {expected!r}"


def _make_root(base: Path):
    root = base / "opt"
    etc = base / "etc" / "opt"
    var = base / "var" / "opt"
    return root, etc, var


# ── the override is honoured ─────────────────────────────────────────────

def test_opt_package_uses_overridden_etc_and_var_roots(tmp_path):
    root, etc, var = _make_root(tmp_path)
    pkg = OptPackage(
        "demo",
        "acme",
        opt_root=str(root),
        etc_opt_root=str(etc),
        var_opt_root=str(var),
    )
    assert pkg.etc_opt_root == etc
    assert pkg.var_opt_root == var
    _eq(pkg.etc_path, etc / "acme" / "demo")
    _eq(pkg.var_path, var / "acme" / "demo")
    # and *not* the real system directories
    assert not _same(pkg.etc_path, Path("/etc/opt"))
    assert not _same(pkg.var_path, Path("/var/opt"))


def test_opt_package_without_provider_uses_overridden_roots(tmp_path):
    root, etc, var = _make_root(tmp_path)
    pkg = OptPackage(
        "solo",
        opt_root=str(root),
        etc_opt_root=str(etc),
        var_opt_root=str(var),
    )
    _eq(pkg.etc_path, etc / "solo")
    _eq(pkg.var_path, var / "solo")
    assert pkg.etc_path.name == "solo"
    assert pkg.etc_path.parent == etc


def test_default_roots_are_unchanged(tmp_path):
    """Production behaviour must not move: /etc/opt and /var/opt by default."""
    pkg = OptPackage("prod", opt_root=str(tmp_path / "opt"))
    assert pkg.etc_path == safe_child(Path("/etc/opt"), "prod")
    assert pkg.var_path == safe_child(Path("/var/opt"), "prod")
    assert pkg.etc_opt_root == Path("/etc/opt")
    assert pkg.var_opt_root == Path("/var/opt")


def test_default_roots_with_provider_are_unchanged(tmp_path):
    pkg = OptPackage("prod", "acme", opt_root=str(tmp_path / "opt"))
    assert pkg.etc_path == safe_child(safe_child(Path("/etc/opt"), "acme"), "prod")
    assert pkg.var_path == safe_child(safe_child(Path("/var/opt"), "acme"), "prod")


# ── the overrides reach the package layer ────────────────────────────────

def test_package_manager_forwards_overrides(tmp_path):
    root, etc, var = _make_root(tmp_path)
    mgr = PackageOptManager(str(root), str(etc), str(var))
    assert mgr.etc_opt_root == etc
    assert mgr.var_opt_root == var

    pkg = mgr.install_package("app", "acme")
    _eq(pkg.etc_path, etc / "acme" / "app")
    _eq(pkg.var_path, var / "acme" / "app")

    again = mgr.get_package("app", "acme")
    _eq(again.etc_path, etc / "acme" / "app")
    _eq(again.var_path, var / "acme" / "app")


def test_package_manager_list_packages_uses_overrides(tmp_path):
    """`list_packages` builds an OptPackage per entry - all must be scoped."""
    root, etc, var = _make_root(tmp_path)
    for name, provider in (("a", "p1"), ("b", "p1"), ("c", "")):
        OptPackage(name, provider, str(root), str(etc), str(var))
    mgr = PackageOptManager(str(root), str(etc), str(var))
    listed = mgr.list_packages()
    assert len(listed) == 3
    for entry in listed:
        assert entry["integrity"], entry


def test_high_level_manager_forwards_into_package_layer(tmp_path):
    root, etc, var = _make_root(tmp_path)
    mgr = HighLevelOptManager(str(root), str(etc), str(var))
    # the package sub-manager must carry the overrides, not the defaults
    assert mgr.package_manager.etc_opt_root == etc
    assert mgr.package_manager.var_opt_root == var
    result = mgr.install("hi", "prov", [])
    assert result["success"] is True, result
    pkg = mgr.package_manager.get_package("hi", "prov")
    _eq(pkg.etc_path, etc / "prov" / "hi")
    _eq(pkg.var_path, var / "prov" / "hi")


def test_temp_root_run_touches_no_real_system_dirs(tmp_path):
    """The whole point of H189: a temp-root run must stay inside the temp root."""
    root, etc, var = _make_root(tmp_path)
    real_etc = Path("/etc/opt").resolve() if Path("/etc/opt").exists() else None
    real_var = Path("/var/opt").resolve() if Path("/var/opt").exists() else None
    mgr = HighLevelOptManager(str(root), str(etc), str(var))
    assert mgr.install("iso", "", [])["success"] is True
    pkg = mgr.package_manager.get_package("iso", "")
    _eq(pkg.etc_path, etc / "iso")
    _eq(pkg.var_path, var / "iso")
    if real_etc is not None:
        assert not _same(pkg.etc_path, real_etc)
    if real_var is not None:
        assert not _same(pkg.var_path, real_var)


# ── containment still fails closed ───────────────────────────────────────

@pytest.mark.parametrize("name", ["../../etc", "..", ".", "a/../../b"])
def test_traversal_names_still_raise(tmp_path, name):
    root, etc, var = _make_root(tmp_path)
    with pytest.raises(PathTraversalError):
        OptPackage(name, "", str(root), str(etc), str(var))


def test_traversal_provider_still_raises(tmp_path):
    root, etc, var = _make_root(tmp_path)
    with pytest.raises(PathTraversalError):
        OptPackage("ok", "../../etc", str(root), str(etc), str(var))


def test_etc_root_is_also_contained(tmp_path):
    """A hostile *root* must not let the package escape either."""
    root, etc, var = _make_root(tmp_path)
    with pytest.raises(PathTraversalError):
        OptPackage("ok", "", str(root), str(tmp_path), str(var))
