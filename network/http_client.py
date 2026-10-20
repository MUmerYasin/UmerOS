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

#!/usr/bin/env python3
"""HTTP and HTTPS client for UmerOS internet access.

TODAY:
    Provides async request helpers using ``aiohttp`` when available and a
    standard-library ``urllib`` fallback when it is not.

FUTURE:
    Post-quantum TLS policy can be enforced beneath this facade when the host
    TLS stack and PQC libraries support it.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

# Zero-trust capability gate for network egress (HTTP client).
from core.capability_gate import CAP_NET_SEND, gate

log = logging.getLogger("UmerOS.Network.HTTP")

# Address scopes that must never be reached by an untrusted egress client.
# Reaching them from a metadada/SSRF perspective is a classic server-side
# request forgery (SSRF) primitive (cloud metadata 169.254.169.254, localhost
# admin panels, RFC1918 LAN hosts, link-local/multicast control planes...).
_SSRF_BLOCKED_SCOPES = (
    "is_private",
    "is_loopback",
    "is_link_local",
    "is_reserved",
    "is_multicast",
)


def _host_is_internal(host: str) -> bool:
    """Return True when `host` resolves to a non-public address (SSRF-protected).

    Literal IPs are classified directly; hostnames are resolved and
    every address is checked. Fail-closed: a hostname that cannot be resolved is
    treated as blocked rather than allowed.
    """
    host = (host or "").strip().strip("[]")  # tolerate [IPv6] brackets
    if not host:
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        pass  # not a literal — fall through to DNS resolution
    else:
        return any(getattr(addr, scope, False) for scope in _SSRF_BLOCKED_SCOPES) \
            or addr == ipaddress.ip_address("0.0.0.0")
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, OSError):
        return True  # fail-closed: cannot resolve -> assume internal
    for _family, _type, _proto, _canon, sockaddr in infos:
        ip = sockaddr[0].split("%")[0]  # strip IPv6 zone id
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if any(getattr(addr, scope, False) for scope in _SSRF_BLOCKED_SCOPES):
            return True
    return False


@dataclass(frozen=True)
class HTTPResponse:
    """Normalized HTTP response returned by ``HTTPClient``."""

    status: int
    body: str
    headers: Dict[str, str]
    url: str
    reason: str = ""

    @property
    def ok(self) -> bool:
        """Return True for 2xx responses."""
        return 200 <= self.status < 300

    def json(self) -> Any:
        """Parse the response body as JSON."""
        return json.loads(self.body)

    def as_dict(self) -> Dict[str, Any]:
        """Return a backward-compatible dictionary representation."""
        return {
            "status": self.status,
            "body": self.body,
            "headers": dict(self.headers),
            "url": self.url,
            "reason": self.reason,
            "ok": self.ok,
        }


class HTTPClient:
    """Async HTTP client for UmerOS network operations."""

    DEFAULT_HEADERS = {
        "User-Agent": "UmerOS/2.0 (+https://local.umeros)",
        "Accept": "*/*",
    }

    def __init__(self, timeout: float = 10.0, max_response_bytes: int = 10_485_760) -> None:
        """Initialize the HTTP client.

        Args:
            timeout: Request timeout in seconds.
            max_response_bytes: Safety cap for response bodies.
        """
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self._aiohttp_available = self._can_import_aiohttp()

    async def get(self, url: str, headers: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
        """Perform an HTTP GET and return a dictionary response."""
        response = await self.request("GET", url, headers=headers)
        return response.as_dict()

    async def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send a JSON POST request and return a dictionary response."""
        body = json.dumps(payload).encode("utf-8")
        merged = {"Content-Type": "application/json", **dict(headers or {})}
        response = await self.request("POST", url, body=body, headers=merged)
        return response.as_dict()

    async def fetch_json(
        self,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """Fetch a URL and parse the response body as JSON."""
        response = await self.request("GET", url, headers=headers)
        if not response.ok:
            raise ConnectionError(f"GET {url} failed with HTTP {response.status}")
        return response.json()

    async def download(
        self,
        url: str,
        destination: str | Path,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Path:
        """Download a URL to a local file.

        Args:
            url: HTTP or HTTPS URL.
            destination: File path to write.
            headers: Optional extra request headers.

        Returns:
            Destination path.
        """
        response = await self.request("GET", url, headers=headers)
        if not response.ok:
            raise ConnectionError(f"download failed with HTTP {response.status}: {url}")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(response.body, encoding="utf-8")
        return target

    async def request(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> HTTPResponse:
        """Perform an HTTP request.

        Args:
            method: HTTP method.
            url: HTTP or HTTPS URL.
            body: Optional request body bytes.
            headers: Optional extra headers.

        Returns:
            Normalized ``HTTPResponse``. Network failures return status ``0``.
        """
        # zero-trust gate: every network egress requires CAP_NET_SEND
        # (this chokepoint transitively covers get/post_json/fetch_json/download
        # and the NetworkStack/InternetFacade wrappers, which all call request()).
        gate.require(CAP_NET_SEND)
        clean_url = self._validate_url(url)
        merged_headers = {**self.DEFAULT_HEADERS, **dict(headers or {})}
        method = method.upper().strip()

        if self._aiohttp_available:
            return await self._request_aiohttp(method, clean_url, body, merged_headers)
        return await self._request_urllib(method, clean_url, body, merged_headers)

    async def _request_aiohttp(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
    ) -> HTTPResponse:
        """Run the request through aiohttp."""
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout, headers=dict(headers)) as session:
                async with session.request(method, url, data=body) as resp:
                    raw = await resp.content.read(self.max_response_bytes + 1)
                    if len(raw) > self.max_response_bytes:
                        raise ValueError("response exceeds configured size limit")
                    text = raw.decode(resp.charset or "utf-8", errors="replace")
                    return HTTPResponse(
                        status=resp.status,
                        body=text,
                        headers={k: v for k, v in resp.headers.items()},
                        url=str(resp.url),
                        reason=resp.reason or "",
                    )
        except Exception as exc:
            log.warning("%s %s failed via aiohttp: %s", method, url, exc)
            return HTTPResponse(0, str(exc), {}, url, reason=exc.__class__.__name__)

    async def _request_urllib(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
    ) -> HTTPResponse:
        """Run the request through urllib in an executor."""
        loop = asyncio.get_running_loop()

        def _fetch() -> HTTPResponse:
            req = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read(self.max_response_bytes + 1)
                    if len(raw) > self.max_response_bytes:
                        raise ValueError("response exceeds configured size limit")
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return HTTPResponse(
                        status=getattr(resp, "status", resp.getcode()),
                        body=raw.decode(charset, errors="replace"),
                        headers={k: v for k, v in resp.headers.items()},
                        url=resp.geturl(),
                        reason=getattr(resp, "reason", ""),
                    )
            except urllib.error.HTTPError as exc:
                raw = exc.read(self.max_response_bytes + 1)
                return HTTPResponse(
                    status=exc.code,
                    body=raw.decode("utf-8", errors="replace"),
                    headers={k: v for k, v in exc.headers.items()},
                    url=url,
                    reason=str(exc.reason),
                )

        try:
            return await loop.run_in_executor(None, _fetch)
        except Exception as exc:
            log.warning("%s %s failed via urllib: %s", method, url, exc)
            return HTTPResponse(0, str(exc), {}, url, reason=exc.__class__.__name__)

    @staticmethod
    def _validate_url(url: str) -> str:
        """Validate that a URL is suitable for network access.

        SSRF defense-in-depth: when the zero-trust posture is active
        (a CapabilityManager is wired, or strict mode is on) the destination host
        must not resolve to an internal / loopback / link-local / reserved /
        multicast address. In a permissive standalone or dev build the check is
        relaxed so legitimate localhost workflows (and the existing loopback
        tests) keep working. This mirrors the project-wide "permissive when
        unwired" convention used by the capability gate itself.
        """
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("only http:// and https:// URLs are supported")
        if not parsed.netloc:
            raise ValueError("URL must include a host")
        # parsed.hostname strips any userinfo (user:pass@) and port, and handles
        # bracketed IPv6 literals (e.g. [::1]:8080 -> ::1).
        host = parsed.hostname
        if host is None:
            raise ValueError("URL must include a host")
        if gate.enforcing and _host_is_internal(host):
            raise ValueError(
                f"refusing to connect to internal address (possible SSRF): {host}"
            )
        return urllib.parse.urlunparse(parsed)

    @staticmethod
    def _can_import_aiohttp() -> bool:
        """Return True when aiohttp is importable."""
        try:
            import aiohttp  # noqa: F401
            return True
        except ImportError:
            return False



async def _selftest_async() -> bool:
    """Self-test for URL validation, the SSRF classifier and a real fetch.

    The round-trip runs against a throwaway ``http.server`` on an ephemeral
    loopback port, so the test never touches the internet -- it only needs
    loopback TCP, the same assumption every other test in this repo makes.
    """

    def fail(message: str) -> bool:
        print(f"http_client selftest: {message}")
        return False

    # -- URL validation -----------------------------------------------------
    for bad in ("", "   ", "ftp://example.com/x", "http://", "https:///x", "file:///etc/passwd"):
        try:
            HTTPClient._validate_url(bad)
        except ValueError:
            continue
        return fail(f"_validate_url accepted {bad!r}")
    if HTTPClient._validate_url("https://example.com/a?b=1") != "https://example.com/a?b=1":
        return fail("_validate_url did not round-trip a valid URL")

    # -- SSRF defense-in-depth ----------------------------------------------
    for scope in ("is_private", "is_loopback", "is_link_local", "is_reserved", "is_multicast"):
        if scope not in _SSRF_BLOCKED_SCOPES:
            return fail(f"the SSRF scope table lost {scope!r}")
    for internal in (
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.1",
        "172.16.0.9",
        "169.254.169.254",
        "224.0.0.1",
        "0.0.0.0",
        "",
        "[::1]",
    ):
        if not _host_is_internal(internal):
            return fail(f"{internal!r} must be classified as internal")
    if _host_is_internal("8.8.8.8"):
        return fail("a public address must not be classified as internal")
    if not _host_is_internal("no such host"):
        return fail("an unresolvable host must be treated as internal (fail-closed)")

    # -- HTTPResponse normalisation ------------------------------------------
    good = HTTPResponse(200, '{"value": 42}', {"Content-Type": "application/json"}, "http://x/")
    if not good.ok or good.json() != {"value": 42}:
        return fail("HTTPResponse.ok/json() disagree with the body")
    if HTTPResponse(404, "", {}, "http://x/").ok:
        return fail("a 404 must not be reported as ok")
    as_dict = good.as_dict()
    if as_dict["status"] != 200 or as_dict["ok"] is not True:
        return fail("as_dict() lost the response fields")
    if as_dict["body"] != '{"value": 42}' or as_dict["url"] != "http://x/":
        return fail("as_dict() lost the body or url")

    # -- real loopback round-trip ---------------------------------------------
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class _Handler(BaseHTTPRequestHandler):
        """Tiny fixture: /health, /data.json, /echo (POST), everything else 404."""

        def _send(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header(
                "Content-Type",
                "application/json" if body.startswith(b"{") else "text/plain",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            if self.path == "/health":
                self._send(200, b"pong")
            elif self.path == "/data.json":
                self._send(200, b'{"value": 42}')
            else:
                self._send(404, b"not found")

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            self._send(200, b"posted:" + body)

        def log_message(self, *_args: object) -> None:
            """Silence the per-request stderr noise."""

    fixture = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = fixture.server_address[1]
    worker = threading.Thread(target=fixture.serve_forever, daemon=True)
    worker.start()
    try:
        client = HTTPClient()
        base = f"http://127.0.0.1:{port}"
        health = await client.get(f"{base}/health")
        if health["status"] != 200 or health["body"] != "pong":
            return fail(f"GET /health returned {health!r}")
        if await client.fetch_json(f"{base}/data.json") != {"value": 42}:
            return fail("fetch_json() did not parse the fixture body")
        posted = await client.post_json(f"{base}/echo", {"a": 1})
        if posted["status"] != 200 or posted["body"] != 'posted:{"a": 1}':
            return fail(f"post_json() round-trip failed: {posted!r}")
        missing = await client.get(f"{base}/missing")
        if missing["status"] != 404:
            return fail(f"an unknown path should be a 404, got {missing['status']}")

        # the response size cap must bite before the body is handed over
        capped = await HTTPClient(max_response_bytes=2).get(f"{base}/health")
        if capped["status"] != 0 or "size limit" not in capped["body"]:
            return fail(f"the response size cap did not bite: {capped!r}")

        # a bad scheme is refused before any socket is opened
        try:
            await client.get("ftp://example.com/")
        except ValueError:
            pass
        else:
            return fail("request() accepted a non-HTTP scheme")
    finally:
        fixture.shutdown()
        fixture.server_close()
        worker.join(timeout=5)

    return True


def _selftest() -> bool:
    """Run the module self-test (async body driven through ``asyncio.run``)."""
    return asyncio.run(_selftest_async())


if __name__ == "__main__":
    import sys as _sys

    _ok = _selftest()
    print("http_client selftest:", "OK" if _ok else "FAIL")
    _sys.exit(0 if _ok else 1)
