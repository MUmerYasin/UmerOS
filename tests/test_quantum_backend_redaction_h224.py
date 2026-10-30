"""pin that a failed IBM backend init cannot leak the provider token.

The row said ``quantum/backend.py:291`` ``IBMBackend.__init__`` does
``print(f"IBM Backend init warning: {e}")``, which "can surface
token/endpoint detail in stdout".

Drift-recon (session 211): premise **TRUE**, line ref stale -- the ``print``
was at **304**, not 291.  The module had **no ``logging`` import at all**, so
the only diagnostic channel was stdout, and the exception text was interpolated
verbatim: a ``HTTPError`` from ``requests`` (raised deep inside the IBM SDK)
carries the request URL including its query string, and some SDKs format the
auth token straight into the message.

Fix, following the row's remedy (the ``providers/base.py`` redaction pattern):

* ``import logging`` + ``log = logging.getLogger("UmerOS.Quantum.Backend")``
* ``_redact_secrets(text, *secrets)`` scrubs every supplied secret to ``***``
* the ``except Exception`` branch now logs at WARNING with the exception *type*
  and the **scrubbed** message -- nothing is printed
* ``IBMBackend.__repr__`` mirrors ``BackendSession.__repr__``: ``token='***'``
"""

from __future__ import annotations

import ast
import logging
import sys
import types
from pathlib import Path

import pytest

BACKEND_PATH = Path(__file__).resolve().parent.parent / "quantum" / "backend.py"

TOKEN = "tok-secret-abcdef123456"


def _src() -> str:
    return BACKEND_PATH.read_text(encoding="utf-8")


def _backend_mod():
    root = str(BACKEND_PATH.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from quantum import backend

    return backend


def _print_calls(tree: ast.AST) -> list:
    """Return every ``print(...)`` call node in ``tree``."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "print":
                found.append(node)
    return found


# ---------------------------------------------------------------------------
# Source invariants
# ---------------------------------------------------------------------------

class TestSourceInvariants:
    def test_no_print_call_anywhere(self):
        """The module is a library: diagnostics go through ``logging`` only."""
        calls = _print_calls(ast.parse(_src()))
        assert calls == [], f"backend.py still prints at lines {[c.lineno for c in calls]}"

    def test_module_has_logging(self):
        src = _src()
        assert "import logging" in src
        assert "logging.getLogger(" in src

    def test_old_raw_print_string_is_gone(self):
        assert "IBM Backend init warning" not in _src()

    def test_exception_is_logged_at_warning(self):
        src = _src()
        assert "log.warning(" in src
        # the type name is logged separately from the (untrusted) message
        assert "type(exc).__name__" in src

    def test_redaction_helper_defined(self):
        src = _src()
        assert "def _redact_secrets(" in src
        assert '_SECRET_PLACEHOLDER = "***"' in src

    def test_repr_redacts_token(self):
        mod = _backend_mod()
        tree = ast.parse(_src())
        ibm = next(
            n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "IBMBackend"
        )
        names = [n.name for n in ibm.body if isinstance(n, ast.FunctionDef)]
        assert "__repr__" in names
        assert "***" in _src()
        # and the attribute really exists at runtime
        assert "__repr__" in mod.IBMBackend.__dict__

    def test_docstring_documents_redaction(self):
        doc = _backend_mod().__doc__ or ""
        assert "redact" in doc.lower() or "token" in doc.lower()

    def test_section1_trailer(self):
        src = _src()
        assert "Author:  Umer OS Project" in src
        assert "License: GPL-3.0 (GNU General Public License v3)" in src


# ---------------------------------------------------------------------------
# The scrubber itself
# ---------------------------------------------------------------------------

class TestRedactSecrets:
    def test_replaces_token(self):
        redact = _backend_mod()._redact_secrets
        out = redact(f"401 for token={TOKEN}", TOKEN)
        assert TOKEN not in out
        assert out == "401 for token=***"

    def test_replaces_every_occurrence(self):
        redact = _backend_mod()._redact_secrets
        out = redact(f"{TOKEN} and again {TOKEN}", TOKEN)
        assert TOKEN not in out
        assert out.count("***") == 2

    def test_multiple_secrets(self):
        redact = _backend_mod()._redact_secrets
        out = redact("token=aaaabbbb key=ccccdddd", "aaaabbbb", "ccccdddd")
        assert "aaaabbbb" not in out and "ccccdddd" not in out
        assert out == "token=*** key=***"

    def test_none_secret_ignored(self):
        redact = _backend_mod()._redact_secrets
        assert redact("hello", None) == "hello"

    def test_empty_secret_ignored(self):
        redact = _backend_mod()._redact_secrets
        assert redact("hello", "") == "hello"

    def test_short_secret_ignored(self):
        """A 1-3 char 'secret' would shred the message for no gain."""
        redact = _backend_mod()._redact_secrets
        assert redact("a bc", "a") == "a bc"

    def test_four_char_secret_is_scrubbed(self):
        redact = _backend_mod()._redact_secrets
        assert redact("abcd", "abcd") == "***"

    def test_none_text_becomes_empty(self):
        redact = _backend_mod()._redact_secrets
        assert redact(None, TOKEN) == ""

    def test_non_string_text_coerced(self):
        redact = _backend_mod()._redact_secrets
        assert redact(RuntimeError(f"bad {TOKEN}"), TOKEN) == "bad ***"

    def test_no_secrets_is_identity(self):
        redact = _backend_mod()._redact_secrets
        assert redact("plain text") == "plain text"


# ---------------------------------------------------------------------------
# Behaviour of a failed init
# ---------------------------------------------------------------------------

def _fake_sdk(monkeypatch, service_cls):
    """Install a stand-in ``qiskit_ibm_runtime`` module into ``sys.modules``."""
    mod = types.ModuleType("qiskit_ibm_runtime")
    mod.QiskitRuntimeService = service_cls
    monkeypatch.setitem(sys.modules, "qiskit_ibm_runtime", mod)


class TestInitFailureIsQuiet:
    def test_missing_dependency_stays_offline(self, monkeypatch, capsys, caplog):
        monkeypatch.setitem(sys.modules, "qiskit_ibm_runtime", None)
        backend = _backend_mod()
        with caplog.at_level(logging.DEBUG, logger="UmerOS.Quantum.Backend"):
            be = backend.IBMBackend(token=TOKEN)
        assert be.status() is backend.BackendStatus.OFFLINE
        assert capsys.readouterr().out == ""
        # the missing optional dependency is a debug note, not a warning
        assert all(r.levelno < logging.WARNING for r in caplog.records)

    def test_failed_auth_logs_warning_without_token(self, monkeypatch, capsys, caplog):
        class Boom:
            def __init__(self, token=None, instance=None):
                raise RuntimeError(
                    f"401 Unauthorized: token={token} "
                    f"GET https://api.quantum.ibm.com/v1/backends?access_token={token}"
                )

        _fake_sdk(monkeypatch, Boom)
        backend = _backend_mod()
        with caplog.at_level(logging.WARNING, logger="UmerOS.Quantum.Backend"):
            be = backend.IBMBackend(token=TOKEN)

        out = capsys.readouterr().out
        assert out == "", "a failed init must not write to stdout"
        assert be.status() is backend.BackendStatus.OFFLINE

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert TOKEN not in message, "the token leaked into the log record"
        assert "***" in message
        assert "RuntimeError" in message

    def test_failed_init_keeps_offline_defaults(self, monkeypatch):
        class Boom:
            def __init__(self, token=None, instance=None):
                raise RuntimeError("nope")

        _fake_sdk(monkeypatch, Boom)
        backend = _backend_mod()
        be = backend.IBMBackend(token=TOKEN, backend_name="ibm_torino")
        assert be.num_qubits == 127
        assert be.max_shots == 4000
        assert be.name == "ibm_torino"
        assert be._backend is None and be._service is None

    def test_repr_masks_token(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "qiskit_ibm_runtime", None)
        backend = _backend_mod()
        be = backend.IBMBackend(token=TOKEN)
        text = repr(be)
        assert TOKEN not in text
        # same shape as providers/base.py::BackendSession.__repr__ -> "token=***"
        assert "token=***" in text
        assert "online=False" in text

    def test_repr_without_token_says_none(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "qiskit_ibm_runtime", None)
        backend = _backend_mod()
        assert "token=None" in repr(backend.IBMBackend())

    def test_successful_init_is_silent(self, monkeypatch, capsys, caplog):
        class FakeBackendHandle:
            num_qubits = 156
            max_shots = 3000

            def status(self):
                return types.SimpleNamespace(operational=True)

        class Ok:
            def __init__(self, token=None, instance=None):
                self.token = token

            def backend(self, name):
                return FakeBackendHandle()

        _fake_sdk(monkeypatch, Ok)
        backend = _backend_mod()
        with caplog.at_level(logging.DEBUG, logger="UmerOS.Quantum.Backend"):
            be = backend.IBMBackend(token=TOKEN)
        assert capsys.readouterr().out == ""
        assert caplog.records == []
        assert be.status() is backend.BackendStatus.ONLINE
        assert be.num_qubits == 156
