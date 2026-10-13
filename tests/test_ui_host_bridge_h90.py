"""tests — HostBridge host-disk containment (ui/umer_de.py).

``ui/umer_de.py`` imports tkinter/vlc/fitz/PIL at module scope, which may be
unavailable in a headless test runner, so we load the module by file path under
a unique name and stub only the *third-party* GUI deps we cannot import. The
logic under test (``HostBridge`` + ``_host_autoopen_allowed``) touches none of
them.

The headline security claims:
  * a ``vfs_path`` ending in ``..`` can NO LONGER escape ``HostFiles/``
  * the write is ``O_CREAT|O_EXCL|O_NOFOLLOW`` (no clobber, no symlink redirect)
  * auto-open is refused by default (opt-in env + extension allow-list)
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "ui" / "umer_de.py"


# ── load ui/umer_de.py with stubbed GUI deps ──────────────────────────────
def _make_stub(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


class _Any:
    """Callable/attr-lazy sentinel for stubbed GUI classes."""

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, item):
        return _Any()

    def __call__(self, *a, **k):
        return _Any()


def _install_stubs():
    saved = {}
    stubs = {
        "tkinter": _make_stub("tkinter", Toplevel=_Any, Tk=_Any, Canvas=_Any,
                              Frame=_Any, Label=_Any, StringVar=_Any,
                              BOTH=1, X=1, Y=1, LEFT=1, RIGHT=1, TOP=1,
                              BOTTOM=1, END=1, VERTICAL=1, W=1),
        "tkinter.ttk": _make_stub("tkinter.ttk", Frame=_Any, Label=_Any,
                                  Button=_Any, Entry=_Any, Treeview=_Any,
                                  Style=_Any, Separator=_Any),
        "tkinter.scrolledtext": _make_stub("tkinter.scrolledtext",
                                           ScrolledText=_Any),
        "tkinter.messagebox": _make_stub("tkinter.messagebox",
                                         showinfo=_Any, showerror=_Any),
        "yt_dlp": _make_stub("yt_dlp", YoutubeDL=_Any),
        "vlc": _make_stub("vlc", Instance=_Any),
        "fitz": _make_stub("fitz", open=_Any, Matrix=_Any),
        "PIL": _make_stub("PIL", Image=_Any, ImageTk=_Any),
        "PIL.Image": _make_stub("PIL.Image", frombytes=_Any),
        "PIL.ImageTk": _make_stub("PIL.ImageTk", PhotoImage=_Any),
    }
    for name, mod in stubs.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod
        if "." in name:
            parent, _, child = name.partition(".")
            pmod = sys.modules.get(parent)
            if pmod is not None:
                setattr(pmod, child, mod)
    return saved


def _restore(saved):
    for name, mod in saved.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod


def _load_module():
    saved = _install_stubs()
    try:
        spec = importlib.util.spec_from_file_location("umer_de_h90", MOD_PATH)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["umer_de_h90"] = mod
        spec.loader.exec_module(mod)
    finally:
        _restore(saved)
    return mod


_MOD = _load_module()
HostBridge = _MOD.HostBridge
_host_autoopen_allowed = _MOD._host_autoopen_allowed
_HOST_AUTOOPEN_EXTS = _MOD._HOST_AUTOOPEN_EXTS


# ── a minimal fake VFS ────────────────────────────────────────────────────
class _FakeVFS:
    def __init__(self, files):
        self._files = files

    def read_file(self, path):
        return self._files.get(path)


class _FakeKernel:
    def __init__(self, files):
        self.vfs = _FakeVFS(files)


@pytest.fixture()
def host_dir(tmp_path, monkeypatch):
    """Point HostBridge at a temp HostFiles/ dir and return (host_dir, kernel)."""
    hd = tmp_path / "HostFiles"
    monkeypatch.setattr(HostBridge, "HOST_DIR", str(hd))
    return hd


# ── the traversal escape (the H90 headline) ───────────────────────────────
@pytest.mark.parametrize("vfs_path", [
    "/user/..",
    "..",
    "/user/a/../..",
    "../..",
])
def test_traversal_leaf_rejected(host_dir, vfs_path, monkeypatch):
    """A vfs_path whose leaf is `..` must NOT escape HostFiles/."""
    sentinel = host_dir.parent / "PWNED.txt"
    kernel = _FakeKernel({vfs_path: b"PWNED"})
    ok, result = HostBridge.extract_and_open(kernel, vfs_path)
    assert ok is False, f"traversal accepted for {vfs_path!r}"
    assert not sentinel.exists(), "write escaped HostFiles/ to its parent!"
    # nothing was created inside HostFiles either
    assert not list(host_dir.glob("*")) if host_dir.exists() else True


def test_normal_file_still_works(host_dir):
    kernel = _FakeKernel({"/user/notes.txt": b"hello"})
    ok, host_path = HostBridge.extract_and_open(kernel, "/user/notes.txt")
    assert ok is True
    assert Path(host_path).parent == host_dir
    assert Path(host_path).name == "notes.txt"
    assert Path(host_path).read_bytes() == b"hello"


def test_missing_vfs_file_reported(host_dir):
    kernel = _FakeKernel({})
    ok, result = HostBridge.extract_and_open(kernel, "/user/nope.txt")
    assert ok is False
    assert "not found" in result.lower()


def test_no_clobber_existing_host_file(host_dir):
    """O_EXCL: a pre-existing target is not overwritten."""
    host_dir.mkdir(parents=True, exist_ok=True)
    target = host_dir / "notes.txt"
    target.write_bytes(b"ORIGINAL")
    kernel = _FakeKernel({"/user/notes.txt": b"REPLACED"})
    ok, result = HostBridge.extract_and_open(kernel, "/user/notes.txt")
    assert ok is False
    assert target.read_bytes() == b"ORIGINAL"


def test_basename_leaf_is_contained(host_dir):
    """Deep VFS paths land directly in HostFiles/ with only the leaf name."""
    kernel = _FakeKernel({"/a/b/c/deep.bin": b"data"})
    ok, host_path = HostBridge.extract_and_open(kernel, "/a/b/c/deep.bin")
    assert ok is True
    assert Path(host_path).parent == host_dir
    assert Path(host_path).name == "deep.bin"


# ── auto-open must be OFF by default ──────────────────────────────────────
def test_open_in_host_refused_by_default(monkeypatch):
    monkeypatch.delenv("UMEROS_ALLOW_HOST_AUTOOPEN", raising=False)
    ok, msg = HostBridge.open_in_host("C:/tmp/whatever.txt")
    assert ok is False
    assert "disabled" in msg.lower()


def test_autoopen_gate_env_off(monkeypatch):
    monkeypatch.delenv("UMEROS_ALLOW_HOST_AUTOOPEN", raising=False)
    assert _host_autoopen_allowed("x.txt") is False


@pytest.mark.parametrize("ext", ["exe", "bat", "cmd", "ps1", "scr", "html", "svg",
                                 "pdf", "js", "vbs", "lnk", "zip", "docm", "jar"])
def test_autoopen_gate_rejects_active_extensions(monkeypatch, ext):
    monkeypatch.setenv("UMEROS_ALLOW_HOST_AUTOOPEN", "1")
    assert _host_autoopen_allowed(f"payload.{ext}") is False


@pytest.mark.parametrize("ext", sorted(_HOST_AUTOOPEN_EXTS))
def test_autoopen_gate_accepts_allowlisted(monkeypatch, ext):
    monkeypatch.setenv("UMEROS_ALLOW_HOST_AUTOOPEN", "1")
    assert _host_autoopen_allowed(f"pic.{ext}") is True


def test_autoopen_env_one_required(monkeypatch):
    monkeypatch.setenv("UMEROS_ALLOW_HOST_AUTOOPEN", "true")  # not exactly "1"
    assert _host_autoopen_allowed("a.txt") is False


# ── source invariants ─────────────────────────────────────────────────────
def test_source_uses_path_guard_and_excl():
    src = MOD_PATH.read_text(encoding="utf-8")
    assert "safe_child(" in src
    assert "os.O_CREAT | os.O_EXCL" in src
    assert "os.O_NOFOLLOW" in src
    assert "UMEROS_ALLOW_HOST_AUTOOPEN" in src
