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

"""H238 -- readiness must be polled, and the "forged token" claim re-checked.

The row (BLUE) says ``scripts/test_endpoint.py`` ``start_app``/``main``:

1. blocks ``time.sleep(3)`` and then *assumes* the server is up — flaky on slow
   CI, no readiness probe; and
2. hits ``/cpuinfo`` "with a forged ``Bearer`` token, bypassing whatever
   ``CapabilityManager``/auth the real app would enforce (the test only 'works'
   because the service is unauthenticated, H64)".

Drift-recon (session 224): **half 1 true, half 2 stale on three counts.**

* Half 1 was live and is fixed here.  There is no ``/health`` route to poll, and
  every ``/proc`` endpoint is wrapped in ``secure_endpoint`` — so the readiness
  signal is a **401** on ``/cpuinfo``, which proves the route is mounted *and*
  that auth is enforcing.  ``wait_until_ready`` polls it, watches the child
  process so a crashed server fails in milliseconds with its log tail, and
  bounds the whole thing with ``UMEROS_SMOKE_READY_TIMEOUT``.
* Half 2: the service is **not** unauthenticated.  ``/cpuinfo`` is
  ``Depends(secure_endpoint)``, which composes ``verify_oauth_token`` and
  ``rate_limiter``; ``tests/test_driver_service.py`` pins that an anonymous
  request is a 401 and that ``"test-secret"`` is rejected.  H64 fixed it, and
  H237 made the harness present a *real* dev-mode credential signed with the
  secret it hands the server — plus assertions that a token signed with another
  secret, and no token, are both 401.  So the token is not forged and the auth
  is not bypassed; it is exercised.
* The ``CapabilityManager`` part is stale too: ``drivers/driver_service.py``
  contains zero references to ``CapabilityManager``/``capability_gate``/
  ``SecuritySandbox``.  It is a userspace HTTP service, not a kernel IPC path.

The two premise-pinning tests at the bottom keep that honest.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
import types
from pathlib import Path

import httpx
import pytest

PROJ = Path(__file__).resolve().parent.parent
if str(PROJ) not in sys.path:
    sys.path.insert(0, str(PROJ))

SCRIPT = PROJ / "scripts" / "test_endpoint.py"
SERVICE = PROJ / "drivers" / "driver_service.py"


def _load():
    spec = importlib.util.spec_from_file_location("_h238_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def smoke():
    return _load()


@pytest.fixture(scope="module")
def src() -> str:
    return SCRIPT.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------

class _StubServer:
    """Minimal ``ServerHandle`` stand-in: scripted exit codes and log output."""

    def __init__(self, exit_codes=None, log=""):
        self._codes = list(exit_codes or [])
        self._log = log
        self.stopped = False

    def poll(self):
        return self._codes.pop(0) if self._codes else None

    def log_tail(self, limit=2000):
        return self._log[-limit:]

    def stop(self, timeout=10.0):
        self.stopped = True


class _Clock:
    """Deterministic ``time.monotonic`` so the timeout test cannot flake."""

    def __init__(self, step=0.5):
        self.now = 0.0
        self.step = step

    def monotonic(self):
        self.now += self.step
        return self.now


def _stub_httpx(monkeypatch, smoke, outcomes):
    """Serve a scripted sequence of status codes / exceptions from ``httpx.get``."""
    queue = list(outcomes)
    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        assert queue, "wait_until_ready() probed more times than scripted"
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return types.SimpleNamespace(status_code=item)

    monkeypatch.setattr(smoke.httpx, "get", fake_get)
    return calls


@pytest.fixture()
def quiet(monkeypatch, smoke):
    """No real sleeping."""
    monkeypatch.setattr(smoke.time, "sleep", lambda s: None)


# ---------------------------------------------------------------------------
# Half 1: readiness is polled, not slept through
# ---------------------------------------------------------------------------

class TestReadinessProbe:
    def test_returns_on_the_first_401(self, smoke, monkeypatch, quiet):
        calls = _stub_httpx(monkeypatch, smoke, [401])
        elapsed = smoke.wait_until_ready(_StubServer(), timeout=5)
        assert elapsed >= 0
        assert len(calls) == 1

    def test_polls_through_connection_errors_and_404s(self, smoke, monkeypatch, quiet):
        """A server that is still starting is not a failure."""
        _stub_httpx(
            monkeypatch, smoke,
            [httpx.ConnectError("refused"), httpx.ReadTimeout("slow"), 404, 401],
        )
        smoke.wait_until_ready(_StubServer(), timeout=5)  # must not raise

    def test_a_200_without_a_token_is_a_security_failure(self, smoke, monkeypatch, quiet):
        """200 on a gated route means the gate is off — not "slow start"."""
        _stub_httpx(monkeypatch, smoke, [200])
        with pytest.raises(smoke.SmokeTestError, match="not enforcing authentication"):
            smoke.wait_until_ready(_StubServer(), timeout=5)

    def test_a_crashed_server_fails_fast_with_its_log(self, smoke, monkeypatch, quiet):
        """``denied`` mode raises at startup — report it, do not wait 30s."""
        _stub_httpx(monkeypatch, smoke, [401, 401, 401])
        server = _StubServer(exit_codes=[1], log="RuntimeError: authentication is not configured")
        with pytest.raises(smoke.SmokeTestError) as excinfo:
            smoke.wait_until_ready(server, timeout=30)
        message = str(excinfo.value)
        assert "exited with code 1" in message
        assert "authentication is not configured" in message

    def test_timeout_is_bounded_and_reports_the_last_status(self, smoke, monkeypatch, quiet):
        clock = _Clock(step=0.5)
        monkeypatch.setattr(smoke.time, "monotonic", clock.monotonic)
        _stub_httpx(monkeypatch, smoke, [404, 404, 404, 404, 404, 404])
        with pytest.raises(smoke.SmokeTestError) as excinfo:
            smoke.wait_until_ready(_StubServer(), timeout=1.0)
        assert "did not become ready within 1s" in str(excinfo.value)
        assert "HTTP 404" in str(excinfo.value)

    def test_probe_carries_no_authorization_header(self, smoke, monkeypatch, quiet):
        """Readiness must be provable without a credential, or it proves nothing."""
        calls = _stub_httpx(monkeypatch, smoke, [404, 401])
        smoke.wait_until_ready(_StubServer(), timeout=5)
        for call in calls:
            assert "headers" not in call or "Authorization" not in call.get("headers", {})

    def test_probe_hits_the_gated_route(self, smoke, monkeypatch, quiet):
        calls = _stub_httpx(monkeypatch, smoke, [401])
        smoke.wait_until_ready(_StubServer(), timeout=5)
        assert calls[0]["url"].endswith("/cpuinfo")

    def test_interval_is_honoured(self, smoke, monkeypatch):
        """One sleep per unsuccessful probe, none after success."""
        sleeps = []
        monkeypatch.setattr(smoke.time, "sleep", lambda s: sleeps.append(s))
        _stub_httpx(monkeypatch, smoke, [404, 404, 401])
        smoke.wait_until_ready(_StubServer(), timeout=5, interval=0.123)
        assert sleeps == [0.123, 0.123]

    def test_timeouts_are_env_tunable_and_positive(self, smoke):
        assert smoke.READY_TIMEOUT > 0
        assert smoke.READY_INTERVAL > 0
        assert smoke.PROBE_TIMEOUT > 0
        assert smoke.READY_INTERVAL < smoke.READY_TIMEOUT


class TestNoFixedStartupSleep:
    def test_startup_delay_constant_is_gone(self, smoke, src):
        """The row's literal complaint: a fixed 3-second settle."""
        assert not hasattr(smoke, "STARTUP_DELAY"), (
            "STARTUP_DELAY is back; readiness must be polled, not slept through"
        )
        assert "STARTUP_DELAY" not in src

    def test_main_waits_before_it_asserts(self, smoke, monkeypatch):
        order = []
        server = _StubServer()

        monkeypatch.setattr(smoke, "start_app", lambda env: server)
        monkeypatch.setattr(
            smoke, "wait_until_ready",
            lambda srv, **kwargs: order.append("ready") or 0.0,
        )
        monkeypatch.setattr(
            smoke, "call_cpuinfo",
            lambda token, timeout=10.0: order.append("probe") or 200,
        )
        monkeypatch.setattr(smoke, "_report", lambda *a, **k: True)
        smoke.main()
        assert order[0] == "ready", f"readiness must come first, got {order}"

    def test_readiness_failure_is_a_setup_error(self, smoke, monkeypatch):
        server = _StubServer()

        def never_ready(srv, **kwargs):
            raise smoke.SmokeTestError("did not become ready")

        monkeypatch.setattr(smoke, "start_app", lambda env: server)
        monkeypatch.setattr(smoke, "wait_until_ready", never_ready)
        assert smoke.main() == 2
        assert server.stopped, "the server must be torn down even when readiness fails"


# ---------------------------------------------------------------------------
# The subprocess must not be able to deadlock
# ---------------------------------------------------------------------------

class TestServerHandle:
    def test_start_app_redirects_output_to_a_file_not_a_pipe(self, smoke, monkeypatch):
        """An undrained PIPE deadlocks the child once the buffer fills."""
        monkeypatch.setitem(sys.modules, "uvicorn", types.ModuleType("uvicorn"))
        captured = {}

        def fake_popen(argv, **kwargs):
            captured["argv"] = argv
            captured.update(kwargs)
            return types.SimpleNamespace(returncode=None, poll=lambda: None,
                                         terminate=lambda: None, wait=lambda timeout=None: 0)

        monkeypatch.setattr(smoke.subprocess, "Popen", fake_popen)
        handle = smoke.start_app(smoke.build_server_env("s3cret", base={}))
        try:
            assert isinstance(handle, smoke.ServerHandle)
            assert captured["stdout"] is not subprocess.PIPE
            assert hasattr(captured["stdout"], "read"), "output must be readable for the log tail"
            assert captured["stderr"] == subprocess.STDOUT
        finally:
            handle.stop()

    def test_log_tail_decodes_bytes_and_truncates(self, smoke):
        import tempfile

        log = tempfile.TemporaryFile()
        log.write(b"x" * 5000 + b"\nRuntimeError: boom\n")
        log.flush()
        handle = smoke.ServerHandle(types.SimpleNamespace(), log)
        try:
            tail = handle.log_tail(limit=100)
            assert "RuntimeError: boom" in tail
            assert len(tail) <= 100
        finally:
            log.close()

    def test_stop_terminates_then_waits(self, smoke):
        state = {}

        class Proc:
            returncode = None

            def poll(self):
                return None

            def terminate(self):
                state["terminated"] = True

            def wait(self, timeout=None):
                state["waited"] = timeout
                return 0

        handle = smoke.ServerHandle(Proc(), types.SimpleNamespace(close=lambda: None))
        handle.stop(timeout=5)
        assert state.get("terminated") is True
        assert state.get("waited") == 5

    def test_stop_kills_a_server_that_will_not_die(self, smoke):
        state = {"kills": 0}

        class Proc:
            returncode = None

            def poll(self):
                return None

            def terminate(self):
                pass

            def wait(self, timeout=None):
                if not state["kills"]:
                    raise subprocess.TimeoutExpired(cmd="uvicorn", timeout=timeout)
                return 0

            def kill(self):
                state["kills"] += 1

        handle = smoke.ServerHandle(Proc(), types.SimpleNamespace(close=lambda: None))
        handle.stop(timeout=1)
        assert state["kills"] == 1


# ---------------------------------------------------------------------------
# Half 2: pin the facts that make the "forged token / no auth" claim stale
# ---------------------------------------------------------------------------

class TestPremiseIsStale:
    def test_cpuinfo_is_auth_gated(self):
        """The row says the test "only works because the service is unauthenticated"."""
        tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
        handler = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "endpoint_cpuinfo":
                handler = node
        assert handler is not None, "/cpuinfo handler not found"
        defaults = [ast.unparse(d) for d in handler.args.defaults]
        assert any("secure_endpoint" in d for d in defaults), (
            f"/cpuinfo is no longer gated by secure_endpoint: {defaults}"
        )

    def test_secure_endpoint_composes_auth_and_rate_limiting(self):
        source = SERVICE.read_text(encoding="utf-8")
        assert "def secure_endpoint(" in source
        start = source.index("def secure_endpoint(")
        signature = source[start:source.index("):", start) + 2]
        assert "verify_oauth_token" in signature, signature
        assert "rate_limiter" in signature, signature

    def test_service_has_no_capability_manager_to_bypass(self):
        """``CapabilityManager`` is a kernel concept; this is a userspace service."""
        source = SERVICE.read_text(encoding="utf-8")
        for name in ("CapabilityManager", "capability_gate", "SecuritySandbox"):
            assert name not in source, (
                f"{name} now appears in driver_service — re-check H238's framing"
            )
