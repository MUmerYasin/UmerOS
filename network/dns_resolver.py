#!/usr/bin/env python3
"""
Umer OS Async DNS Resolver

Resolves domain names to IP addresses using the system's nameservers.
Equivalent to Linux's net/dns_resolver/ subsystem.
"""

import socket
import asyncio


class DNSResolver:
    """Asynchronous DNS resolution service."""

    def __init__(self):
        self._cache: dict = {}
        print("[DNS] Resolver initialized.")

    async def resolve(self, hostname: str) -> str:
        """Resolve a hostname to an IPv4 address, with caching."""
        if hostname in self._cache:
            print(f"[DNS] Cache hit: {hostname} -> {self._cache[hostname]}")
            return self._cache[hostname]

        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None, socket.gethostbyname, hostname
            )
            self._cache[hostname] = result
            print(f"[DNS] Resolved: {hostname} -> {result}")
            return result
        except socket.gaierror as e:
            print(f"[DNS] Resolution failed for '{hostname}': {e}")
            return ""

    def flush_cache(self):
        self._cache.clear()
        print("[DNS] Cache flushed.")
