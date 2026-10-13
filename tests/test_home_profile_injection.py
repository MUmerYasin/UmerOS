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
Regression tests for H86 (home/user_profile.py shell injection).

H86 was "shell-injection via unsanitized profile values": ``set_env`` stored an
arbitrary ``value`` and ``_generate_profile`` emitted ``export {key}="{value}"``,
while ``add_alias`` stored an arbitrary ``command`` and ``_generate_bashrc``
emitted ``alias {name}='{cmd}'``.  A value containing ``"``, ``$(...)``,
backticks or a newline broke out of the quotes and executed when the login shell
*sourced* ``.profile`` / ``.bashrc`` (e.g. ``set_env(u, "X", '"; rm -rf ~ #')``).

The fix:
  * validates env keys / alias names against ``^[A-Za-z_][A-Za-z0-9_]*$``
    (raising ``ValueError`` at the entry points, skipping + warning at generation),
  * emits every value / command as a POSIX **single-quoted** shell literal via
    ``_shell_quote`` (the ``'\\''`` idiom), so nothing can break out.
"""

import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)


def _load(mod_name, relpath):
    spec = importlib.util.spec_from_file_location(mod_name, os.path.join(_PROJ, relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


up_mod = _load("umeros_h86_user_profile", "home/user_profile.py")
_shell_quote = up_mod._shell_quote

EVIL_KEY = ["X; rm -rf ~", "1BAD", "A-B", "A B", "", "X\nY", "A$B", "a=b"]
EVIL_ALIAS = ["foo; rm -rf ~", "1bad", "a-b", "", "foo bar", "f'o"]


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture
def mgr(home):
    m = up_mod.UserProfileManager(home_path=str(home))
    m.create_profile("alice")
    return m


# --------------------------------------------------------------------------- #
# _shell_quote unit semantics                                                  #
# --------------------------------------------------------------------------- #
def test_shell_quote_wraps_in_single_quotes():
    assert _shell_quote("hello") == "'hello'"
    assert _shell_quote("") == "''"


def test_shell_quote_escapes_embedded_single_quote():
    # '  ->  '\''
    assert _shell_quote("it's") == "'it'\\''s'"
    assert _shell_quote("''") == "''\\'''\\'''"


def test_shell_quote_neutralizes_metacharacters():
    payload = '"; rm -rf ~ #'
    q = _shell_quote(payload)
    assert q == "'\"; rm -rf ~ #'"
    # the dangerous double-quote is now inside a single-quoted literal
    assert q.startswith("'") and q.endswith("'")


# --------------------------------------------------------------------------- #
# Identifier validation (entry points fail closed)                             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", EVIL_KEY)
def test_set_env_rejects_bad_key(mgr, bad):
    with pytest.raises(ValueError):
        mgr.set_env("alice", bad, "v")


@pytest.mark.parametrize("bad", EVIL_ALIAS)
def test_add_alias_rejects_bad_name(mgr, bad):
    with pytest.raises(ValueError):
        mgr.add_alias("alice", bad, "echo hi")


def test_valid_keys_still_accepted(mgr):
    assert mgr.set_env("alice", "FOO_BAR", "1") is True
    assert mgr.set_env("alice", "_x9", "1") is True
    assert mgr.add_alias("alice", "ll", "ls -la") is True


# --------------------------------------------------------------------------- #
# Generated files are single-quoted / inert                                    #
# --------------------------------------------------------------------------- #
def test_generated_profile_single_quotes_values(mgr, home):
    mgr.set_env("alice", "X", '"; rm -rf ~ #')
    text = (home / "alice" / ".profile").read_text(encoding="utf-8")
    assert "export X='\"; rm -rf ~ #'" in text
    # the raw, unquoted form must NOT appear
    assert 'export X="' not in text


def test_generated_bashrc_single_quotes_commands(mgr, home):
    mgr.add_alias("alice", "foo", "echo 'x'; touch /tmp/nope")
    text = (home / "alice" / ".bashrc").read_text(encoding="utf-8")
    assert "alias foo='echo '\\''x'\\''; touch /tmp/nope'" in text
    assert "alias foo=\"" not in text


def test_invalid_stored_key_is_skipped_not_emitted(mgr, home):
    # simulate a caller that mutated the public dataclass field directly
    prof = mgr.get_profile("alice")
    prof.env_vars["BAD; KEY"] = "x"
    mgr._write_profile_files(prof)
    text = (home / "alice" / ".profile").read_text(encoding="utf-8")
    assert "BAD; KEY" not in text
    assert "export BAD" not in text


def test_evil_shell_value_is_quoted(mgr, home):
    mgr.set_env("alice", "SHELL", '"; touch PWNED; #')
    text = (home / "alice" / ".profile").read_text(encoding="utf-8")
    assert "export SHELL='\"; touch PWNED; #'" in text


# --------------------------------------------------------------------------- #
# End-to-end: sourcing the generated file must NOT execute the payload         #
# --------------------------------------------------------------------------- #
def test_sourcing_generated_profile_is_inert(tmp_path):
    sh = shutil.which("sh")
    if not sh:
        pytest.skip("no POSIX sh available")
    home = tmp_path / "home"
    home.mkdir()
    m = up_mod.UserProfileManager(home_path=str(home))
    m.create_profile("alice")

    sentinel = tmp_path / "PWNED"
    s = str(sentinel).replace("\\", "/")
    payload = f'"; touch {s}; echo "'
    m.set_env("alice", "X", payload)

    profile = home / "alice" / ".profile"
    profile_posix = str(profile).replace("\\", "/")
    script = f"set -a; . '{profile_posix}'; printf '%s' \"$X\""
    out = subprocess.run([sh, "-c", script], capture_output=True, text=True)

    assert not sentinel.exists(), "shell injection executed the payload!"
    assert out.stdout == payload, f"value was mangled: {out.stdout!r}"


def test_sourcing_generated_alias_line_is_inert(tmp_path):
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("no bash available")
    home = tmp_path / "home"
    home.mkdir()
    m = up_mod.UserProfileManager(home_path=str(home))
    m.create_profile("alice")

    sentinel = tmp_path / "PWNED2"
    s = str(sentinel).replace("\\", "/")
    m.add_alias("alice", "foo", f"touch {s}; echo hi")

    bashrc = (home / "alice" / ".bashrc").read_text(encoding="utf-8")
    alias_line = next(l for l in bashrc.splitlines() if l.startswith("alias foo="))
    out = subprocess.run([bash, "-c", alias_line + "; alias foo"],
                         capture_output=True, text=True)

    assert not sentinel.exists(), "alias injection executed the payload!"
    assert "touch" in out.stdout  # the command text is data, not executed
