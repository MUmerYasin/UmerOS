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
Regression tests for the /drivers /proc API fail-closed authentication (H64).

Covers ``drivers/driver_service.py``:

* The legacy hardcoded static HS256 secret ("test-secret") has been removed.
  A token signed with that literal is now REJECTED.
* When OIDC (JWKS_URL/ISSUER) is unconfigured and no explicit dev opt-in is
  set, the API refuses to start (fail-closed) and rejects every token.
* The Prometheus ``/metrics`` endpoint is no longer unauthenticated.
* ``/pid/{pid}/environ`` requires authentication AND a 'proc:environ:read'
  scope (owner/ptrace-style authorization proxy for process secrets).

NOTE: ``driver_service.py`` references a ``proc.pid_*`` API that no longer
exists in this codebase, so the four missing modules are stubbed before
import. That is out of H64 scope; these tests exercise only the auth layer.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest
from jose import jwt as jose_jwt

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_DEV_SECRET = "explicit-non-default-dev-secret-ZZ9"
_ISS = "test-issuer"
_AUD = "test-audience"


# ---------------------------------------------------------------------------
# Module loading in a chosen auth mode
# ---------------------------------------------------------------------------

def _stub_proc_modules() -> None:
    """Inject the four orphaned proc.pid_* modules the service imports."""
    for name in ("proc.pid_status", "proc.pid_cmdline", "proc.pid_environ", "proc.pid_fd"):
        mod = types.ModuleType(name)
        mod.get = lambda *a, **k: {}          # type: ignore[assignment]
        mod.list_fds = lambda *a, **k: [1]     # type: ignore[assignment]
        sys.modules[name] = mod
    pe = types.ModuleType("proc.pid_entries")
    pe.list_all = lambda *a, **k: [1]          # type: ignore[assignment]
    sys.modules["proc.pid_entries"] = pe


def _load_driver_service(env: dict):
    """Import driver_service freshly in the given auth-environment.

    Unregisters the module-level Prometheus ``Counter`` before re-import so a
    second import in the same process does not raise DuplicateTimeseries. The
    orphaned ``proc.pid_*`` modules are stubbed ONLY for this import, then the
    original ``sys.modules`` state is restored so other test modules that use
    the real ``proc`` package are not polluted.
    """
    previous = sys.modules.get("drivers.driver_service")
    if previous is not None:
        try:
            from prometheus_client import REGISTRY
            REGISTRY.unregister(previous.REQUEST_COUNT)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass

    # Snapshot sys.modules so we can restore it afterwards (no global pollution).
    saved = {k: sys.modules[k] for k in list(sys.modules) if k.startswith("proc.pid")}

    for key in list(sys.modules):
        if key == "drivers" or key.startswith("drivers.") or key.startswith("proc.pid"):
            del sys.modules[key]

    for var in [v for v in os.environ if v.startswith(("OIDC_", "UMEROS_"))]:
        del os.environ[var]
    os.environ.update(env)

    _stub_proc_modules()
    import drivers.driver_service as module  # imported fresh per mode

    # Restore sys.modules: drop our injected stubs, bring back any real proc.pid_*
    # modules that existed before this call. driver_service already bound the stub
    # names it needs, so removing the stubs from sys.modules is safe.
    for key in list(sys.modules):
        if key.startswith("proc.pid") and key not in saved:
            del sys.modules[key]
    for key, mod in saved.items():
        sys.modules[key] = mod

    return module


def _sign_token(secret: str = _DEV_SECRET, scope=None, sub: str = "tester") -> str:
    claims = {"sub": sub, "iss": _ISS, "aud": _AUD}
    if scope is not None:
        claims["scope"] = scope
    return jose_jwt.encode(claims, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Dev mode (explicit non-default secret) — the realistic local path
# ---------------------------------------------------------------------------

@pytest.fixture()
def dev_service():
    return _load_driver_service(
        {"UMEROS_DEV_AUTH": "1", "UMEROS_DEV_JWT_SECRET": _DEV_SECRET}
    )


class TestDevModeAuth:
    def test_valid_dev_token_reaches_proc(self, dev_service):
        from fastapi.testclient import TestClient
        token = _sign_token()
        with TestClient(dev_service.app) as client:
            resp = client.get("/cpuinfo", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_static_test_secret_is_rejected(self, dev_service):
        # [FIX H64] The old hardcoded "test-secret" must no longer authenticate.
        from fastapi.testclient import TestClient
        legacy = _sign_token(secret="test-secret")
        with TestClient(dev_service.app) as client:
            resp = client.get("/cpuinfo", headers={"Authorization": f"Bearer {legacy}"})
        assert resp.status_code == 401

    def test_missing_token_is_rejected(self, dev_service):
        from fastapi.testclient import TestClient
        with TestClient(dev_service.app) as client:
            resp = client.get("/cpuinfo")
        assert resp.status_code == 401


class TestMetricsGated:
    def test_metrics_requires_auth(self, dev_service):
        # [FIX H64] /metrics was previously unauthenticated; it must now be gated.
        from fastapi.testclient import TestClient
        with TestClient(dev_service.app) as client:
            anon = client.get("/metrics")
            authed = client.get(
                "/metrics", headers={"Authorization": f"Bearer {_sign_token()}"}
            )
        assert anon.status_code == 401
        assert authed.status_code == 200
        assert b"http_requests_total" in authed.content


class TestEnvironScopeGate:
    def test_environ_requires_auth(self, dev_service):
        from fastapi.testclient import TestClient
        with TestClient(dev_service.app) as client:
            resp = client.get("/pid/1/environ")
        assert resp.status_code == 401

    def test_environ_requires_scope(self, dev_service):
        # [FIX H64] Authenticated but without the environ scope -> 403.
        from fastapi.testclient import TestClient
        token_no_scope = _sign_token(scope=None)
        with TestClient(dev_service.app) as client:
            resp = client.get(
                "/pid/1/environ", headers={"Authorization": f"Bearer {token_no_scope}"}
            )
        assert resp.status_code == 403

    def test_environ_with_scope_succeeds(self, dev_service):
        from fastapi.testclient import TestClient
        token_with_scope = _sign_token(scope="proc:environ:read")
        with TestClient(dev_service.app) as client:
            resp = client.get(
                "/pid/1/environ", headers={"Authorization": f"Bearer {token_with_scope}"}
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Fail-closed: OIDC unconfigured and no dev opt-in -> deny + refuse to start
# ---------------------------------------------------------------------------

class TestFailClosedDenied:
    def test_mode_is_denied_without_config(self):
        svc = _load_driver_service({})  # no OIDC_*, no UMEROS_*
        assert svc._AUTH_MODE == "denied"

    def test_every_token_rejected_in_denied_mode(self):
        svc = _load_driver_service({})
        from fastapi.testclient import TestClient
        # Startup guard should refuse to boot the API.
        with pytest.raises(RuntimeError):
            with TestClient(svc.app) as client:
                client.get("/cpuinfo", headers={"Authorization": f"Bearer {_sign_token()}"})

    def test_dev_mode_without_secret_refuses_to_start(self):
        # [FIX H64] Even dev mode must not run with an empty secret.
        with pytest.raises(RuntimeError):
            _load_driver_service({"UMEROS_DEV_AUTH": "1"})  # no UMEROS_DEV_JWT_SECRET


# ---------------------------------------------------------------------------
# OIDC (production) mode rejects the static HS256 secret by algorithm mismatch
# ---------------------------------------------------------------------------

class TestOidcMode:
    def test_static_secret_rejected_under_rs256(self):
        # Production verifies RS256 against JWKS; a HS256/"test-secret" token must
        # fail. We stub fetch_jwks so no network call is made.
        svc = _load_driver_service(
            {"OIDC_JWKS_URL": "https://idp.example.com/jwks", "OIDC_ISSUER": "https://idp.example.com"}
        )
        assert svc._AUTH_MODE == "oidc"

        async def fake_jwks():
            return {"keys": []}

        svc.fetch_jwks = fake_jwks
        legacy = _sign_token(secret="test-secret")
        # Direct async call proves the HS256/"test-secret" token is rejected
        # (jose expects RS256 against JWKS, so the static secret is never tried).
        import asyncio
        with pytest.raises(Exception):
            asyncio.run(svc.verify_oauth_token(legacy))
