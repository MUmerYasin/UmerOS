#!/usr/bin/env python3
"""UmerOS network stack.

TODAY:
    A pure-Python network facade for DNS, HTTP/HTTPS, TCP connections,
    simulated VPN tunnel flows, local peer discovery, and heuristic QoS.

EXPERIMENTAL:
    AI traffic classification and real mDNS integration.

FUTURE:
    Post-quantum TLS policy, QKD research hooks, and hardware offload.
    # TODO: QPU integration for future quantum-secure session negotiation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    from .dns_resolver import DNSResolver
    from .http_client import HTTPClient
except ImportError:  # pragma: no cover - supports direct script execution
    from dns_resolver import DNSResolver
    from http_client import HTTPClient

log = logging.getLogger("UmerOS.Network")


@dataclass(frozen=True)
class ConnectionInfo:
    """Metadata tracked for an outbound TCP connection."""

    host: str
    port: int
    traffic_type: str
    priority: int
    opened_at: float


class DNSOverHTTPS:
    """Small DNS-over-HTTPS resolver with system DNS fallback."""

    PRIMARY = "https://cloudflare-dns.com/dns-query"
    SECONDARY = "https://dns.google/resolve"

    def __init__(
        self,
        primary: str = PRIMARY,
        secondary: str = SECONDARY,
        timeout: float = 3.0,
        cache_ttl: float = 300.0,
    ) -> None:
        """Initialize the DoH resolver."""
        self.primary = primary
        self.secondary = secondary
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cache: Dict[tuple[str, str], tuple[List[str], float]] = {}

    def resolve(self, hostname: str, record_type: str = "A") -> List[str]:
        """Resolve a hostname through DoH, falling back to system DNS."""
        name = self._normalize_hostname(hostname)
        record = record_type.upper().strip() or "A"
        cache_key = (name, record)
        cached = self._cache.get(cache_key)
        if cached and cached[1] > time.time():
            return list(cached[0])

        for endpoint in (self.primary, self.secondary):
            answers = self._query_endpoint(endpoint, name, record)
            if answers:
                self._cache[cache_key] = (answers, time.time() + self.cache_ttl)
                return answers

        answers = self._system_resolve(name, record)
        if answers:
            self._cache[cache_key] = (answers, time.time() + min(60.0, self.cache_ttl))
        return answers

    async def resolve_async(self, hostname: str, record_type: str = "A") -> List[str]:
        """Async wrapper for ``resolve``."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.resolve, hostname, record_type)

    def flush_cache(self) -> None:
        """Clear DoH cache."""
        self._cache.clear()

    def _query_endpoint(self, endpoint: str, hostname: str, record_type: str) -> List[str]:
        """Query one DoH JSON endpoint."""
        query = urllib.parse.urlencode({"name": hostname, "type": record_type})
        separator = "&" if "?" in endpoint else "?"
        url = f"{endpoint}{separator}{query}"
        req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            log.debug("DoH endpoint failed for %s via %s: %s", hostname, endpoint, exc)
            return []

        expected_type = self._rtype_int(record_type)
        answers: List[str] = []
        for answer in payload.get("Answer", []):
            if answer.get("type") == expected_type and "data" in answer:
                answers.append(str(answer["data"]))
        return self._dedupe(answers)

    @staticmethod
    def _system_resolve(hostname: str, record_type: str) -> List[str]:
        """Use the host resolver as fallback."""
        family = socket.AF_INET6 if record_type == "AAAA" else socket.AF_INET
        try:
            infos = socket.getaddrinfo(hostname, 0, family, socket.SOCK_STREAM)
        except socket.gaierror:
            return []
        return DNSOverHTTPS._dedupe(sockaddr[0] for *_rest, sockaddr in infos)

    @staticmethod
    def _rtype_int(record_type: str) -> int:
        """Convert a DNS record name to its integer code."""
        return {"A": 1, "NS": 2, "CNAME": 5, "MX": 15, "AAAA": 28}.get(
            record_type.upper(),
            1,
        )

    @staticmethod
    def _normalize_hostname(hostname: str) -> str:
        """Normalize and validate a hostname."""
        name = hostname.strip().rstrip(".").lower()
        if not name:
            raise ValueError("hostname must not be empty")
        if any(ch.isspace() for ch in name):
            raise ValueError(f"hostname contains whitespace: {hostname!r}")
        return name

    @staticmethod
    def _dedupe(values: Any) -> List[str]:
        """Preserve order while removing duplicates."""
        seen: set[str] = set()
        result: List[str] = []
        for value in values:
            text = str(value)
            if text not in seen:
                seen.add(text)
                result.append(text)
        return result


class VPNClient:
    """WireGuard command wrapper.

    The class never shells out through a string; it uses argv lists so config
    paths are not interpreted by the shell.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialize the VPN wrapper."""
        self.config_path = config_path
        self._wg_quick = shutil.which("wg-quick")
        self._wg = shutil.which("wg")
        self._connected = False

    @property
    def is_available(self) -> bool:
        """Return True when WireGuard tooling is available."""
        return bool(self._wg_quick or self._wg)

    @property
    def is_connected(self) -> bool:
        """Return True when this wrapper has connected a tunnel."""
        return self._connected

    def connect(self, config_path: Optional[str] = None) -> bool:
        """Bring up a WireGuard tunnel with ``wg-quick up``."""
        cfg = config_path or self.config_path
        if not self._wg_quick or not cfg:
            log.warning("WireGuard connect unavailable: wg-quick=%s cfg=%s", self._wg_quick, cfg)
            return False
        try:
            result = subprocess.run(
                [self._wg_quick, "up", cfg],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            log.error("WireGuard connect failed: %s", exc)
            return False
        self._connected = result.returncode == 0
        if not self._connected:
            log.error("wg-quick up failed: %s", result.stderr.strip())
        return self._connected

    def disconnect(self, config_path: Optional[str] = None) -> bool:
        """Bring down a WireGuard tunnel with ``wg-quick down``."""
        cfg = config_path or self.config_path
        if not self._wg_quick or not cfg:
            return False
        try:
            result = subprocess.run(
                [self._wg_quick, "down", cfg],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            log.error("WireGuard disconnect failed: %s", exc)
            return False
        if result.returncode == 0:
            self._connected = False
            return True
        log.error("wg-quick down failed: %s", result.stderr.strip())
        return False

    def status(self) -> dict:
        """Return VPN status metadata."""
        return {
            "available": self.is_available,
            "connected": self.is_connected,
            "config": self.config_path,
            "wg": self._wg,
            "wg_quick": self._wg_quick,
        }


class MDNSDiscovery:
    """Local UmerOS peer registry with optional future mDNS backend."""

    SERVICE_TYPE = "_umeros._tcp.local."

    def __init__(self) -> None:
        """Initialize peer discovery."""
        self._peers: Dict[str, dict] = {}
        self._zeroconf_available = self._can_import_zeroconf()

    def announce(self, device_name: str, host: str = "127.0.0.1", port: int = 7374) -> bool:
        """Announce or register this UmerOS node."""
        name = device_name.strip()
        if not name:
            raise ValueError("device_name must not be empty")
        self._peers[name] = {
            "name": name,
            "host": host,
            "port": port,
            "type": self.SERVICE_TYPE,
            "announced": True,
            "updated_at": time.time(),
        }
        return True

    def discover(self, timeout: float = 2.0) -> List[dict]:
        """Discover known UmerOS peers.

        ``timeout`` is accepted for API compatibility with real mDNS discovery.
        """
        _ = timeout
        return list(self._peers.values())

    def register_peer(self, name: str, host: str, port: int) -> None:
        """Register a peer manually."""
        if not name.strip() or not host.strip():
            raise ValueError("name and host must not be empty")
        self._peers[name.strip()] = {
            "name": name.strip(),
            "host": host.strip(),
            "port": port,
            "type": self.SERVICE_TYPE,
            "updated_at": time.time(),
        }

    def remove_peer(self, name: str) -> bool:
        """Remove a peer by name."""
        return self._peers.pop(name, None) is not None

    def peer_count(self) -> int:
        """Return the number of known peers."""
        return len(self._peers)

    def status(self) -> dict:
        """Return discovery status."""
        return {
            "peers": self.peer_count(),
            "zeroconf_available": self._zeroconf_available,
            "service_type": self.SERVICE_TYPE,
        }

    @staticmethod
    def _can_import_zeroconf() -> bool:
        """Return True if zeroconf is installed."""
        try:
            import zeroconf  # noqa: F401
            return True
        except ImportError:
            return False


class AINetworkQoS:
    """Heuristic network traffic prioritization."""

    PRIORITY = {
        "video_conference": 10,
        "voip": 9,
        "streaming": 7,
        "interactive": 6,
        "web_browse": 4,
        "download": 2,
        "background": 1,
    }

    def __init__(self, low_bandwidth_kbps: int = 1000) -> None:
        """Initialize QoS state."""
        self.low_bandwidth_kbps = low_bandwidth_kbps
        self.current_bandwidth_kbps = 10_000

    def classify_connection(self, dest_host: str, port: int) -> str:
        """Classify traffic by host and port."""
        host = dest_host.lower()
        if port in (5004, 5005) or any(token in host for token in ("meet", "zoom", "webex")):
            return "video_conference"
        if port in (5060, 5061, 3478) or any(token in host for token in ("sip", "voip")):
            return "voip"
        if port == 1935 or any(token in host for token in ("stream", "rtmp")):
            return "streaming"
        if port in (22, 3389):
            return "interactive"
        if port in (80, 443):
            return "web_browse"
        if port == 21 or any(token in host for token in ("download", "update")):
            return "download"
        return "background"

    def get_priority(self, traffic_type: str) -> int:
        """Return priority score for a traffic type."""
        return self.PRIORITY.get(traffic_type, 1)

    def update_bandwidth(self, measured_kbps: int) -> None:
        """Update measured bandwidth."""
        if measured_kbps < 0:
            raise ValueError("measured_kbps must be >= 0")
        self.current_bandwidth_kbps = measured_kbps

    def is_low_bandwidth(self) -> bool:
        """Return True when measured bandwidth is below threshold."""
        return self.current_bandwidth_kbps < self.low_bandwidth_kbps

    def status(self) -> dict:
        """Return QoS status."""
        return {
            "bandwidth_kbps": self.current_bandwidth_kbps,
            "low_bandwidth": self.is_low_bandwidth(),
            "threshold_kbps": self.low_bandwidth_kbps,
            "priority_table": dict(self.PRIORITY),
        }


class InternetAccessManager:
    """High-level internet facade for UmerOS users and services."""

    def __init__(self, http: HTTPClient, dns: DNSResolver) -> None:
        """Initialize with shared HTTP and DNS services."""
        self.http = http
        self.dns = dns

    async def fetch_text(self, url: str) -> str:
        """Fetch text from an HTTP/HTTPS URL."""
        response = await self.http.request("GET", url)
        if not response.ok:
            raise ConnectionError(f"GET {url} failed with HTTP {response.status}: {response.reason}")
        return response.body

    async def fetch_json(self, url: str) -> Any:
        """Fetch and parse JSON from an HTTP/HTTPS URL."""
        return await self.http.fetch_json(url)

    async def download(self, url: str, destination: str | Path) -> Path:
        """Download a URL to a local file."""
        return await self.http.download(url, destination)

    async def can_resolve(self, hostname: str = "example.com") -> bool:
        """Return True if DNS can resolve a hostname."""
        return bool(await self.dns.resolve_all(hostname))

    async def check_http(self, url: str = "https://example.com") -> bool:
        """Return True if an HTTP endpoint can be reached."""
        response = await self.http.request("GET", url)
        return response.ok


class NetworkStack:
    """Top-level UmerOS network manager."""

    def __init__(
        self,
        vpn_config: Optional[str] = None,
        low_bandwidth_kbps: int = 1000,
        dns_timeout: float = 5.0,
        http_timeout: float = 10.0,
    ) -> None:
        """Initialize network services."""
        self.resolver = DNSResolver(timeout=dns_timeout)
        self.dns = DNSOverHTTPS(timeout=min(3.0, dns_timeout))
        self.http = HTTPClient(timeout=http_timeout)
        self.internet = InternetAccessManager(self.http, self.resolver)
        self.vpn = VPNClient(vpn_config)
        self.mdns = MDNSDiscovery()
        self.qos = AINetworkQoS(low_bandwidth_kbps)
        self._running = False
        self._connections: Dict[int, ConnectionInfo] = {}
        self._writers: Dict[int, asyncio.StreamWriter] = {}

    @property
    def running(self) -> bool:
        """Return True when the stack is active."""
        return self._running

    def start(self) -> None:
        """Activate the network stack."""
        self._running = True
        log.info("NetworkStack started")

    async def stop(self) -> None:
        """Deactivate the network stack and close open TCP writers."""
        self._running = False
        await self.close_all()
        log.info("NetworkStack stopped")

    async def connect(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
    ) -> Optional[Tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
        """Open an async TCP connection using DNS and QoS metadata."""
        if port < 1 or port > 65535:
            raise ValueError("port must be between 1 and 65535")

        addresses = await self.resolver.resolve_all(host, port=port)
        targets = addresses or [host]
        traffic_type = self.qos.classify_connection(host, port)
        priority = self.qos.get_priority(traffic_type)
        last_error: Exception | None = None

        for target in targets:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(target, port),
                    timeout=timeout,
                )
            except (OSError, asyncio.TimeoutError) as exc:
                last_error = exc
                continue

            key = id(writer)
            self._writers[key] = writer
            self._connections[key] = ConnectionInfo(
                host=host,
                port=port,
                traffic_type=traffic_type,
                priority=priority,
                opened_at=time.time(),
            )
            return reader, writer

        log.warning("Connection to %s:%d failed: %s", host, port, last_error)
        return None

    async def send_tcp(
        self,
        host: str,
        port: int,
        payload: bytes,
        read_bytes: int = 4096,
        timeout: float = 5.0,
    ) -> bytes:
        """Open a TCP connection, send payload, read one response, and close."""
        connection = await self.connect(host, port, timeout=timeout)
        if connection is None:
            return b""
        reader, writer = connection
        try:
            writer.write(payload)
            await writer.drain()
            return await asyncio.wait_for(reader.read(read_bytes), timeout=timeout)
        finally:
            await self.close_writer(writer)

    async def close_writer(self, writer: asyncio.StreamWriter) -> None:
        """Close a tracked stream writer."""
        key = id(writer)
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
        self._writers.pop(key, None)
        self._connections.pop(key, None)

    async def close_all(self) -> None:
        """Close all tracked TCP writers."""
        writers = list(self._writers.values())
        for writer in writers:
            writer.close()
        for writer in writers:
            try:
                await writer.wait_closed()
            except OSError:
                pass
        self._writers.clear()
        self._connections.clear()

    async def resolve_async(self, hostname: str) -> List[str]:
        """Resolve a hostname asynchronously through the system resolver."""
        return await self.resolver.resolve_all(hostname)

    def resolve(self, hostname: str, record_type: str = "A") -> List[str]:
        """Resolve a hostname synchronously through DoH with fallback."""
        return self.dns.resolve(hostname, record_type)

    async def fetch_url(self, url: str) -> str:
        """Fetch text from the internet."""
        return await self.internet.fetch_text(url)

    async def fetch_json(self, url: str) -> Any:
        """Fetch JSON from the internet."""
        return await self.internet.fetch_json(url)

    async def download(self, url: str, destination: str | Path) -> Path:
        """Download a URL to a local file."""
        return await self.internet.download(url, destination)

    async def check_internet(
        self,
        dns_host: str = "example.com",
        http_url: str = "https://example.com",
    ) -> dict:
        """Check DNS and HTTP connectivity.

        This can be used by the UI or assistant before telling the user that
        internet access is available.
        """
        dns_ok = await self.internet.can_resolve(dns_host)
        http_ok = await self.internet.check_http(http_url) if dns_ok else False
        return {"dns": dns_ok, "http": http_ok, "online": dns_ok and http_ok}

    def status(self) -> dict:
        """Return network stack status."""
        return {
            "running": self._running,
            "connections": len(self._connections),
            "vpn": self.vpn.status(),
            "mdns": self.mdns.status(),
            "qos": self.qos.status(),
        }

    def connection_table(self) -> List[Mapping[str, Any]]:
        """Return tracked TCP connection metadata."""
        return [
            {
                "host": info.host,
                "port": info.port,
                "traffic_type": info.traffic_type,
                "priority": info.priority,
                "opened_at": info.opened_at,
            }
            for info in self._connections.values()
        ]
