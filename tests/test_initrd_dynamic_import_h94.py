"""tests — allow-listed dynamic imports in initrd/ (CWE-470-adjacent).

``ai_helper._try_import`` used to call ``__import__(name)`` with no validation;
``__main__._cmd_selftest`` fed a literal tuple straight into ``__import__``.
Both now resolve names via an explicit allow-list + ``importlib.import_module``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from initrd import __main__ as initrd_main  # noqa: E402
from initrd.ai_helper import AIHelper, _OPTIONAL_IMPORTS  # noqa: E402


# ── ai_helper._try_import ─────────────────────────────────────────────────
def test_allow_list_is_the_documented_set():
    assert _OPTIONAL_IMPORTS == ("qiskit", "sklearn")


@pytest.mark.parametrize("name", ["qiskit", "sklearn"])
def test_allow_listed_names_do_not_raise(name):
    """Allow-listed names either import or degrade to None — never raise."""
    h = AIHelper()
    result = h._try_import(name)  # must not raise regardless of availability
    assert result is None or hasattr(result, "__name__")


@pytest.mark.parametrize("name", [
    "os",                 # stdlib, not allow-listed
    "sys",
    "builtins",           # would expose __import__ itself
    "subprocess",
    "__main__",
    "initrd.ai_helper",   # first-party but not on THIS list
    "",                   # empty
    "os.path",
    "qiskit; os.system",  # injection-shaped
])
def test_non_allow_listed_names_refused(name):
    h = AIHelper()
    assert h._try_import(name) is None


def test_refusal_is_logged(caplog):
    h = AIHelper()
    with caplog.at_level("WARNING", logger="UmerOS.Initrd.AIHelper"):
        h._try_import("totally-not-allowed")
    assert any("Refusing non-allow-listed import" in r.message for r in caplog.records)


def test_allow_list_cannot_be_influenced_by_instance():
    """The allow-list is module-level (not per-instance state)."""
    h = AIHelper()
    h._OPTIONAL_IMPORTS = ("os",)  # attempt an instance-level override
    assert h._try_import("os") is None  # module constant still governs


# ── __main__._cmd_selftest allow-list ─────────────────────────────────────
def test_selftest_module_list_is_closed_and_first_party():
    mods = initrd_main._SELFTEST_MODULES
    assert isinstance(mods, tuple)
    assert all(m.startswith("initrd.") for m in mods)
    assert "initrd.ai_helper" in mods
    assert "initrd.linuxrc" in mods


def test_selftest_runs_and_returns_zero():
    rc = initrd_main._cmd_selftest([])
    assert rc == 0


def _live_dunder_import_calls(src: str) -> list[str]:
    """Return live `__import__(...)` call sites, ignoring comments/strings."""
    import ast as _ast
    tree = _ast.parse(src)
    hits = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call):
            fn = node.func
            if isinstance(fn, _ast.Name) and fn.id == "__import__":
                hits.append(_ast.dump(node))
    return hits


def test_selftest_uses_importlib_not_raw_dunder_import():
    src = (ROOT / "initrd" / "__main__.py").read_text(encoding="utf-8")
    assert "importlib.import_module" in src
    assert _live_dunder_import_calls(src) == []  # no live raw builtin call


def test_ai_helper_uses_importlib_not_raw_dunder_import():
    src = (ROOT / "initrd" / "ai_helper.py").read_text(encoding="utf-8")
    assert "importlib.import_module" in src
    assert _live_dunder_import_calls(src) == []


def test_selftest_rejects_non_initrd_name(monkeypatch, caplog):
    """A widened list (e.g. an injected name) is refused, not imported."""
    monkeypatch.setattr(
        initrd_main, "_SELFTEST_MODULES", ("os", "initrd.cpio"),
    )
    with caplog.at_level("ERROR", logger="UmerOS.Initrd.CLI"):
        rc = initrd_main._cmd_selftest([])
    assert rc == 1  # 'os' refused -> FAIL
    assert any("Refusing non-allow-listed selftest module" in r.message
               for r in caplog.records)


# ── regression: normal helpers still work ─────────────────────────────────
def test_ai_helper_diagnostics_still_work():
    h = AIHelper()
    d = h.diagnostics()
    assert set(d) >= {"qiskit_available", "sklearn_available", "enabled"}
