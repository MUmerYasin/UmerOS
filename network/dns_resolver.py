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
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

# [FIX H177] Zero-trust capability gate for network egress (DNS resolution).
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
        # [FIX H177] zero-trust gate: DNS egress requires CAP_NET_SEND. This is
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
        # [FIX H177] reverse DNS egress (outbound resolver query) also requires
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
