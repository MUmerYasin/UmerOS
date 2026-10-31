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

"""H239 -- dependency installs must be verifiable and must not buffer.

The row (BLUE) says ``scripts/install_deps.py:6`` ``main`` runs
``pip install -r requirements.txt`` with ``capture_output=True``: "no hash
pinning/integrity check (a compromised or edited ``requirements.txt`` installs
arbitrary packages as the current user)", and the whole install log is buffered
in memory.

Drift-recon (session 225): **both halves true**, but the row's remedy needed
correcting.

* ``requirements.txt`` is a *range* spec **by policy** (H15) — its own header
  says builds must be reproducible via bounded ``>=MIN,<MAX`` ranges, and that
  "for fully deterministic, hash-pinned installs, generate a lock and install
  from it" (``pip-compile --generate-hashes --output-file=requirements.lock``).
  So converting ``requirements.txt`` itself to hashes, as the row suggests,
  would contradict the repository's documented policy.  The right fix is to make
  the installer **honour** that policy: prefer ``requirements.lock`` and enforce
  ``--require-hashes`` when installing from it.
* No ``requirements.lock`` exists yet, so the loose path remains the default —
  but it now says so, and names the command that fixes it.
* ``capture_output=True`` was real.  Output is now inherited (streamed), with
  ``--dry-run`` to show the exact command.
* An adjacent bug the row did not mention: ``"requirements.txt"`` was a
  **relative** path resolved against the process cwd, so running the script from
  anywhere else installed a different file or none.  Paths now resolve against
  the repository root.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
import types
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
if str(PROJ) not in sys.path:
    sys.path.insert(0, str(PROJ))

SCRIPT = PROJ / "scripts" / "install_deps.py"


def _load():
    spec = importlib.util.spec_from_file_location("_h239_install", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def idep():
    return _load()


@pytest.fixture(scope="module")
def src() -> str:
    return SCRIPT.read_text(encoding="utf-8")


@pytest.fixture()
def repo(tmp_path):
    """A stand-in repo root with a range spec."""
    (tmp_path / "requirements.txt").write_text("numpy>=1.26.0\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def locked(repo):
    """The same root, plus a hash-pinned lock."""
    (repo / "requirements.lock").write_text(
        "numpy==1.26.4 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8"
    )
    return repo


# ---------------------------------------------------------------------------
# Which file gets installed
# ---------------------------------------------------------------------------

class TestResolveRequirements:
    def test_prefers_the_lock_when_present(self, idep, locked):
        assert idep.resolve_requirements(root=locked).name == "requirements.lock"

    def test_falls_back_to_the_range_spec(self, idep, repo):
        assert idep.resolve_requirements(root=repo).name == "requirements.txt"

    def test_lock_alone_is_enough(self, idep, tmp_path):
        (tmp_path / "requirements.lock").write_text("x==1 --hash=sha256:aa\n", encoding="utf-8")
        assert idep.resolve_requirements(root=tmp_path).name == "requirements.lock"

    def test_explicit_path_wins_over_the_lock(self, idep, locked):
        chosen = idep.resolve_requirements("requirements.txt", root=locked)
        assert chosen.name == "requirements.txt"

    def test_nothing_to_install_is_a_setup_error(self, idep, tmp_path):
        with pytest.raises(idep.SetupError):
            idep.resolve_requirements(root=tmp_path)

    def test_missing_explicit_path_is_a_setup_error(self, idep, repo):
        with pytest.raises(idep.SetupError):
            idep.resolve_requirements("nope.txt", root=repo)

    def test_relative_paths_resolve_against_the_root_not_the_cwd(self, idep, repo):
        """The old script used a bare ``"requirements.txt"`` — a cwd dependency."""
        resolved = idep.resolve_requirements("requirements.txt", root=repo)
        assert resolved.parent == repo, f"{resolved} escaped {repo}"
        assert resolved.is_file()


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------

class TestHashDetection:
    def test_lock_with_hashes_is_pinned(self, idep, locked):
        assert idep.is_hash_pinned(locked / "requirements.lock") is True

    def test_range_spec_is_not_pinned(self, idep, repo):
        assert idep.is_hash_pinned(repo / "requirements.txt") is False

    def test_unreadable_path_is_a_setup_error(self, idep, tmp_path):
        with pytest.raises(idep.SetupError):
            idep.is_hash_pinned(tmp_path)  # a directory, not a file


class TestPipArgv:
    def test_is_an_argv_list_not_a_shell_string(self, idep, repo):
        argv = idep.build_pip_argv(repo / "requirements.txt", require_hashes=False)
        assert isinstance(argv, list)
        assert all(isinstance(part, str) for part in argv)

    def test_uses_the_running_interpreter(self, idep, repo):
        argv = idep.build_pip_argv(repo / "requirements.txt", require_hashes=False)
        assert argv[0] == sys.executable

    def test_passes_the_file_as_a_separate_argument(self, idep, repo):
        path = repo / "requirements.txt"
        argv = idep.build_pip_argv(path, require_hashes=False)
        assert argv[-2] == "-r"
        assert argv[-1] == str(path), "the path must not be spliced into another argument"

    def test_require_hashes_is_forwarded(self, idep, repo):
        argv = idep.build_pip_argv(repo / "requirements.lock", require_hashes=True)
        assert "--require-hashes" in argv

    def test_require_hashes_is_absent_by_default(self, idep, repo):
        argv = idep.build_pip_argv(repo / "requirements.txt", require_hashes=False)
        assert "--require-hashes" not in argv

    def test_never_blocks_on_a_prompt(self, idep, repo):
        argv = idep.build_pip_argv(repo / "requirements.txt", require_hashes=False)
        assert "--no-input" in argv


# ---------------------------------------------------------------------------
# The row's second half: no buffering
# ---------------------------------------------------------------------------

class TestOutputIsStreamedNotBuffered:
    def test_no_capture_output_keyword_anywhere(self, src):
        """The literal regression: ``capture_output=True`` held the whole log."""
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    assert kw.arg != "capture_output", (
                        f"capture_output reappeared at line {node.lineno}"
                    )

    def test_run_inherits_stdout(self, idep, monkeypatch, repo):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured.update(kwargs)
            return types.SimpleNamespace(returncode=0)

        monkeypatch.setattr(idep, "subprocess", types.SimpleNamespace(run=fake_run))
        idep.main(["-r", "requirements.txt"], stream=None)
        assert captured.get("stdout") is None, "stdout must be inherited, not captured"
        assert "capture_output" not in captured

    def test_dry_run_shows_the_command_and_runs_nothing(self, idep, monkeypatch, repo, capsys):
        called = []
        monkeypatch.setattr(
            idep, "subprocess",
            types.SimpleNamespace(run=lambda *a, **k: called.append(a)),
        )
        assert idep.main(["--dry-run"]) == 0
        assert called == []
        assert "would run:" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Exit codes and warnings
# ---------------------------------------------------------------------------

class TestExitCodes:
    def test_success_is_zero(self, idep, monkeypatch, repo):
        monkeypatch.setattr(
            idep, "subprocess",
            types.SimpleNamespace(run=lambda argv, **kw: types.SimpleNamespace(returncode=0)),
        )
        assert idep.main(["-r", "requirements.txt"]) == 0

    def test_pip_failure_code_is_propagated(self, idep, monkeypatch, repo):
        monkeypatch.setattr(
            idep, "subprocess",
            types.SimpleNamespace(run=lambda argv, **kw: types.SimpleNamespace(returncode=3)),
        )
        assert idep.main(["-r", "requirements.txt"]) == 3

    def test_missing_file_is_a_setup_error(self, idep, capsys):
        assert idep.main(["-r", "definitely-not-here.txt"]) == 2
        assert "error:" in capsys.readouterr().err

    def test_require_hashes_without_a_lock_fails_closed(self, idep, capsys):
        """A hardened CI job must be able to refuse the loose file."""
        assert idep.main(["--require-hashes", "--dry-run"]) == 2
        err = capsys.readouterr().err
        assert "records no hashes" in err
        assert "pip-compile" in err


class TestWarnings:
    def test_unpinned_install_warns_and_names_the_fix(self, idep, capsys):
        idep.main(["--dry-run"])
        err = capsys.readouterr().err
        assert "without hash verification" in err
        assert "requirements.lock" in err

    def test_pinned_install_does_not_warn(self, idep, monkeypatch, locked, capsys):
        monkeypatch.setattr(idep, "PROJ", locked)
        monkeypatch.setattr(
            idep, "subprocess",
            types.SimpleNamespace(run=lambda argv, **kw: types.SimpleNamespace(returncode=0)),
        )
        idep.main(["--dry-run"])
        out, err = capsys.readouterr()
        assert "without hash verification" not in err
        assert "hash-verified" in out


# ---------------------------------------------------------------------------
# Injection safety (the row notes this was already fine -- keep it that way)
# ---------------------------------------------------------------------------

class TestNoShell:
    def test_shell_true_is_never_used(self, src):
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    assert not (
                        kw.arg == "shell"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ), f"shell=True at line {node.lineno}"

    def test_subprocess_is_called_with_a_list(self, idep, monkeypatch, repo):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return types.SimpleNamespace(returncode=0)

        monkeypatch.setattr(idep, "subprocess", types.SimpleNamespace(run=fake_run))
        idep.main(["-r", "requirements.txt"])
        assert isinstance(captured["argv"], list)
