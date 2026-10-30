"""H218 -- pin TLS certificate verification for provider auth REST calls.

The row says ``quantum/cloud/auth.py:69-109`` ``_http_request`` uses
``urllib.request.urlopen`` with default system trust only and no cert
pinning, so a rogue CA / MITM can capture provider tokens.

Fix (session 206): added ``_tls_context()`` which returns a strict
``SSLContext`` (``CERT_REQUIRED``, ``check_hostname=True``, minimum TLS 1.2)
with optional CA pinning via ``UMEROS_TLS_CAFILE``.  ``_http_request`` now
passes ``context=_tls_context()`` to ``urlopen``.
"""

from __future__ import annotations

import ast
import os
import ssl
import urllib.request
from pathlib import Path

import pytest

AUTH_PATH = Path(__file__).resolve().parent.parent / "quantum" / "cloud" / "auth.py"
#: H225 moved the TLS policy into ``quantum/tls.py`` so the 22 REST call sites
#: in the package share one implementation.  The *policy* assertions below now
#: point at that single source of truth; ``auth.py`` is asserted to delegate to
#: it, which is the property H218 actually cares about.
TLS_PATH = Path(__file__).resolve().parent.parent / "quantum" / "tls.py"


def _source() -> str:
    return AUTH_PATH.read_text(encoding="utf-8")


def _tls_source() -> str:
    return TLS_PATH.read_text(encoding="utf-8")


class TestSourceInvariants:
    """Source-level checks that the TLS hardening is present."""

    def test_imports_ssl(self) -> None:
        assert "import ssl" in _source(), "auth.py must import ssl"

    def test_has_tls_context_helper(self) -> None:
        assert "_tls_context" in _source(), "auth.py must define _tls_context"

    def test_delegates_to_shared_policy(self) -> None:
        """H218's policy now lives in ``quantum/tls.py``; auth.py delegates."""
        assert "from ..tls import tls_context" in _source()
        assert "return tls_context()" in _source(), (
            "auth.py::_tls_context must delegate to quantum.tls.tls_context"
        )

    def test_cert_required(self) -> None:
        assert "CERT_REQUIRED" in _tls_source(), "must enforce CERT_REQUIRED"

    def test_check_hostname(self) -> None:
        assert "check_hostname = True" in _tls_source(), "must check hostname"

    def test_minimum_tls_1_2(self) -> None:
        assert "TLSv1_2" in _tls_source(), "must enforce minimum TLS 1.2"

    def test_cafile_pinning(self) -> None:
        assert "UMEROS_TLS_CAFILE" in _tls_source(), "must support CA pinning"

    def test_urlopen_passes_context(self) -> None:
        """urlopen must be called with context=_tls_context()."""
        assert "context=_tls_context()" in _source(), (
            "urlopen must pass context=_tls_context()"
        )

    def test_no_unverified_fallback(self) -> None:
        """There must be no *code* path that disables verification.

        AST-based (not a text grep): comments and docstrings may legitimately
        mention ``CERT_NONE`` to explain that it is never used, so the check
        looks for real attribute access on the ``ssl`` module instead.
        """
        tree = ast.parse(_source())
        offenders: list[str] = []
        for node in ast.walk(tree):
            # ssl.CERT_NONE attribute access
            if isinstance(node, ast.Attribute):
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "ssl"
                    and node.attr == "CERT_NONE"
                ):
                    offenders.append(f"line {node.lineno}: ssl.CERT_NONE")
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "ssl"
                    and node.attr == "_create_unverified_context"
                ):
                    offenders.append(
                        f"line {node.lineno}: ssl._create_unverified_context"
                    )
            # Bare CERT_NONE name (from-import form)
            if isinstance(node, ast.Name) and node.id == "CERT_NONE":
                offenders.append(f"line {node.lineno}: bare CERT_NONE")

        assert not offenders, (
            "unverified TLS code found: " + "; ".join(offenders)
        )

    def test_docstring_documents_tls(self) -> None:
        """Module docstring must mention TLS / cert pinning."""
        tree = ast.parse(_source())
        doc = ast.get_docstring(tree)
        assert doc is not None, "module must have a docstring"
        assert "TLS" in doc or "tls" in doc.lower(), (
            "docstring must mention TLS"
        )


class TestTlsContextBehavior:
    """Runtime checks that _tls_context() returns a strict context."""

    def test_returns_ssl_context(self) -> None:
        import sys
        sys.path.insert(0, str(AUTH_PATH.parent.parent.parent))
        from quantum.cloud.auth import _tls_context

        ctx = _tls_context()
        assert isinstance(ctx, ssl.SSLContext), "must return SSLContext"

    def test_cert_required_mode(self) -> None:
        import sys
        sys.path.insert(0, str(AUTH_PATH.parent.parent.parent))
        from quantum.cloud.auth import _tls_context

        ctx = _tls_context()
        assert ctx.verify_mode == ssl.CERT_REQUIRED, (
            "verify_mode must be CERT_REQUIRED"
        )

    def test_check_hostname_true(self) -> None:
        import sys
        sys.path.insert(0, str(AUTH_PATH.parent.parent.parent))
        from quantum.cloud.auth import _tls_context

        ctx = _tls_context()
        assert ctx.check_hostname is True, "check_hostname must be True"

    def test_minimum_tls_1_2(self) -> None:
        import sys
        sys.path.insert(0, str(AUTH_PATH.parent.parent.parent))
        from quantum.cloud.auth import _tls_context

        ctx = _tls_context()
        # The minimum_version should be TLSv1_2 or higher
        assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2, (
            "minimum TLS version must be >= 1.2"
        )

    def test_context_is_cached(self) -> None:
        """_tls_context() should return the same cached context."""
        import sys
        sys.path.insert(0, str(AUTH_PATH.parent.parent.parent))
        from quantum.cloud.auth import _tls_context

        ctx1 = _tls_context()
        ctx2 = _tls_context()
        assert ctx1 is ctx2, "should return cached context"


class TestHttpRequestUsesTls:
    """Verify _http_request passes the TLS context to urlopen."""

    def test_http_request_accepts_context(self) -> None:
        """The _http_request function must pass context to urlopen."""
        src = _source()
        # Find the urlopen call in _http_request
        assert "urlopen" in src
        # Verify the context parameter is passed
        assert "context=_tls_context()" in src


class TestModuleDocstring:
    """Verify the module docstring is compliant with section 1."""

    def test_has_author_trailer(self) -> None:
        assert "Author:  Umer OS Project" in _source(), (
            "docstring must have Author trailer (two spaces)"
        )

    def test_has_license_trailer(self) -> None:
        assert "License: GPL-3.0 (GNU General Public License v3)" in _source(), (
            "docstring must have License trailer"
        )

    def test_has_future_annotations(self) -> None:
        assert "from __future__ import annotations" in _source(), (
            "must have from __future__ import annotations"
        )
