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
"""Async DNS resolver for the UmerOS network subsystem.

TODAY:
    Uses the host resolver through ``asyncio.getaddrinfo`` so UmerOS can
    resolve public internet hosts and local LAN names without third-party
    dependencies.

EXPERIMENTAL:
    Resolver policy hooks can later prefer DNS-over-HTTPS or split-horizon
    resolvers per sandbox.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

# Zero-trust capability gate for network egress (DNS resolution).
from core.capability_gate import CAP_NET_SEND, gate

log = logging.getLogger("UmerOS.Network.DNS")


@dataclass(frozen=True)
class DNSCacheEntry:
    """Cached DNS answer with an expiry timestamp."""

    addresses: Tuple[str, ...]
    expires_at: float


class DNSResolver:
    """Asynchronous DNS resolution service with TTL-based caching."""

    def __init__(self, cache_ttl: float = 300.0, timeout: float = 5.0) -> None:
        """Initialize the resolver.

        Args:
            cache_ttl: Seconds to keep successful answers.
            timeout: Maximum seconds to wait for the system resolver.
        """
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self._cache: Dict[tuple[str, int], DNSCacheEntry] = {}

    async def resolve(self, hostname: str, family: int = socket.AF_UNSPEC) -> str:
        """Resolve a hostname and return the first IP address.

        Args:
            hostname: DNS name or literal IP address.
            family: Address family, usually ``AF_UNSPEC``, ``AF_INET``, or
                ``AF_INET6``.

        Returns:
            First resolved address, or an empty string if resolution fails.
        """
        addresses = await self.resolve_all(hostname, family=family)
        return addresses[0] if addresses else ""

    async def resolve_all(
        self,
        hostname: str,
        family: int = socket.AF_UNSPEC,
        port: int = 0,
    ) -> List[str]:
        """Resolve a hostname to all unique IP addresses.

        Args:
            hostname: DNS name or literal IP address.
            family: Address family filter.
            port: Optional port used by ``getaddrinfo``.

        Returns:
            Unique addresses in resolver order.
        """
        # zero-trust gate: DNS egress requires CAP_NET_SEND. This is
        # the real getaddrinfo chokepoint, so it transitively covers resolve().
        gate.require(CAP_NET_SEND)
        name = self._normalize_hostname(hostname)
        literal = self._literal_ip(name)
        if literal:
            return [literal]

        cache_key = (name, family)
        cached = self._cache.get(cache_key)
        if cached and cached.expires_at > time.time():
            return list(cached.addresses)

        loop = asyncio.get_running_loop()
        try:
            infos = await asyncio.wait_for(
                loop.getaddrinfo(name, port, family=family, type=socket.SOCK_STREAM),
                timeout=self.timeout,
            )
        except (asyncio.TimeoutError, OSError, socket.gaierror) as exc:
            log.warning("DNS resolution failed for %s: %s", name, exc)
            return []

        addresses = self._dedupe(sockaddr[0] for *_rest, sockaddr in infos)
        if addresses:
            self._cache[cache_key] = DNSCacheEntry(
                tuple(addresses),
                time.time() + self.cache_ttl,
            )
        return addresses

    async def reverse_lookup(self, ip_address: str) -> str:
        """Resolve an IP address back to a hostname if available."""
        # reverse DNS egress (outbound resolver query) also requires
        # CAP_NET_SEND, symmetric with resolve_all(). Input validation runs first
        # so a malformed IP still raises ValueError independently of the gate.
        try:
            normalized = str(ipaddress.ip_address(ip_address.strip()))
        except ValueError:
            raise ValueError(f"Invalid IP address: {ip_address!r}") from None

        gate.require(CAP_NET_SEND)
        loop = asyncio.get_running_loop()
        try:
            host, _aliases, _ips = await asyncio.wait_for(
                loop.run_in_executor(None, socket.gethostbyaddr, normalized),
                timeout=self.timeout,
            )
            return host
        except (asyncio.TimeoutError, OSError, socket.herror):
            return ""

    def flush_cache(self) -> None:
        """Clear all cached DNS records."""
        self._cache.clear()

    def cache_size(self) -> int:
        """Return the number of cached host/family entries."""
        return len(self._cache)

    @staticmethod
    def _normalize_hostname(hostname: str) -> str:
        """Validate and normalize a hostname string."""
        name = hostname.strip().rstrip(".")
        if not name:
            raise ValueError("hostname must not be empty")
        if any(ch.isspace() for ch in name):
            raise ValueError(f"hostname contains whitespace: {hostname!r}")
        return name.lower()

    @staticmethod
    def _literal_ip(hostname: str) -> str:
        """Return normalized IP if hostname is a literal address."""
        try:
            return str(ipaddress.ip_address(hostname))
        except ValueError:
            return ""

    @staticmethod
    def _dedupe(values: Iterable[str]) -> List[str]:
        """Preserve order while removing duplicate addresses."""
        seen: set[str] = set()
        result: List[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result



async def _selftest_async() -> bool:
    """Self-test for the resolver: normalization, literals, cache, validation.

    Everything here is deterministic; the only real socket work is a loopback
    ``getaddrinfo`` for ``"localhost"``, which every supported platform
    answers from its own hosts file.
    """

    def fail(message: str) -> bool:
        print(f"dns_resolver selftest: {message}")
        return False

    # -- hostname normalization -------------------------------------------
    if DNSResolver._normalize_hostname("  Example.COM.  ") != "example.com":
        return fail("hostname is not stripped / lower-cased / un-dotted")
    for bad in ("", "   ", "bad host", "two words"):
        try:
            DNSResolver._normalize_hostname(bad)
        except ValueError:
            continue
        return fail(f"_normalize_hostname accepted {bad!r}")

    # -- literal addresses never reach the resolver ------------------------
    resolver = DNSResolver()
    if await resolver.resolve("127.0.0.1") != "127.0.0.1":
        return fail("a literal IPv4 was not returned verbatim")
    if await resolver.resolve_all("::1") != ["::1"]:
        return fail("a literal IPv6 was not returned verbatim")
    if resolver.cache_size() != 0:
        return fail("a literal answer must not occupy a cache slot")

    # -- the TTL cache is actually consulted --------------------------------
    resolver._cache[("cached.test", socket.AF_UNSPEC)] = DNSCacheEntry(
        ("192.0.2.10",), time.time() + 60.0
    )
    if await resolver.resolve_all("cached.test") != ["192.0.2.10"]:
        return fail("a live cache entry was not served")
    if resolver.cache_size() != 1:
        return fail("cache_size() ignored the seeded entry")
    resolver.flush_cache()
    if resolver.cache_size() != 0:
        return fail("flush_cache() left entries behind")

    # -- reverse lookup validates its input before any egress ----------------
    for bad in ("", "not-an-ip", "999.1.1.1", "localhost"):
        try:
            await resolver.reverse_lookup(bad)
        except ValueError:
            continue
        return fail(f"reverse_lookup accepted {bad!r}")

    # -- order-preserving de-duplication -------------------------------------
    if DNSResolver._dedupe(["a", "b", "a", "c", "b", "a"]) != ["a", "b", "c"]:
        return fail("dedupe did not preserve first-seen order")

    # -- the real chokepoint: loopback getaddrinfo through the gate -----------
    loopback = await resolver.resolve_all("localhost", family=socket.AF_INET)
    if "127.0.0.1" not in loopback:
        return fail(f"localhost did not resolve to a loopback address: {loopback!r}")
    if any(not ipaddress.ip_address(a).is_loopback for a in loopback):
        return fail("a non-loopback address came back for localhost")

    return True


def _selftest() -> bool:
    """Run the module self-test (async body driven through ``asyncio.run``)."""
    return asyncio.run(_selftest_async())


if __name__ == "__main__":
    import sys as _sys

    _ok = _selftest()
    print("dns_resolver selftest:", "OK" if _ok else "FAIL")
    _sys.exit(0 if _ok else 1)
