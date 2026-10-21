"""
shell injection in the generated /opt PATH/profile snippets.

Before the fix, a discovered ``bin_path`` was interpolated unescaped into
``export PATH="<path>:$PATH"`` written to ``/etc/profile.d/opt-paths.sh``
and appended to ``~/.bashrc`` — both of which every login shell sources.  A
package directory name containing a quote broke out of the string literal
and ran arbitrary commands for every user of the machine.

The tests below pin the two guards that replaced it:

1. provider/package directory names that are not plain filesystem names are
   dropped from discovery (and logged) instead of being interpolated; and
2. every surviving path is ``shlex.quote``-d individually, so a name with a
   space, quote, ``$`` or backtick can never break out of the snippet.

The final test actually executes the generated snippet in a real shell and
asserts the payload never runs.
"""
from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from opt.env import (  # noqa: E402
    OptEnvManager,
    _drop_shell_unsafe,
    _shell_export,
)
from opt.integration import OptPathManager  # noqa: E402

# A name that is creatable on both POSIX and Windows (no path separator),
# yet is lethal if interpolated unquoted into a double-quoted shell string.
EVIL_NAME = "evil$(touch pwned_marker)"
# Spaces are legal in a package name: this one must be *kept* and quoted.
SPACED_NAME = "my pkg"

HAS_BASH = shutil.which("bash") is not None or Path(r"C:\Program Files\Git\bin\bash.exe").exists()


def _make_opt_root(base: Path) -> Path:
    """Create ``<base>/opt`` with a spaced and a hostile package."""
    root = base / "opt"
    for name in (SPACED_NAME, EVIL_NAME):
        pkg = root / name / "bin"
        pkg.mkdir(parents=True)
        (pkg / "tool").write_text("#!", encoding="utf-8")
    # a well-formed provider/package layout
    prov = root / "mozilla" / "thunderbird" / "bin"
    prov.mkdir(parents=True)
    (prov / "thunderbird").write_text("#!", encoding="utf-8")
    return root


# ── guard 1: hostile names never reach the snippet ───────────────────────

def test_hostile_package_name_is_dropped_from_discovery(tmp_path):
    root = _make_opt_root(tmp_path)
    mgr = OptEnvManager(opt_root=root)
    bins = mgr.discover_bin_dirs()
    assert str(root / SPACED_NAME / "bin") in bins
    assert str(root / "mozilla" / "thunderbird" / "bin") in bins
    assert not any("pwned_marker" in b for b in bins)


def test_drop_is_scoped_below_the_root(tmp_path):
    """The (administrator-chosen) root is not itself name-validated."""
    root = tmp_path / "opt"
    (root / "firefox" / "bin").mkdir(parents=True)
    (root / "firefox" / "bin" / "f").write_text("#!", encoding="utf-8")
    assert _drop_shell_unsafe([str(root / "firefox" / "bin")], root) == [
        str(root / "firefox" / "bin")
    ]
    # the same absolute path, validated against a root it is not below
    assert _drop_shell_unsafe([str(root / "firefox" / "bin")], "/somewhere/else") == []


def test_drop_only_affects_hostile_names(tmp_path):
    root = tmp_path / "opt"
    for name in ("fine", "has space", "dot.ted", "plus+minus-", "at@sign", "pct%", "eq=al"):
        d = root / name / "bin"
        d.mkdir(parents=True)
    assert len(OptEnvManager(opt_root=root).discover_bin_dirs()) == 7


# ── guard 2: everything that survives is quoted ──────────────────────────

@pytest.mark.parametrize("variable", ["PATH", "MANPATH", "LD_LIBRARY_PATH"])
def test_exports_are_shell_safe(tmp_path, variable):
    root = _make_opt_root(tmp_path)
    mgr = OptEnvManager(opt_root=root)
    dirs = mgr.discover_bin_dirs()
    assert dirs, "expected at least one discovered directory"
    line = _shell_export(dirs, variable)
    assert line.startswith(f"export {variable}=")
    assert "$(" not in line and "`" not in line and '"' not in line
    # the whole export must parse as exactly one shell word per assignment
    words = shlex.split(line)
    assert len(words) == 2, f"{line!r} is not a single shell word"
    assert words[1].startswith(f"{variable}=")


def test_spaced_directory_is_quoted_not_dropped(tmp_path):
    root = _make_opt_root(tmp_path)
    export = OptEnvManager(opt_root=root).generate_path_export()
    wanted = str(root / SPACED_NAME / "bin").replace("\\", "/")
    assert "'" + wanted + "'" in export
    assert "pwned_marker" not in export


def test_profile_d_file_is_shell_safe(tmp_path):
    root = _make_opt_root(tmp_path)
    mgr = OptEnvManager(opt_root=root)
    profile_d = tmp_path / "profile.d"
    assert mgr.write_profile_d(profile_d) is True
    script = (profile_d / "opt-paths.sh").read_text(encoding="utf-8")
    assert "firefox" not in script or True
    for line in script.splitlines():
        if line.startswith("export "):
            assert "$(" not in line and "`" not in line
            assert len(shlex.split(line)) == 2
    assert "pwned_marker" not in script


@pytest.mark.skipif(not HAS_BASH, reason="no bash available")
@pytest.mark.parametrize("which", ["env", "integration"])
def test_generated_snippet_does_not_execute_payload(tmp_path, which):
    """End-to-end: run the real snippet in a real shell, assert nothing fires."""
    root = _make_opt_root(tmp_path)
    if which == "env":
        snippet = OptEnvManager(opt_root=root).generate_all_exports()
    else:
        snippet = OptPathManager(str(root), profile_path=str(tmp_path / "p.sh")).generate_profile_script()
    assert "pwned_marker" not in snippet

    script = tmp_path / "opt-paths.sh"
    script.write_text(snippet, encoding="utf-8")
    bash = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"
    subprocess.run(
        [bash, str(script)], cwd=str(tmp_path), capture_output=True, timeout=60, check=False
    )
    assert not (tmp_path / "pwned_marker").exists(), "shell injection fired"


# ── opt/integration.py specifics ────────────────────────────────────────

def test_integration_script_is_quoted_and_interpolated(tmp_path):
    root = _make_opt_root(tmp_path)
    mgr = OptPathManager(str(root), profile_path=str(tmp_path / "p.sh"))
    script = mgr.generate_profile_script()
    assert "pwned_marker" not in script
    assert "$(" not in script and "`" not in script
    # the two OPT_ROOT lines used to be missing their `f` prefix
    assert "{self.opt_root}" not in script
    assert f"export OPT_ROOT={shlex.quote(str(root))}" in script
    wanted = str(root / SPACED_NAME / "bin").replace("\\", "/")
    assert shlex.quote(wanted) in script
    for line in script.splitlines():
        s = line.strip()
        if s.startswith("export PATH=") or s.startswith("export OPT_"):
            assert "$(" not in s and "`" not in s
            assert len(shlex.split(s)) == 2


def test_integration_discovers_flat_layout(tmp_path):
    """`if item.is_dir():` was always true, so /opt/<pkg>/bin was never found."""
    root = tmp_path / "opt"
    flat = root / "flatpkg" / "bin"
    flat.mkdir(parents=True)
    nested = root / "prov" / "nestedpkg" / "bin"
    nested.mkdir(parents=True)
    mgr = OptPathManager(str(root), profile_path=str(tmp_path / "p.sh"))
    paths = mgr.get_package_paths()
    assert set(paths) == {"flatpkg", "nestedpkg"}


def test_install_refuses_default_dotfile_without_opt_in(tmp_path):
    """Mutating ~/.bashrc must be an explicit, deliberate act (H188)."""
    mgr = OptPathManager(str(_make_opt_root(tmp_path)))
    with pytest.raises(PermissionError, match="login file"):
        mgr.install_profile_integration()


def test_install_with_explicit_profile_writes_safely(tmp_path):
    root = _make_opt_root(tmp_path)
    profile = tmp_path / "bashrc"
    mgr = OptPathManager(str(root), profile_path=str(profile))
    assert mgr.install_profile_integration() is True
    assert mgr._is_installed() is True
    body = profile.read_text(encoding="utf-8")
    assert "pwned_marker" not in body and "$(" not in body
    assert mgr.uninstall_profile_integration() is True
    assert mgr._is_installed() is False


def test_install_with_home_profile_opt_in(tmp_path):
    root = _make_opt_root(tmp_path)
    profile = tmp_path / "bashrc"
    mgr = OptPathManager(str(root), profile_path=str(profile), allow_home_profile=True)
    assert mgr.install_profile_integration() is True
    assert "UmerOS /opt PATH integration" in profile.read_text(encoding="utf-8")


def test_integration_logs_instead_of_printing(tmp_path):
    """The two profile-mutation error paths must not print to stdout."""
    import inspect

    import opt.integration as mod

    assert isinstance(mod.log, logging.Logger)
    for fn in (mod.OptPathManager.install_profile_integration,
               mod.OptPathManager.uninstall_profile_integration,
               mod.OptServiceManager.start_service,
               mod.OptServiceManager.stop_service):
        assert "print(" not in inspect.getsource(fn)


def test_opt_env_selftest(tmp_path, capsys):
    from opt import env as env_mod

    assert env_mod._selftest() is True
    out = capsys.readouterr().out
    assert "shell-unsafe package names are dropped" in out
    assert "shlex.quote-d" in out
