#!/usr/bin/env python3
"""
Umer OS HTTP Client

Lightweight async HTTP/HTTPS client for REST APIs and OTA downloads.
Uses aiohttp when available, falls back to urllib.
"""

import asyncio
import json


class HTTPClient:
    """Async HTTP client for Umer OS network operations."""

    def __init__(self):
        self._aiohttp_available = False
        try:
            import aiohttp  # noqa: F401
            self._aiohttp_available = True
        except ImportError:
            pass
        engine = "aiohttp" if self._aiohttp_available else "urllib-fallback"
        print(f"[HTTP] Client initialized ({engine}).")

    async def get(self, url: str) -> dict:
        """Perform an HTTP GET request. Returns {'status': int, 'body': str}."""
        if self._aiohttp_available:
            return await self._get_aiohttp(url)
        return await self._get_urllib(url)

    async def _get_aiohttp(self, url: str) -> dict:
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    body = await resp.text()
                    print(f"[HTTP] GET {url} -> {resp.status}")
                    return {"status": resp.status, "body": body}
        except Exception as e:
            print(f"[HTTP] GET failed: {e}")
            return {"status": 0, "body": str(e)}

    async def _get_urllib(self, url: str) -> dict:
        import urllib.request
        loop = asyncio.get_running_loop()
        try:
            def _fetch():
                req = urllib.request.Request(url, headers={"User-Agent": "UmerOS/2.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return {"status": resp.status, "body": resp.read().decode(errors='replace')}
            result = await loop.run_in_executor(None, _fetch)
            print(f"[HTTP] GET {url} -> {result['status']}")
            return result
        except Exception as e:
            print(f"[HTTP] GET failed: {e}")
            return {"status": 0, "body": str(e)}
