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
pytest suite for the antivirus REST API (H245).

H245: the aiohttp AV API on 127.0.0.1:9095 exposed destructive endpoints
(``POST /api/quarantine`` / ``/api/quarantine/delete``, realtime start/stop)
with no authn/authz. The remediation was applied with a broken indentation:
``create_app`` returned ``None`` and the route registrations were unreachable
dead code inside ``_auth_middleware``. These tests pin the correct shape:

  * ``create_app()`` returns an ``Application`` carrying the auth middleware
    and all routes;
  * when ``UMEROS_AV_API_TOKEN`` is set every route requires ``Bearer``;
  * destructive endpoints answer 403 (fail-closed) with no token;
  * destructive endpoints are also denied by the capability gate.
"""

import os
import sys
import unittest
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    import aiohttp  # noqa: F401
    from aiohttp.test_utils import TestClient, TestServer
    _AIOHTTP = True
except Exception:  # pragma: no cover - aiohttp optional
    _AIOHTTP = False


@unittest.skipUnless(_AIOHTTP, "aiohttp not installed")
class TestAvApiPosture(unittest.IsolatedAsyncioTestCase):
    """H245: AV API auth posture + destructive-endpoint fail-closed."""

    def setUp(self):
        self._saved = os.environ.pop("UMEROS_AV_API_TOKEN", None)

    def tearDown(self):
        os.environ.pop("UMEROS_AV_API_TOKEN", None)
        if self._saved is not None:
            os.environ["UMEROS_AV_API_TOKEN"] = self._saved

    async def _client(self):
        import security.antivirus.api_server as m
        client = TestClient(TestServer(m.create_app()))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return client

    def test_create_app_returns_application_with_routes_and_middleware(self):
        import security.antivirus.api_server as m
        app = m.create_app()
        self.assertIsNotNone(app, "create_app() must return the Application, not None")
        self.assertEqual(len(app.middlewares), 1, "auth middleware must be attached")
        routes = {
            r.resource.canonical
            for r in app.router.routes()
            if hasattr(r, "resource")
        }
        for path in (
            "/api/dashboard",
            "/api/scan/directory",
            "/api/quarantine",
            "/api/quarantine/delete",
            "/api/quarantine/restore",
            "/api/realtime/watch",
        ):
            self.assertIn(path, routes)

    async def test_all_routes_require_bearer_when_token_set(self):
        os.environ["UMEROS_AV_API_TOKEN"] = "sekret"
        client = await self._client()
        self.assertEqual((await client.get("/api/dashboard")).status, 401)
        ok = await client.get(
            "/api/dashboard", headers={"Authorization": "Bearer sekret"})
        self.assertEqual(ok.status, 200)

    async def test_destructive_route_forbidden_without_token(self):
        client = await self._client()
        r = await client.post("/api/quarantine/delete", json={"id": "x"})
        self.assertEqual(r.status, 403)

    async def test_readonly_route_ok_without_token(self):
        client = await self._client()
        self.assertEqual((await client.get("/api/dashboard")).status, 200)

    async def test_destructive_route_denied_by_cap_gate(self):
        from core.capability_gate import CapabilityGate
        from kernel.capability_manager import CapabilityManager
        import security.antivirus.api_server as m

        os.environ["UMEROS_AV_API_TOKEN"] = "sekret"
        cm = CapabilityManager()
        cm.register(os.getpid())  # registered but granted NOTHING
        g = CapabilityGate()
        g.wire(cm)
        prev = m.gate
        m.gate = g
        try:
            client = await self._client()
            r = await client.post(
                "/api/quarantine/delete",
                json={"id": "x"},
                headers={"Authorization": "Bearer sekret"},
            )
            self.assertEqual(r.status, 403)
        finally:
            m.gate = prev


if __name__ == "__main__":
    unittest.main()
