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

"""Entry-point tests: `main.py`, `python -m boot.init`, and the console script.

The individual kernel subsystems are unit-tested, but nothing exercised the
documented entry point from start to finish.  Three fatal defects sat there
undetected as a result:

* ``self.vfs.mkdir("/tmp")`` raised ``FileExistsError`` (the VFS constructor
  had already created it);
* ``self.crypto.decrypt(nonce, ciphertext)`` passed two arguments to a method
  that unpacks ``(nonce, ciphertext)`` from one;
* ``main.py`` called ``boot()`` with no arguments, so ``--accept-eula`` was
  unreachable and the documented entry point could not be run non-interactively
  at all.

These tests run the real entry points in subprocesses with stdin closed (so the
shell receives EOF and the kernel shuts down gracefully) and assert exit codes,
ordered boot checkpoints, and consent handling.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_BOOT_TIMEOUT_S = 180

# Checkpoints that must appear, in order, on a successful boot.
_BOOT_MARKERS = (
    "[KERNEL] Boot sequence initiated.",
    "[QFS] Mounted at /",
    "[KERNEL] Crypto round-trip verification: PASS",
    "[KERNEL] Entering main execution loop...",
)


def _run(
    args: list[str],
    *,
    stdin: str = "devnull",
    tmp_path: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run an entry point.

    ``stdin="devnull"`` uses the platform null device — on Windows ``NUL``
    reports ``isatty() == True``, so it exercises the *interactive* branch.  Use
    ``stdin="empty"`` for a genuine non-TTY stdin (empty regular file), which is
    the case a service manager or shell redirection produces.
    """
    if stdin == "empty":
        assert tmp_path is not None, "stdin='empty' needs tmp_path"
        empty = tmp_path / "empty_stdin"
        empty.write_bytes(b"")
        stdin_arg: object = open(empty, "rb")
    else:
        stdin_arg = subprocess.DEVNULL

    try:
        return subprocess.run(
            [sys.executable, *args],
            cwd=str(_ROOT),
            stdin=stdin_arg,
            capture_output=True,
            text=True,
            timeout=_BOOT_TIMEOUT_S,
        )
    finally:
        if hasattr(stdin_arg, "close"):
            stdin_arg.close()


# ── The real thing: a full boot through the documented entry point ──────────

def test_main_accept_eula_boots_and_exits_cleanly():
    """`python main.py --accept-eula` must boot, idle, and exit 0."""
    result = _run(["main.py", "--accept-eula"])

    assert "Traceback" not in result.stderr, (
        "boot raised an unhandled exception:\n" + result.stderr[-4000:]
    )
    assert result.returncode == 0, (
        f"boot exited {result.returncode}\n"
        f"--- stdout tail ---\n{result.stdout[-2000:]}\n"
        f"--- stderr tail ---\n{result.stderr[-2000:]}"
    )
    for marker in _BOOT_MARKERS:
        assert marker in result.stdout, f"boot never reached: {marker}"


def test_headless_boot_on_real_non_tty_stdin_exits(tmp_path):
    """The headless case that used to hang: real non-TTY stdin.

    With a non-TTY stdin no shell starts, so nothing ever requested shutdown and
    the idle loop spun forever. ``--exit-after-boot`` gives a deterministic exit.
    """
    result = _run(
        ["main.py", "--accept-eula", "--exit-after-boot"],
        stdin="empty",
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, (
        f"headless boot exited {result.returncode}\n"
        f"--- stdout tail ---\n{result.stdout[-2000:]}\n"
        f"--- stderr tail ---\n{result.stderr[-2000:]}"
    )
    for marker in _BOOT_MARKERS:
        assert marker in result.stdout, f"boot never reached: {marker}"
    assert "exit-after-boot requested" in result.stdout


def test_boot_init_module_accept_eula_boots_and_exits_cleanly():
    """The `python -m boot.init --accept-eula` path must also complete."""
    result = _run(["-m", "boot.init", "--accept-eula"])
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    assert "[KERNEL] Boot sequence initiated." in result.stdout


def test_boot_init_module_supports_exit_after_boot(tmp_path):
    result = _run(
        ["-m", "boot.init", "--accept-eula", "--exit-after-boot"],
        stdin="empty",
        tmp_path=tmp_path,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]


def test_main_without_consent_fails_closed(tmp_path):
    """No flag and no TTY must abort *before* booting (fail-closed)."""
    result = _run(["main.py"], stdin="empty", tmp_path=tmp_path)

    assert result.returncode == 1, (
        "non-interactive boot without --accept-eula must refuse to boot"
    )
    assert "explicit consent" in (result.stdout + result.stderr)
    # Must fail closed cleanly, not die with a traceback.
    assert "Traceback" not in result.stderr, result.stderr[-2000:]
    # The kernel must never have started.
    assert "[KERNEL] Boot sequence initiated." not in result.stdout


# ── CLI surface ─────────────────────────────────────────────────────────────

def test_help_documents_accept_eula():
    result = _run(["main.py", "--help"])
    assert result.returncode == 0
    assert "--accept-eula" in result.stdout


def test_version_flag():
    result = _run(["main.py", "--version"])
    assert result.returncode == 0
    assert re.search(r"UmerOS \d+\.\d+\.\d+", result.stdout)


def test_unknown_flag_is_a_usage_error():
    result = _run(["main.py", "--definitely-not-a-flag"])
    assert result.returncode == 2


# ── Flag forwarding (in-process) ────────────────────────────────────────────

def test_main_forwards_accept_eula_true(monkeypatch):
    import main as entry

    seen = {}
    monkeypatch.setattr(entry, "boot", lambda **kw: seen.update(kw))

    assert entry.main(["--accept-eula"]) == 0
    assert seen == {"accept_eula": True, "exit_after_boot": False}


def test_main_forwards_accept_eula_false_by_default(monkeypatch):
    import main as entry

    seen = {}
    monkeypatch.setattr(entry, "boot", lambda **kw: seen.update(kw))

    assert entry.main([]) == 0
    assert seen == {"accept_eula": False, "exit_after_boot": False}


def test_main_forwards_exit_after_boot(monkeypatch):
    import main as entry

    seen = {}
    monkeypatch.setattr(entry, "boot", lambda **kw: seen.update(kw))

    assert entry.main(["--accept-eula", "--exit-after-boot"]) == 0
    assert seen == {"accept_eula": True, "exit_after_boot": True}


def test_main_accepts_an_explicit_argv(monkeypatch):
    import main as entry

    seen = {}
    monkeypatch.setattr(entry, "boot", lambda **kw: seen.update(kw))

    entry.main(["--accept-eula"])
    assert seen["accept_eula"] is True


# ── Headless termination ────────────────────────────────────────────────────

def test_headless_run_installs_signal_handlers(monkeypatch):
    """Without a shell, SIGINT/SIGTERM must request a graceful shutdown.

    The idle loop otherwise has no way to stop other than killing the process.
    """
    import signal

    from kernel.umer_kernel import UmerKernel

    kernel = UmerKernel()
    installed: dict = {}
    monkeypatch.setattr(signal, "signal",
                        lambda sig, handler: installed.setdefault(sig, handler))

    kernel._install_shutdown_signal_handlers()

    assert installed, "no shutdown signal handlers were installed"
    assert kernel._shutdown_requested is False
    for handler in installed.values():
        handler(signal.SIGINT, None)
    assert kernel._shutdown_requested is True


def test_boot_accepts_exit_after_boot():
    """`boot.init.boot` must expose the flag and forward it to the kernel."""
    import inspect

    from boot.init import Bootloader, boot

    assert "exit_after_boot" in inspect.signature(boot).parameters
    assert "exit_after_boot" in inspect.signature(Bootloader.load_kernel).parameters


# ── Console-script wiring ───────────────────────────────────────────────────

def test_umeros_console_script_target_resolves():
    """The `module:attr` in setup.py must import and be callable."""
    text = (_ROOT / "setup.py").read_text(encoding="utf-8")
    match = re.search(r'"umeros=([\w.]+):(\w+)"', text)
    assert match, "setup.py no longer registers the umeros console script"

    module_name, attr = match.group(1), match.group(2)
    import importlib

    module = importlib.import_module(module_name)
    assert hasattr(module, attr), (
        f"setup.py registers '{module_name}:{attr}' but {module_name} has no "
        f"attribute '{attr}' — the console script cannot run"
    )
    assert callable(getattr(module, attr))


# ── Capability-gate lifecycle through a real boot ───────────────────────────

def test_boot_wires_the_capability_gate_and_detaches_on_shutdown():
    """H113 end-to-end: the running kernel must enforce, then release the gate."""
    probe = (
        "import asyncio, sys;"
        "from core.capability_gate import gate;"
        "from kernel.umer_kernel import UmerKernel;"
        "k = UmerKernel();"
        "assert gate.enforcing, 'gate not wired after construction';"
        "assert gate.principal == 0, 'kernel is not the system principal';"
        "asyncio.run(k.shutdown());"
        "assert not gate.enforcing, 'gate still enforcing after shutdown';"
        "print('GATE_OK')"
    )
    result = _run(["-c", probe])
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-4000:]
    assert "GATE_OK" in result.stdout
