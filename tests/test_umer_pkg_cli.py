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

"""``umer-pkg`` console entry point regression tests.

``setup.py`` registers ``umer-pkg=packages.umer_pkg:main``.  No ``main`` existed,
so the advertised console script raised ``AttributeError`` at import and could
never run — installing UmerOS produced a broken command.  These tests pin the
entry point down: it must exist, must be the name ``setup.py`` registers, must
return POSIX exit codes, and must drive a real signed build / verify / install /
list / remove cycle.
"""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.capability_gate import CapabilityGate, gate  # noqa: E402
from packages import umer_pkg  # noqa: E402
from packages.trusted_keys import (  # noqa: E402
    TRUSTED_PUBLIC_KEYS,
    pin_trusted_key,
    unpin_trusted_key,
)

TEST_KEY_ID = "umer-test-dev"


@pytest.fixture(autouse=True)
def _permissive_gate():
    """Isolate these tests from whatever posture the global gate is in."""
    saved_manager = gate._manager
    saved_strict = gate.strict
    gate.unwire()
    gate.set_strict(False)
    try:
        yield
    finally:
        gate._manager = saved_manager
        gate.set_strict(saved_strict)


@pytest.fixture
def env(tmp_path):
    """Isolated install/registry/cache roots plus a pinned throwaway signer.

    The trust store is process-global and ``tests/test_packages.py`` pins the
    same ``umer-test-dev`` id at import time, so the previous entry (if any) is
    restored rather than removed — unpinning it here would break that module.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    key_file = tmp_path / "signing.key"
    key_file.write_bytes(key.private_bytes_raw())

    had_previous = TEST_KEY_ID in TRUSTED_PUBLIC_KEYS
    previous = TRUSTED_PUBLIC_KEYS.get(TEST_KEY_ID)
    pin_trusted_key(TEST_KEY_ID, key.public_key())
    try:
        yield {
            "key_file": key_file,
            "dirs": [
                "--install-dir", str(tmp_path / "pkgs"),
                "--registry-dir", str(tmp_path / "reg"),
                "--cache-dir", str(tmp_path / "cache"),
            ],
            "root": tmp_path,
        }
    finally:
        if had_previous:
            TRUSTED_PUBLIC_KEYS[TEST_KEY_ID] = previous
        else:
            unpin_trusted_key(TEST_KEY_ID)


# ── Entry point wiring ──────────────────────────────────────────────────────

def test_main_exists_and_is_callable():
    assert callable(umer_pkg.main)


def test_setup_py_entry_point_target_is_importable():
    """The exact ``module:attr`` that setup.py registers must resolve."""
    text = (_ROOT / "setup.py").read_text(encoding="utf-8")
    match = re.search(r'"umer-pkg=([\w.]+):(\w+)"', text)
    assert match, "setup.py no longer registers the umer-pkg console script"

    module_name, attr = match.group(1), match.group(2)
    import importlib

    module = importlib.import_module(module_name)
    assert hasattr(module, attr), (
        f"setup.py registers '{module_name}:{attr}' but {module_name} has no "
        f"attribute '{attr}' — the console script cannot run"
    )
    assert callable(getattr(module, attr))


# ── Exit codes ──────────────────────────────────────────────────────────────

def test_no_arguments_is_a_usage_error(env):
    with pytest.raises(SystemExit) as exc:
        umer_pkg.main([])
    assert exc.value.code != 0


def test_stats_and_list_succeed_on_empty_roots(env, capsys):
    assert umer_pkg.main([*env["dirs"], "stats"]) == 0
    assert umer_pkg.main([*env["dirs"], "list"]) == 0
    assert "no packages installed" in capsys.readouterr().out


def test_search_succeeds_with_no_hits(env):
    assert umer_pkg.main([*env["dirs"], "search", "definitely-not-a-package"]) == 0


def test_info_unknown_package_fails(env):
    assert umer_pkg.main([*env["dirs"], "info", "nope"]) == 1


def test_verify_missing_archive_fails(env):
    assert umer_pkg.main([*env["dirs"], "verify", str(env["root"] / "nope.umerpkg")]) == 1


def test_stats_json_is_machine_readable(env, capsys):
    assert umer_pkg.main([*env["dirs"], "--json", "stats"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "stats"
    assert payload["stats"]["installed"] == 0


# ── End-to-end signed lifecycle ─────────────────────────────────────────────

def _make_source(root: Path) -> Path:
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "hello.py").write_text("print('hello from a signed package')\n",
                                  encoding="utf-8")
    return src


def test_signed_build_verify_install_list_remove(env, capsys):
    src = _make_source(env["root"])
    # ``install`` resolves the target against the on-disk registry before it
    # will touch a file, so the archive is published into the registry dir.
    registry = env["root"] / "reg"
    registry.mkdir(parents=True, exist_ok=True)

    # build (signed) --------------------------------------------------------
    rc = umer_pkg.main([
        *env["dirs"], "build", str(src),
        "--name", "hello", "--version", "1.2.3",
        "--description", "CLI round-trip fixture",
        "--output", str(registry),
        "--sign-key", str(env["key_file"]),
        "--key-id", TEST_KEY_ID,
    ])
    assert rc == 0, capsys.readouterr().err

    archive = registry / "hello-1.2.3.umerpkg"
    assert archive.is_file(), "build did not produce the .umerpkg archive"

    # the archive really carries a signature member -------------------------
    import tarfile

    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
    assert "SIGNATURE" in names
    assert "HASH" in names

    # verify ----------------------------------------------------------------
    assert umer_pkg.main([*env["dirs"], "verify", str(archive)]) == 0

    # install (registry lookup and explicit --file both work) ---------------
    assert umer_pkg.main([*env["dirs"], "install", "hello"]) == 0
    assert umer_pkg.main(
        [*env["dirs"], "install", "hello", "--file", str(archive)]
    ) == 0

    # list ------------------------------------------------------------------
    capsys.readouterr()  # discard earlier non-JSON output
    assert umer_pkg.main([*env["dirs"], "--json", "list"]) == 0
    listed = json.loads(capsys.readouterr().out)["packages"]
    assert [p["name"] for p in listed] == ["hello"]
    assert listed[0]["version"] == "1.2.3"

    # info ------------------------------------------------------------------
    assert umer_pkg.main([*env["dirs"], "info", "hello"]) == 0

    # remove ----------------------------------------------------------------
    assert umer_pkg.main([*env["dirs"], "remove", "hello"]) == 0
    capsys.readouterr()
    assert umer_pkg.main([*env["dirs"], "--json", "list"]) == 0
    assert json.loads(capsys.readouterr().out)["packages"] == []


def test_unsigned_archive_is_refused(env, capsys):
    """A package with no SIGNATURE member must be refused (fail-closed)."""
    from packages.umer_pkg import UmerPackageManager

    src = _make_source(env["root"] / "unsigned")
    registry = env["root"] / "reg"
    registry.mkdir(parents=True, exist_ok=True)

    pm = UmerPackageManager(
        install_dir=str(env["root"] / "pkgs"),
        registry_dir=str(registry),
        cache_dir=str(env["root"] / "cache"),
    )
    archive = pm.build(
        source_dir=str(src),
        manifest={"name": "unsigned", "version": "0.1.0",
                  "description": "unsigned fixture"},
        output_dir=str(registry),
        signing_key=None,
    )
    assert umer_pkg.main([*env["dirs"], "verify", str(archive)]) == 1
    assert umer_pkg.main([*env["dirs"], "install", "unsigned"]) == 1


def test_capability_gate_class_is_untouched_by_cli(env):
    """The CLI must not silently change the process-wide gate posture."""
    fresh = CapabilityGate()
    assert fresh.strict is False
    umer_pkg.main([*env["dirs"], "stats"])
    assert gate.enforcing is False


def test_signature_member_is_valid_base64(env):
    """The SIGNATURE member is base64 Ed25519 material, not a placeholder."""
    src = _make_source(env["root"] / "b64")
    out_dir = env["root"] / "dist_b64"
    out_dir.mkdir(parents=True, exist_ok=True)
    assert umer_pkg.main([
        *env["dirs"], "build", str(src), "--name", "b64", "--version", "9.9.9",
        "--output", str(out_dir), "--sign-key", str(env["key_file"]),
        "--key-id", TEST_KEY_ID,
    ]) == 0

    import tarfile

    with tarfile.open(out_dir / "b64-9.9.9.umerpkg", "r:gz") as tar:
        blob = tar.extractfile("SIGNATURE").read()
    decoded = base64.b64decode(blob)
    assert len(decoded) == 64, "Ed25519 signatures are 64 bytes"
