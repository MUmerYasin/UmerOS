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
UmerOS — driver-service smoke test
==================================
Starts ``drivers.driver_service`` under uvicorn in explicit dev-auth mode,
waits for it to actually answer, mints a short-lived HS256 token from the
*same* secret the service is handed, and asserts that ``/cpuinfo`` answers
200 — plus that a token signed with a different secret, and no token at all,
are both rejected with 401.

The secret is never a literal.  ``drivers.driver_service`` removed its
hardcoded ``"test-secret"`` fallback in favour of a fail-closed posture
(``UMEROS_DEV_AUTH=1`` + a real ``UMEROS_DEV_JWT_SECRET``, or RS256 against an
OIDC JWKS).  A smoke test that re-introduces that literal would sign tokens
with a value the service no longer trusts — and, worse, would keep "passing"
while the service rejected everything, because a bare print of the status code
cannot tell success from failure.  So this harness takes the secret from the
environment, generates a fresh one per run when it is unset, and fails loudly.

Readiness is *polled*, not slept through.  There is no ``/health`` route: every
``/proc`` endpoint is wrapped in ``secure_endpoint`` (``verify_oauth_token`` +
``rate_limiter``), so the readiness signal is a **401** on ``/cpuinfo`` — it
proves the route is mounted *and* that the auth dependency is enforcing.  A
200 there would mean the gate is off, which is a security failure rather than a
slow start, and is reported as such.  The poll also watches the child process,
so a server that dies during startup fails in milliseconds with its log tail
instead of stalling for the whole timeout.

Run it as::

    UMEROS_DEV_JWT_SECRET=… python scripts/test_endpoint.py

Leaving the variable unset is fine — a random per-run secret is minted and
handed to both sides.  Requires ``uvicorn`` and ``python-jose``; exits 2 with a
clear message if either is missing.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import httpx

PROJ = Path(__file__).resolve().parent.parent

DEV_SECRET_ENV = "UMEROS_DEV_JWT_SECRET"
DEV_AUTH_ENV = "UMEROS_DEV_AUTH"

#: Claims the service falls back to in dev mode when ``OIDC_*`` is unset.
DEV_ISSUER = "test-issuer"
DEV_AUDIENCE = "test-audience"

#: Secrets that must never be used again.  The first entry is the literal this
#: harness used to hardcode; the rest are the usual placeholder defaults.
FORBIDDEN_SECRETS = frozenset({"test-secret", "secret", "changeme", "password"})

#: How long to wait for the server to answer before giving up, and how often
#: to ask.  The poll is deliberately cheap: unauthenticated requests are
#: rejected by ``verify_oauth_token`` before ``rate_limiter`` runs, so probing
#: does not consume the 20-per-minute budget the real checks need.
READY_TIMEOUT = float(os.getenv("UMEROS_SMOKE_READY_TIMEOUT", "30"))
READY_INTERVAL = float(os.getenv("UMEROS_SMOKE_READY_INTERVAL", "0.25"))

#: Per-probe request timeout — short, so one hung attempt cannot eat the budget.
PROBE_TIMEOUT = float(os.getenv("UMEROS_SMOKE_PROBE_TIMEOUT", "2"))

HOST = "127.0.0.1"
PORT = int(os.getenv("UMEROS_SMOKE_PORT", "8000"))
BASE_URL = f"http://{HOST}:{PORT}"
TOKEN_TTL = 300


class SmokeTestError(RuntimeError):
    """Raised when the harness cannot set up, or the server never becomes ready."""


class ServerHandle:
    """A spawned ``driver_service`` plus the log file its output is written to.

    Output goes to a temporary **file**, not a ``subprocess.PIPE``: a pipe
    nobody drains deadlocks the child once the OS buffer fills, and on failure
    we want the tail of the log to explain why the server never came up.
    """

    def __init__(self, proc, log):
        self.proc = proc
        self._log = log

    @property
    def returncode(self):
        return self.proc.returncode

    def poll(self):
        return self.proc.poll()

    def log_tail(self, limit: int = 2000) -> str:
        """Return the last ``limit`` characters of server output."""
        try:
            self._log.seek(0)
            data = self._log.read()
        except (OSError, ValueError):
            return ""
        if isinstance(data, bytes):
            data = data.decode("utf-8", "replace")
        return data[-limit:].strip()

    def stop(self, timeout: float = 10.0) -> None:
        """Terminate, then kill if it will not go quietly."""
        if self.proc.poll() is None:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=timeout)
        try:
            self._log.close()
        except (OSError, ValueError):
            pass


def resolve_dev_secret(env: Optional[dict] = None) -> str:
    """Return the dev-mode JWT secret to use for *both* sides of the smoke test.

    Preference order: an explicit ``UMEROS_DEV_JWT_SECRET`` from the
    environment, otherwise a fresh ``secrets.token_urlsafe`` per run.  There is
    deliberately **no** literal fallback: a hardcoded default is a credential
    that ships with the source tree and authenticates against any deployment
    that fails to override it.
    """
    source = os.environ if env is None else env
    value = (source.get(DEV_SECRET_ENV) or "").strip()
    if value:
        if value in FORBIDDEN_SECRETS:
            raise SmokeTestError(
                f"{DEV_SECRET_ENV} is set to the retired placeholder {value!r}. "
                "Pick a real secret, or unset it to have one generated per run."
            )
        return value
    return secrets.token_urlsafe(32)


def build_server_env(secret: str, base: Optional[dict] = None) -> dict:
    """Environment for the uvicorn subprocess.

    Forces the service into ``dev`` auth mode and pins it to ``secret``.  Any
    inherited ``OIDC_*`` variables are dropped: if they survived, the service
    would boot into ``oidc`` mode and expect RS256, while this harness signs
    HS256 — a confusing 401 that looks like a bug in the service rather than a
    misconfigured harness.
    """
    env = dict(os.environ if base is None else base)
    for key in [k for k in env if k.startswith("OIDC_")]:
        del env[key]
    env[DEV_AUTH_ENV] = "1"
    env[DEV_SECRET_ENV] = secret
    return env


def generate_test_jwt(secret: str, sub: str = "smoke-test") -> str:
    """Mint an HS256 token signed with ``secret``.

    ``secret`` is positional and required — there is no default to fall back
    on, so a caller cannot accidentally mint a token with a built-in value.
    Uses ``python-jose``, the same library ``drivers.driver_service`` verifies
    with, so the harness is not exercising a second, differently-behaved JWT
    implementation.
    """
    if not secret:
        raise SmokeTestError("refusing to mint a token with an empty secret")
    if secret in FORBIDDEN_SECRETS:
        raise SmokeTestError(f"refusing to mint a token with {secret!r}")
    from jose import jwt as jose_jwt

    claims = {
        "sub": sub,
        "iss": DEV_ISSUER,
        "aud": DEV_AUDIENCE,
        "exp": int(time.time()) + TOKEN_TTL,
    }
    return jose_jwt.encode(claims, secret, algorithm="HS256")


def start_app(env: Optional[dict] = None) -> ServerHandle:
    """Launch ``drivers.driver_service`` under uvicorn and return a handle."""
    try:
        import uvicorn  # noqa: F401 - presence check only
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SmokeTestError(
            "uvicorn is not installed; install it with `pip install uvicorn` "
            "to run the socket-level smoke test."
        ) from exc

    log = tempfile.TemporaryFile()
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "drivers.driver_service:app",
            "--host", HOST, "--port", str(PORT), "--log-level", "warning",
        ],
        cwd=str(PROJ),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return ServerHandle(proc, log)


def wait_until_ready(server, timeout: Optional[float] = None,
                     interval: Optional[float] = None) -> float:
    """Block until the service answers; return the seconds it took.

    The probe is an **unauthenticated** ``GET /cpuinfo``.  Because every route
    is wrapped in ``secure_endpoint``, the expected answer is ``401``: that
    proves the app is up, the route is mounted, and authentication is being
    enforced.  ``200`` means the gate is off — reported as a security failure
    rather than a slow start.  ``404`` and connection errors just mean "not yet".

    Raises ``SmokeTestError`` if the process exits, if a 200 comes back, or if
    the deadline passes.  The message carries the server's log tail.
    """
    timeout = READY_TIMEOUT if timeout is None else timeout
    interval = READY_INTERVAL if interval is None else interval
    started = time.monotonic()
    deadline = started + timeout
    last = "no attempt"

    while time.monotonic() < deadline:
        code = server.poll()
        if code is not None:
            raise SmokeTestError(
                f"server exited with code {code} before becoming ready\n"
                f"--- server log ---\n{server.log_tail()}"
            )
        try:
            status = httpx.get(f"{BASE_URL}/cpuinfo", timeout=PROBE_TIMEOUT).status_code
        except httpx.HTTPError as exc:
            last = f"{type(exc).__name__}"
        else:
            if status == 401:
                return time.monotonic() - started
            if status == 200:
                raise SmokeTestError(
                    "the service answered /cpuinfo without a token — "
                    "secure_endpoint is not enforcing authentication"
                )
            last = f"HTTP {status}"
        time.sleep(interval)

    raise SmokeTestError(
        f"server did not become ready within {timeout:g}s (last: {last})\n"
        f"--- server log ---\n{server.log_tail()}"
    )


def call_cpuinfo(token: Optional[str], timeout: float = 10.0) -> int:
    """GET ``/cpuinfo`` with an optional bearer token; return the status code."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        return httpx.get(f"{BASE_URL}/cpuinfo", headers=headers, timeout=timeout).status_code
    except httpx.HTTPError as exc:
        raise SmokeTestError(f"could not reach {BASE_URL}/cpuinfo: {exc}") from exc


def _report(label: str, expected: int, actual: int) -> bool:
    ok = actual == expected
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: expected {expected}, got {actual}")
    return ok


def main() -> int:
    """Return 0 on success, 1 if a check failed, 2 if the test bed is unusable."""
    try:
        secret = resolve_dev_secret()
        env = build_server_env(secret)
        valid = generate_test_jwt(secret)
        forged = generate_test_jwt(secrets.token_urlsafe(32))
        server = start_app(env)
    except SmokeTestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    results: list = []
    try:
        elapsed = wait_until_ready(server)
        print(f"server ready after {elapsed:.2f}s")
        results.append(_report("valid token", 200, call_cpuinfo(valid)))
        results.append(_report("token signed with another secret", 401, call_cpuinfo(forged)))
        results.append(_report("no token", 401, call_cpuinfo(None)))
    except SmokeTestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        server.stop()

    if all(results):
        print("smoke test: OK")
        return 0
    print(f"smoke test: {results.count(False)} of {len(results)} checks FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
