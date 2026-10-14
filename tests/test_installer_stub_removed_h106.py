"""tests — `installer/install.py` dead-stub removal (drift confirmation).

The standard's H106 remedy ("Delete `install.py`; keep one `installer.py`
entry point") was ALREADY applied in a prior fix (H98/H106). This suite adds
H106-tagged traceability and covers angles the existing
`test_installer_security.py::TestH98Reexport` does not:

  * no stale `install.pyc` lingering in `installer/__pycache__/`
  * no residual `installer.install` reference anywhere in the source tree
  * the package's re-export loop targets the `installer` module, not `install`
  * exactly one `class UmerInstaller` exists in the whole tree
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INST = ROOT / "installer"


def test_install_py_absent():
    assert not (INST / "install.py").exists()


def test_no_install_py_anywhere_in_tree():
    hits = [
        p for p in ROOT.rglob("install.py")
        if "__pycache__" not in p.parts
    ]
    assert hits == []


def test_no_stale_install_pyc():
    pyc = INST / "__pycache__"
    if pyc.is_dir():
        stale = [p.name for p in pyc.iterdir() if p.name.startswith("install.")]
        assert stale == [], f"stale bytecode for removed install.py: {stale}"


def test_installer_install_module_not_importable():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("installer.install")


def test_reexport_targets_installer_module_not_install():
    """The __init__ re-export tuple must name 'installer', never 'install'."""
    tree = ast.parse((INST / "__init__.py").read_text(encoding="utf-8"))
    tuples = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and node.elts:
            first = node.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                tuples.append(first.value)
    # the module name fed to _try_import must be 'installer'
    assert "installer" in tuples
    assert "install" not in tuples


def test_exactly_one_umerinstaller_class():
    defs = []
    for p in ROOT.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "UmerInstaller":
                defs.append(str(p.relative_to(ROOT)).replace("\\", "/"))
    assert defs == ["installer/installer.py"], defs


def test_package_reexports_real_installer():
    pkg = importlib.import_module("installer")
    real = importlib.import_module("installer.installer")
    assert pkg.UmerInstaller is real.UmerInstaller
