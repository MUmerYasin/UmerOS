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

"""H180 tests — DoH answers must not silently degrade to system DNS.

``network/network_stack.py::DNSOverHTTPS.resolve()`` queried two DoH endpoints
and, when both failed, silently fell back to the host resolver.  The caller
had asked for an authenticated answer and received a spoofable one — which is
exactly the answer that then feeds ``NetworkStack.connect()``.

Two distinct problems are pinned here:

1. **The silent fail-open.** The fallback is now opt-in
   (``allow_system_fallback=False``) and resolution fails closed instead.
2. **"DoH" was being mistaken for "authenticated".** DoH only hides the query
   behind TLS; **DNSSEC** is what authenticates the answer.  The ``AD``
   (authentic-data) bit is now parsed, exposed via ``dnssec_status()``, and
   enforceable with ``require_dnssec``.

Note on test mechanics: ``resolve()`` is synchronous and ``urlopen`` blocks
the calling thread, so calling it directly from inside an ``async`` test blocks
the event loop the fake DoH server needs in order to *accept* the connection.
Every assertion here therefore goes through ``resolve_async()`` (which already
runs ``resolve`` in an executor) or ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import json
import unittest

from network.network_stack import DNSOverHTTPS

#: A real DoH JSON A-record answer, DNSSEC-validated (``AD`` set).
DOH_AD = {
    "Status": 0,
    "Answer": [
        {"name": "example.com", "type": 1, "TTL": 300, "data": "9.9.9.9", "AD": 1},
        {"name": "example.com", "type": 1, "TTL": 300, "data": "9.9.9.9", "AD": 1},
    ],
}

#: Same answer, but *not* DNSSEC-validated (no ``AD`` bit).
DOH_NO_AD = {
    "Status": 0,
    "Answer": [{"name": "example.com", "type": 1, "TTL": 300, "data": "9.9.9.9"}],
}

#: A no-such-name answer.
DOH_NXDOMAIN = {"Status": 3, "Answer": []}

#: An IPv6 answer.
DOH_AAAA = {
    "Status": 0,
    "Answer": [
        {"name": "example.com", "type": 28, "TTL": 300, "data": "::1", "AD": 1}
    ],
}

#: A port that nothing listens on, so every DoH attempt fails fast.
DEAD = "http://127.0.0.1:9/dns-query"


class FakeDoHServer:
    """A tiny HTTP server that answers DoH JSON queries."""

    def __init__(self, payload, status: int = 200):
        self.payload = payload
        self.status = status
        self.server = None
        self.port = None
        self.requests = 0

    async def start(self):
        async def handle(reader, writer):
            self.requests += 1
            await reader.read(65536)
            body = json.dumps(self.payload).encode("utf-8")
            writer.write(
                b"HTTP/1.1 %d OK\r\n" % self.status
                + b"Content-Type: application/dns-json\r\n"
                + b"Content-Length: %d\r\n" % len(body)
                + b"Connection: close\r\n\r\n"
                + body
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        self.server = await asyncio.start_server(handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def stop(self):
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()

    def url(self) -> str:
        # Deliberately http://: UmerOS's DoH client builds the URL itself and
        # these tests must not depend on upstream TLS trust or real network.
        return f"http://127.0.0.1:{self.port}/dns-query"


class TestDoHFailClosed(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.servers = []

    async def asyncTearDown(self):
        for srv in self.servers:
            await srv.stop()

    # -- helpers -----------------------------------------------------------

    async def _online(self, payload=DOH_AD, **kwargs) -> DNSOverHTTPS:
        # `status` configures the *server*, not the resolver.
        status = kwargs.pop("status", 200)
        srv = FakeDoHServer(payload, status=status)
        await srv.start()
        self.servers.append(srv)
        return DNSOverHTTPS(primary=srv.url(), secondary=srv.url(), **kwargs)

    @staticmethod
    def _offline(**kwargs) -> DNSOverHTTPS:
        return DNSOverHTTPS(primary=DEAD, secondary=DEAD, timeout=0.4, **kwargs)

    async def _refused(self, resolver, *args):
        with self.assertRaises(PermissionError):
            await resolver.resolve_async(*args)

    # -- the silent fail-open is closed ------------------------------------

    async def test_default_refuses_when_no_endpoint_answers(self):
        await self._refused(self._offline(), "example.com")

    async def test_default_never_consults_system_dns(self):
        d = self._offline()
        await self._refused(d, "example.com")
        self.assertIsNone(d.dnssec_status("example.com"))

    async def test_failure_names_the_opt_in(self):
        d = self._offline()
        with self.assertRaises(PermissionError) as ctx:
            await d.resolve_async("example.com")
        self.assertIn("allow_system_fallback", str(ctx.exception))

    async def test_explicit_opt_in_still_falls_back(self):
        d = self._offline(allow_system_fallback=True)
        self.assertIsInstance(await d.resolve_async("localhost"), list)

    async def test_fallback_answer_is_marked_unauthenticated(self):
        d = self._offline(allow_system_fallback=True)
        await d.resolve_async("localhost")
        self.assertIs(d.dnssec_status("localhost"), False)

    # -- DNSSEC is the authenticator, DoH is not ---------------------------

    async def test_doh_success_needs_no_opt_in(self):
        d = await self._online()
        self.assertEqual(await d.resolve_async("example.com"), ["9.9.9.9"])

    async def test_dnssec_true_when_ad_is_set(self):
        d = await self._online(DOH_AD)
        await d.resolve_async("example.com")
        self.assertIs(d.dnssec_status("example.com"), True)

    async def test_dnssec_false_without_ad(self):
        d = await self._online(DOH_NO_AD)
        await d.resolve_async("example.com")
        self.assertIs(d.dnssec_status("example.com"), False)

    async def test_require_dnssec_accepts_validated(self):
        d = await self._online(DOH_AD, require_dnssec=True)
        self.assertEqual(await d.resolve_async("example.com"), ["9.9.9.9"])

    async def test_require_dnssec_rejects_unvalidated(self):
        d = await self._online(DOH_NO_AD, require_dnssec=True)
        await self._refused(d, "example.com")

    async def test_dnssec_status_none_before_any_query(self):
        d = await self._online()
        self.assertIsNone(d.dnssec_status("never.queried"))

    async def test_flush_clears_dnssec_state(self):
        d = await self._online(DOH_AD)
        await d.resolve_async("example.com")
        self.assertIs(d.dnssec_status("example.com"), True)
        d.flush_cache()
        self.assertIsNone(d.dnssec_status("example.com"))

    # -- behaviour that must not regress -----------------------------------

    async def test_cache_is_consulted_before_egress(self):
        srv = FakeDoHServer(DOH_AD)
        await srv.start()
        self.servers.append(srv)
        d = DNSOverHTTPS(primary=srv.url(), secondary=srv.url())
        await d.resolve_async("example.com")
        await d.resolve_async("example.com")
        self.assertEqual(srv.requests, 1, "second resolve did not hit the cache")

    async def test_answers_are_deduped(self):
        d = await self._online()
        self.assertEqual(await d.resolve_async("example.com"), ["9.9.9.9"])

    async def test_nxdomain_fails_closed(self):
        d = await self._online(DOH_NXDOMAIN)
        await self._refused(d, "nonexistent.example")

    async def test_http_500_is_a_failure(self):
        d = await self._online(DOH_AD, status=500)
        await self._refused(d, "example.com")

    async def test_empty_hostname_is_rejected(self):
        d = await self._online()
        with self.assertRaises(ValueError):
            await d.resolve_async("   ")

    async def test_aaaa_record_is_honoured(self):
        d = await self._online(DOH_AAAA)
        self.assertEqual(await d.resolve_async("example.com", "AAAA"), ["::1"])

    async def test_second_endpoint_is_tried(self):
        first = FakeDoHServer({"Status": 3, "Answer": []})
        await first.start()
        self.servers.append(first)
        second = FakeDoHServer(DOH_AD)
        await second.start()
        self.servers.append(second)
        d = DNSOverHTTPS(primary=first.url(), secondary=second.url())
        self.assertEqual(await d.resolve_async("example.com"), ["9.9.9.9"])


if __name__ == "__main__":
    unittest.main()
