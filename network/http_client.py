#!/usr/bin/env python3
"""HTTP and HTTPS client for UmerOS internet access.

TODAY:
    Provides async request helpers using ``aiohttp`` when available and a
    standard-library ``urllib`` fallback when it is not.

FUTURE:
    Post-quantum TLS policy can be enforced beneath this facade when the host
    TLS stack and PQC libraries support it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

log = logging.getLogger("UmerOS.Network.HTTP")


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
        """Validate that a URL is suitable for network access."""
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("only http:// and https:// URLs are supported")
        if not parsed.netloc:
            raise ValueError("URL must include a host")
        return urllib.parse.urlunparse(parsed)

    @staticmethod
    def _can_import_aiohttp() -> bool:
        """Return True when aiohttp is importable."""
        try:
            import aiohttp  # noqa: F401
            return True
        except ImportError:
            return False
