"""H225 -- every provider REST call must go through the pinned TLS policy.

The row says provider tokens travel in clear headers over provider REST --
IBM ``Bearer {access_token}``, IonQ ``apiKey {api_key}``, AWS
``AWS4-HMAC-SHA256 Credential={access_key}``, Rigetti ``Bearer {api_key}`` --
"with no pinning (overlaps H218)", and asks to "centralize provider HTTP in
``cloud/`` with pinned certs + redacted logging".

Drift-recon (session 212): premise **TRUE**, and worse than stated.  H218
hardened exactly one call site (``cloud/auth.py``); **21 more** ``urlopen``
calls across six modules still passed no ``context=`` argument at all, so they
used the platform default:

* ``cloud/job.py``            -- 1 (job polling, ``Authorization: Bearer``)
* ``providers/braket_provider.py`` -- 1 (SigV4 ``Credential=``)
* ``providers/ionq_provider.py``   -- 2 (``apiKey``)
* ``providers/rigetti_provider.py`` -- 1 (``Bearer``)
* ``quantum_sim.py``          -- 16 (IBM/IonQ/Braket/Rigetti device classes)

``cloud/session.py`` needed no change: it routes every request through
``cloud.job._http_request``, so it inherits the policy -- its unused
``import urllib.error``/``urllib.request`` were removed because a local
``urlopen`` would silently bypass it.

Fix: ``quantum/tls.py`` is now the single source of truth (``tls_context()``,
``CAFILE_ENV``, ``MINIMUM_TLS_VERSION``, ``reset_tls_context()``); ``auth.py``
keeps ``_tls_context`` as a thin alias so the H218 suite still pins that name,
and every other call site passes ``context=tls_context()``.
"""

from __future__ import annotations

import ast
import os
import ssl
import sys
from pathlib import Path

import pytest

QUANTUM = Path(__file__).resolve().parent.parent / "quantum"
TLS_PATH = QUANTUM / "tls.py"

CANON = "License: GPL-3.0 (GNU General Public License v3)"
AUTHOR = "Author:  Umer OS Project"

#: urlopen call sites per module, as audited in session 212.  A change here is
#: a conscious act, not an accident.
EXPECTED_SITES = {
    "cloud/auth.py": 1,
    "cloud/job.py": 1,
    "providers/braket_provider.py": 1,
    "providers/ionq_provider.py": 2,
    "providers/rigetti_provider.py": 1,
    "quantum_sim.py": 16,
}


def _tls_src() -> str:
    return TLS_PATH.read_text(encoding="utf-8")


def _tls_mod():
    root = str(QUANTUM.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from quantum import tls

    return tls


def _quantum_modules() -> list[Path]:
    return sorted(
        p for p in QUANTUM.rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "tls.py"
    )


def _is_urlopen(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "urlopen"
    return isinstance(func, ast.Name) and func.id == "urlopen"


def _urlopen_sites(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _is_urlopen(n)]


# ---------------------------------------------------------------------------
# The shared policy module
# ---------------------------------------------------------------------------

class TestTlsModule:
    def test_exists_and_has_section1_header(self):
        assert TLS_PATH.is_file()
        src = _tls_src()
        assert "GNU General Public License" in src
        assert "https://www.gnu.org/licenses/" in src
        assert AUTHOR in src
        assert CANON in src
        assert "from __future__ import annotations" in src

    def test_exports_the_policy(self):
        tls = _tls_mod()
        assert callable(tls.tls_context)
        assert callable(tls.reset_tls_context)
        assert tls.CAFILE_ENV == "UMEROS_TLS_CAFILE"
        assert tls.MINIMUM_TLS_VERSION >= ssl.TLSVersion.TLSv1_2

    def test_returns_ssl_context(self):
        assert isinstance(_tls_mod().tls_context(), ssl.SSLContext)

    def test_cert_required(self):
        assert _tls_mod().tls_context().verify_mode == ssl.CERT_REQUIRED

    def test_check_hostname(self):
        assert _tls_mod().tls_context().check_hostname is True

    def test_minimum_version(self):
        assert _tls_mod().tls_context().minimum_version >= ssl.TLSVersion.TLSv1_2

    def test_context_is_cached(self):
        tls = _tls_mod()
        assert tls.tls_context() is tls.tls_context()

    def test_reset_clears_the_cache(self):
        tls = _tls_mod()
        first = tls.tls_context()
        tls.reset_tls_context()
        second = tls.tls_context()
        assert first is not second
        assert second.verify_mode == ssl.CERT_REQUIRED

    def test_no_unverified_path_in_code(self):
        """No ``ssl.CERT_NONE`` / ``_create_unverified_context`` anywhere."""
        offenders = []
        for path in sorted(QUANTUM.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in (
                    "CERT_NONE", "_create_unverified_context"
                ):
                    offenders.append(f"{path.name}:{node.lineno} {node.attr}")
                if isinstance(node, ast.Name) and node.id == "CERT_NONE":
                    offenders.append(f"{path.name}:{node.lineno} bare CERT_NONE")
        assert not offenders, "unverified TLS in code: " + "; ".join(offenders)

    def test_bad_cafile_fails_closed(self, monkeypatch, tmp_path):
        """A broken pin must not silently fall back to the system store."""
        tls = _tls_mod()
        tls.reset_tls_context()
        monkeypatch.setenv(tls.CAFILE_ENV, str(tmp_path / "missing-ca.pem"))
        try:
            with pytest.raises(RuntimeError) as excinfo:
                tls.tls_context()
            message = str(excinfo.value)
            assert tls.CAFILE_ENV in message
            assert "fall back" in message
        finally:
            tls.reset_tls_context()

    def test_good_cafile_is_accepted(self, monkeypatch):
        """A real CA bundle in the env var is loaded and logged."""
        cafile = ssl.get_default_verify_paths().cafile
        if not cafile or not os.path.exists(cafile):
            # Windows Python usually has no OpenSSL default bundle; certifi
            # ships one and is installed as a requests dependency.
            try:
                import certifi

                cafile = certifi.where()
            except Exception:  # pragma: no cover - no bundle on this host
                pytest.skip("no CA bundle discoverable on this platform")
        if not cafile or not os.path.exists(cafile):
            pytest.skip("no CA bundle discoverable on this platform")
        tls = _tls_mod()
        tls.reset_tls_context()
        monkeypatch.setenv(tls.CAFILE_ENV, cafile)
        try:
            ctx = tls.tls_context()
            assert ctx.verify_mode == ssl.CERT_REQUIRED
            assert ctx.check_hostname is True
        finally:
            tls.reset_tls_context()


# ---------------------------------------------------------------------------
# Every call site uses the policy
# ---------------------------------------------------------------------------

class TestEveryUrlopenIsPinned:
    def test_no_bare_urlopen_anywhere(self):
        offenders = []
        for path in _quantum_modules():
            for call in _urlopen_sites(path):
                keywords = {kw.arg for kw in call.keywords}
                if "context" not in keywords:
                    rel = path.relative_to(QUANTUM.parent).as_posix()
                    offenders.append(f"{rel}:{call.lineno}")
        assert not offenders, (
            "urlopen without context= (would use the platform default): "
            + ", ".join(offenders)
        )

    def test_expected_site_counts(self):
        for rel, expected in EXPECTED_SITES.items():
            path = QUANTUM / rel
            assert len(_urlopen_sites(path)) == expected, (
                f"{rel}: expected {expected} urlopen call(s), "
                f"found {len(_urlopen_sites(path))}"
            )

    def test_context_is_the_shared_helper(self):
        for rel in EXPECTED_SITES:
            src = (QUANTUM / rel).read_text(encoding="utf-8")
            assert "tls_context" in src, f"{rel} must use quantum.tls.tls_context"

    def test_providers_import_from_parent_package(self):
        for rel in (
            "providers/braket_provider.py",
            "providers/ionq_provider.py",
            "providers/rigetti_provider.py",
        ):
            assert "from ..tls import tls_context" in (QUANTUM / rel).read_text(
                encoding="utf-8"
            ), f"{rel} must import tls_context from quantum.tls"

    def test_quantum_sim_imports_the_helper(self):
        src = (QUANTUM / "quantum_sim.py").read_text(encoding="utf-8")
        assert "from .tls import tls_context" in src


# ---------------------------------------------------------------------------
# auth.py delegates; session.py cannot bypass
# ---------------------------------------------------------------------------

class TestAuthDelegates:
    def test_auth_alias_returns_the_shared_context(self):
        root = str(QUANTUM.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from quantum.cloud import auth
        from quantum import tls

        assert auth._tls_context() is tls.tls_context()

    def test_auth_source_delegates(self):
        src = (QUANTUM / "cloud" / "auth.py").read_text(encoding="utf-8")
        assert "return tls_context()" in src

    def test_auth_urlopen_still_passes_context(self):
        src = (QUANTUM / "cloud" / "auth.py").read_text(encoding="utf-8")
        assert "context=_tls_context()" in src


class TestSessionCannotBypass:
    def test_session_has_no_local_urlopen(self):
        """AST, not a text grep: a comment may legitimately say "urlopen"."""
        tree = ast.parse((QUANTUM / "cloud" / "session.py").read_text(encoding="utf-8"))
        calls = [n.lineno for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and _is_urlopen(n)]
        assert calls == [], f"session.py calls urlopen directly at {calls}"

        urllib_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                urllib_imports += [a.name for a in node.names if a.name.startswith("urllib")]
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").startswith("urllib"):
                    urllib_imports.append(node.module)
        assert urllib_imports == [], f"session.py imports urllib: {urllib_imports}"
