"""
pytest test suite for UmerOS /opt managers.

Covers:
  * normal behaviour of VarOptManager / OptConfig / OptManager / OptPackage
    against temporary roots (LIVE managers never touch the real /opt, /etc/opt,
    /var/opt).
  * SECURITY REGRESSION TESTS for H185/H186 (CWE-22 path traversal). The
    headline cases are:
      - VarOptManager.write_file("../../etc/passwd", ...) must NOT write
        outside /var/opt.
      - OptManager.remove("../../etc") must NOT rmtree anything outside the
        managed roots.
      - OptConfig.install_config with a traversal package_name must be refused.
      - OptPackage constructed/removed with a traversal name must be refused.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from core.path_guard import PathTraversalError  # noqa: E402
from opt.var import VarOptManager  # noqa: E402
from opt.config import OptConfig  # noqa: E402
from opt.manager import OptManager  # noqa: E402
from opt.package import OptPackage, OptManager as PkgOptManager  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def opt_root():
    """A throwaway /opt tree so LIVE managers never touch the real system."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "opt"
        root.mkdir()
        yield root


@pytest.fixture
def var_opt_root():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "var_opt"
        root.mkdir()
        yield root


@pytest.fixture
def etc_opt_root():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "etc_opt"
        root.mkdir()
        yield root


@pytest.fixture
def var_mgr(var_opt_root):
    return VarOptManager(var_opt_root=var_opt_root)


@pytest.fixture
def config_mgr(etc_opt_root, opt_root):
    return OptConfig(opt_root=opt_root, etc_opt_root=etc_opt_root)


# ── Normal behaviour ───────────────────────────────────────────────────────

def test_var_write_read(var_mgr):
    assert var_mgr.write_file("firefox", "mozilla", "cache.dat", b"cachedata") is True
    assert var_mgr.read_file("firefox", "mozilla", "cache.dat") == b"cachedata"


def test_var_nested_filename(var_mgr, var_opt_root):
    # Nested (legal) filenames must still work after the fix.
    assert var_mgr.write_file("pkg", "", "sub/dir/file.txt", b"nested") is True
    assert (Path(var_opt_root) / "pkg" / "sub" / "dir" / "file.txt").read_bytes() == b"nested"
    assert var_mgr.read_file("pkg", "", "sub/dir/file.txt") == b"nested"


def test_var_remove_package_dir(var_mgr, var_opt_root):
    var_mgr.ensure_package_dir("vim")
    assert var_mgr.remove_package_dir("vim") is True
    assert not (Path(var_opt_root) / "vim").exists()


def test_config_install_get(var_mgr, config_mgr):
    p = config_mgr.install_config("app", {"port": 8080})
    assert p.exists()
    assert config_mgr.get_config("app") == {"port": 8080}


def test_manager_install_remove(opt_root, etc_opt_root, var_opt_root):
    mgr = OptManager(
        opt_root=str(opt_root),
        etc_opt_root=str(etc_opt_root),
        var_opt_root=str(var_opt_root),
    )
    res = mgr.install("demo", version="1.0.0", config={"x": 1})
    assert res["success"] is True
    rem = mgr.remove("demo")
    assert rem["success"] is True
    assert rem["paths_removed"]


def test_package_install_remove(opt_root):
    mgr = PkgOptManager(str(opt_root))
    pkg = mgr.install_package("editor")
    assert pkg.base_path.is_dir()
    assert mgr.remove_package("editor") is True


# ── SECURITY: H185 / H186 path-traversal regression ────────────────────────

def test_var_write_file_cannot_escape_root(var_mgr, var_opt_root):
    """H185: a traversal filename must NOT write outside /var/opt."""
    result = var_mgr.write_file("pkg", "", "../../escape.txt", b"pwn")
    assert result is False
    escaped = Path(var_opt_root).parent / "escape.txt"
    assert not escaped.exists(), "CRITICAL: /var/opt write path-traversal succeeded!"


def test_var_read_file_rejects_traversal(var_mgr):
    assert var_mgr.read_file("pkg", "", "../../etc/shadow") is None


def test_var_remove_package_dir_rejects_traversal(var_mgr):
    assert var_mgr.remove_package_dir("../../etc") is False


def test_config_install_refuses_traversal(config_mgr):
    """H185: install_config with a traversal package_name must be refused."""
    with pytest.raises(ValueError):
        config_mgr.install_config("../../etc/passwd", {"x": 1})


def test_config_remove_refuses_traversal(config_mgr):
    assert config_mgr.remove_config("../../etc") is False


def test_manager_remove_refuses_traversal(opt_root, etc_opt_root, var_opt_root):
    """H186: OptManager.remove with a traversal name must rmtree nothing."""
    mgr = OptManager(
        opt_root=str(opt_root),
        etc_opt_root=str(etc_opt_root),
        var_opt_root=str(var_opt_root),
    )
    res = mgr.remove("../../escape")
    # Nothing outside the managed roots was deleted.
    assert res["paths_removed"] == []
    assert any("Refusing" in e for e in res["errors"])
    assert not (Path(opt_root).parent / "escape").exists()


def test_package_construction_refuses_traversal(opt_root):
    """H186: OptPackage built with a traversal name fails closed."""
    with pytest.raises(PathTraversalError):
        OptPackage("../../etc", "", str(opt_root))


def test_package_remove_refuses_traversal(opt_root):
    mgr = PkgOptManager(str(opt_root))
    assert mgr.remove_package("../../etc") is False
