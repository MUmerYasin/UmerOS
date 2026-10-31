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

"""H237 -- the smoke harness must not re-introduce the retired shared secret.

The row says ``scripts/test_endpoint.py:17-26`` ``generate_test_jwt`` hardcodes
``secret = "test-secret"``, "the **same** trusted secret as
``drivers.driver_service`` (H64)", so the harness "legitimates the broken auth
and would PASS against the vulnerable service, masking H64".

Drift-recon (session 223): premise **half stale, and the surviving half is
worse than described** --

* H64 is **already fixed**.  ``drivers/driver_service.py`` has no static HS256
  secret at all: it is ``oidc`` (RS256 via JWKS) / ``dev`` (HS256 with an
  explicit ``UMEROS_DEV_JWT_SECRET``) / ``denied`` (refuses to boot), and
  ``tests/test_driver_service.py::TestDevModeAuth::test_static_test_secret_is_rejected``
  already pins that ``"test-secret"`` no longer authenticates.  So the literal
  is *not* "the same trusted secret" any more -- it authenticates against
  nothing.
* That makes the harness **worse** than the row says: it signed with a secret
  the service rejects, never set ``UMEROS_DEV_AUTH``/``UMEROS_DEV_JWT_SECRET``
  on the server it spawned (so the service came up ``denied`` and refused to
  boot), imported PyJWT while the service verifies with python-jose, and
  **asserted nothing** -- it printed the status code and exited 0 whatever
  happened.  Run today it dies at ``import jwt`` (PyJWT is not installed).
  The masking mechanism was never the shared secret; it was the absent
  assertion.
* ``uvicorn`` is not installed either, so the socket path cannot run here.

Fix: the secret comes from ``UMEROS_DEV_JWT_SECRET`` or is generated per run
with ``secrets.token_urlsafe``; the retired placeholders are refused outright;
the same secret is pushed into the uvicorn subprocess env (with ``OIDC_*``
stripped so the service cannot drift into RS256 mode); tokens are minted with
``python-jose`` -- the library the service verifies with; and the harness now
asserts valid-token 200, **forged-token 401** and no-token 401, returning
non-zero if any check fails.

``time.sleep`` readiness and the forged-token/capability-gate analysis are
H238's scope and deliberately untouched here.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import types
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
if str(PROJ) not in sys.path:
    sys.path.insert(0, str(PROJ))

SCRIPT = PROJ / "scripts" / "test_endpoint.py"
SERVICE = PROJ / "drivers" / "driver_service.py"

RETIRED = "test-secret"


def _load():
    """Import ``scripts/test_endpoint.py`` by path (``scripts/`` is not a package)."""
    spec = importlib.util.spec_from_file_location("_h237_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def smoke():
    return _load()


@pytest.fixture(scope="module")
def src() -> str:
    return SCRIPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tree(src) -> ast.Module:
    return ast.parse(src)


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name}() not found")


# ---------------------------------------------------------------------------
# The literal must be gone -- and must be unable to come back
# ---------------------------------------------------------------------------

class TestNoHardcodedSecret:
    def test_the_retired_literal_is_not_assigned_anywhere(self, tree):
        """No ``<name containing 'secret'> = "literal"`` anywhere in the module.

        Names ending in ``_ENV`` are exempt: they hold the *name* of an
        environment variable (``DEV_SECRET_ENV = "UMEROS_DEV_JWT_SECRET"``),
        not a credential value.
        """
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            else:
                continue
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            for t in targets:
                if not isinstance(t, ast.Name):
                    continue
                if "secret" in t.id.lower() and not t.id.endswith("_ENV"):
                    offenders.append(f"{t.id} = {value.value!r} (line {node.lineno})")
        assert offenders == [], (
            f"credential literal assigned in the harness: {offenders}"
        )

    def test_denylisted_literals_live_only_in_the_denylist(self, tree):
        """Every retired placeholder may appear *only* inside ``FORBIDDEN_SECRETS``.

        This is the structural form of the row's complaint: the old harness had
        ``secret = "test-secret"`` as a live value.  Here the same string may
        exist exactly once, as an entry in the deny list.
        """
        denied = {"test-secret", "secret", "changeme", "password"}
        spans = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            if any(isinstance(t, ast.Name) and t.id == "FORBIDDEN_SECRETS" for t in targets):
                spans.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
        assert spans, "FORBIDDEN_SECRETS is not defined at module level"

        def inside_a_denylist(lineno: int) -> bool:
            return any(lo <= lineno <= hi for lo, hi in spans)

        stray = [
            f"line {n.lineno}: {n.value!r}"
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and n.value in denied
            and not inside_a_denylist(n.lineno)
        ]
        assert stray == [], f"retired credential literal outside the denylist: {stray}"

    def test_generate_test_jwt_has_no_default_secret(self, tree):
        """``secret`` must be required, so no built-in value can be used."""
        fn = _func(tree, "generate_test_jwt")
        args = fn.args
        positional = [a.arg for a in args.args]
        assert positional[0] == "secret", positional
        # len(defaults) counts from the right: with 2 positional params and 1
        # default, only the last one has one -- so ``secret`` cannot.
        assert len(args.defaults) == len(positional) - 1, (
            f"generate_test_jwt() gives a default to {positional[:len(positional) - len(args.defaults)]} "
            "-- the secret must be required"
        )

    def test_retired_literals_are_denylisted(self, smoke):
        assert RETIRED in smoke.FORBIDDEN_SECRETS
        assert {"secret", "changeme", "password"} <= set(smoke.FORBIDDEN_SECRETS)

    def test_source_mentions_the_retired_literal_only_as_a_denylist_entry(self, src):
        """It may appear in the denylist and in prose, never in a call."""
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for arg in list(node.args) + [k.value for k in node.keywords]:
                    assert not (
                        isinstance(arg, ast.Constant) and arg.value == RETIRED
                    ), f"the retired literal is passed to {getattr(node.func, 'id', '?')}() at line {node.lineno}"


# ---------------------------------------------------------------------------
# Secret sourcing
# ---------------------------------------------------------------------------

class TestSecretResolution:
    def test_generated_when_unset(self, smoke):
        value = smoke.resolve_dev_secret({})
        assert isinstance(value, str) and len(value) >= 32

    def test_two_runs_do_not_share_a_secret(self, smoke):
        assert smoke.resolve_dev_secret({}) != smoke.resolve_dev_secret({})

    def test_environment_value_is_honoured_and_stripped(self, smoke):
        assert smoke.resolve_dev_secret({smoke.DEV_SECRET_ENV: "  abc123  "}) == "abc123"

    @pytest.mark.parametrize("bad", sorted({"test-secret", "secret", "changeme", "password"}))
    def test_retired_placeholders_are_refused(self, smoke, bad):
        with pytest.raises(smoke.SmokeTestError):
            smoke.resolve_dev_secret({smoke.DEV_SECRET_ENV: bad})

    def test_empty_environment_value_falls_back_to_generation(self, smoke):
        """An empty ``UMEROS_DEV_JWT_SECRET`` must not become an empty secret."""
        value = smoke.resolve_dev_secret({smoke.DEV_SECRET_ENV: "   "})
        assert value and value.strip() == value


# ---------------------------------------------------------------------------
# Both sides must be handed the same secret
# ---------------------------------------------------------------------------

class TestServerEnv:
    def test_forces_dev_auth(self, smoke):
        env = smoke.build_server_env("s3cret", base={})
        assert env[smoke.DEV_AUTH_ENV] == "1"

    def test_propagates_the_secret(self, smoke):
        assert smoke.build_server_env("s3cret", base={})[smoke.DEV_SECRET_ENV] == "s3cret"

    def test_strips_inherited_oidc_variables(self, smoke):
        env = smoke.build_server_env(
            "s3cret",
            base={"OIDC_JWKS_URL": "https://x", "OIDC_ISSUER": "i", "OIDC_AUDIENCE": "a"},
        )
        assert [k for k in env if k.startswith("OIDC_")] == []

    def test_preserves_unrelated_variables(self, smoke):
        assert smoke.build_server_env("s3cret", base={"PATH": "/usr/bin"})["PATH"] == "/usr/bin"

    def test_does_not_mutate_the_caller_s_environment(self, smoke):
        base = {"OIDC_ISSUER": "i", "PATH": "/usr/bin"}
        smoke.build_server_env("s3cret", base=base)
        assert base == {"OIDC_ISSUER": "i", "PATH": "/usr/bin"}

    def test_start_app_passes_the_env_to_the_subprocess(self, smoke, monkeypatch):
        """The secret is useless if the spawned server never receives it."""
        monkeypatch.setitem(sys.modules, "uvicorn", types.ModuleType("uvicorn"))
        captured = {}

        def fake_popen(argv, **kwargs):
            captured["argv"] = argv
            captured.update(kwargs)
            return types.SimpleNamespace(terminate=lambda: None, wait=lambda timeout=None: 0)

        monkeypatch.setattr(smoke.subprocess, "Popen", fake_popen)
        env = smoke.build_server_env("s3cret", base={})
        smoke.start_app(env)
        assert captured.get("env") == env
        assert captured.get("cwd") == str(PROJ)
        assert "drivers.driver_service:app" in captured["argv"]


# ---------------------------------------------------------------------------
# Token minting agrees with what the service actually verifies
# ---------------------------------------------------------------------------

class TestTokenMinting:
    def test_round_trips_with_the_service_dev_claims(self, smoke):
        from jose import jwt as jose_jwt

        token = smoke.generate_test_jwt("s3cret")
        claims = jose_jwt.decode(
            token,
            "s3cret",
            algorithms=["HS256"],
            issuer=smoke.DEV_ISSUER,
            audience=smoke.DEV_AUDIENCE,
        )
        assert claims["sub"] == "smoke-test"
        assert claims["exp"] > 0

    def test_algorithm_is_hs256(self, smoke):
        from jose import jwt as jose_jwt

        assert jose_jwt.get_unverified_header(smoke.generate_test_jwt("s3cret"))["alg"] == "HS256"

    def test_uses_python_jose_not_pyjwt(self, src):
        assert "from jose import jwt" in src
        assert "\nimport jwt" not in src, "the service verifies with python-jose; use the same library"

    def test_claims_match_the_service_dev_fallbacks(self, smoke):
        """``verify_oauth_token`` falls back to these exact strings in dev mode."""
        service_src = SERVICE.read_text(encoding="utf-8")
        assert f'or "{smoke.DEV_ISSUER}"' in service_src, (
            "driver_service's dev-mode issuer fallback changed; update DEV_ISSUER"
        )
        assert f'or "{smoke.DEV_AUDIENCE}"' in service_src, (
            "driver_service's dev-mode audience fallback changed; update DEV_AUDIENCE"
        )

    @pytest.mark.parametrize("bad", ["", RETIRED])
    def test_refuses_to_mint_with_a_bad_secret(self, smoke, bad):
        with pytest.raises(smoke.SmokeTestError):
            smoke.generate_test_jwt(bad)

    def test_token_from_another_secret_does_not_verify(self, smoke):
        from jose import jwt as jose_jwt

        forged = smoke.generate_test_jwt(smoke.secrets.token_urlsafe(32))
        with pytest.raises(Exception):
            jose_jwt.decode(
                forged,
                "s3cret",
                algorithms=["HS256"],
                issuer=smoke.DEV_ISSUER,
                audience=smoke.DEV_AUDIENCE,
            )


# ---------------------------------------------------------------------------
# The decisive test: the harness must FAIL when a forged token is accepted
# ---------------------------------------------------------------------------

class _FakeServer:
    """Stands in for ``ServerHandle``; records teardown."""

    def __init__(self):
        self.stopped = False

    def poll(self):
        return None

    def log_tail(self, limit=2000):
        return ""

    def stop(self, timeout=10.0):
        self.stopped = True


def _drive(smoke, monkeypatch, statuses):
    """Run ``main()`` with the network, the subprocess and the readiness poll stubbed."""
    queue = list(statuses)
    server = _FakeServer()

    monkeypatch.setattr(smoke, "start_app", lambda env: server)
    # The readiness probe has its own tests; here we only care about the checks.
    monkeypatch.setattr(smoke, "wait_until_ready", lambda srv, **kwargs: 0.0)
    monkeypatch.setattr(smoke.time, "sleep", lambda s: None)

    def fake_call(token, timeout=10.0):
        assert queue, "main() made more requests than expected"
        return queue.pop(0)

    monkeypatch.setattr(smoke, "call_cpuinfo", fake_call)
    code = smoke.main()
    return code, server, queue


class TestHarnessActuallyAsserts:
    def test_passes_when_all_three_checks_hold(self, smoke, monkeypatch):
        code, server, leftover = _drive(smoke, monkeypatch, [200, 401, 401])
        assert code == 0
        assert leftover == []
        assert server.stopped, "the server subprocess must be torn down"

    def test_fails_when_a_forged_token_is_accepted(self, smoke, monkeypatch):
        """This is the H64 regression the old harness could not see.

        The second request is the token signed with a different secret.  If the
        service (or a stubbed stand-in) answers 200 to it, authentication is
        broken -- and the harness must exit non-zero rather than print and
        return 0.
        """
        code, _, _ = _drive(smoke, monkeypatch, [200, 200, 401])
        assert code == 1, "an accepted forged token must fail the smoke test"

    def test_fails_when_a_valid_token_is_rejected(self, smoke, monkeypatch):
        code, _, _ = _drive(smoke, monkeypatch, [401, 401, 401])
        assert code == 1

    def test_fails_when_an_anonymous_request_succeeds(self, smoke, monkeypatch):
        code, _, _ = _drive(smoke, monkeypatch, [200, 401, 200])
        assert code == 1

    def test_returns_two_when_the_harness_cannot_start(self, smoke, monkeypatch):
        """A missing dependency is a setup error, not a service failure."""
        def boom(env):
            raise smoke.SmokeTestError("uvicorn missing")

        monkeypatch.setattr(smoke, "start_app", boom)
        monkeypatch.setattr(smoke.time, "sleep", lambda s: None)
        assert smoke.main() == 2

    def test_report_returns_its_verdict(self, smoke, capsys):
        assert smoke._report("x", 200, 200) is True
        assert smoke._report("x", 200, 401) is False
        out = capsys.readouterr().out
        assert "[PASS] x: expected 200, got 200" in out
        assert "[FAIL] x: expected 200, got 401" in out


# ---------------------------------------------------------------------------
# The folder still satisfies H236
# ---------------------------------------------------------------------------

class TestStillOnTheSectionOneBaseline:
    def test_canonical_license_line_survives(self, src):
        assert "License: GPL-3.0 (GNU General Public License v3)" in src

    def test_future_annotations_still_first(self, tree):
        body = tree.body
        assert isinstance(body[0], ast.Expr)
        assert isinstance(body[1], ast.ImportFrom) and body[1].module == "__future__"

    def test_module_docstring_still_ends_with_the_trailer(self, tree):
        doc = ast.get_docstring(tree, clean=False)
        tail = [ln for ln in doc.strip().splitlines() if ln.strip()]
        assert tail[-2:] == [
            "Author:  Umer OS Project",
            "License: GPL-3.0 (GNU General Public License v3)",
        ]
