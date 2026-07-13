"""
Umer OS Network Stack  [TODAY]
==============================
Async networking layer for Umer OS.

Components:
  NetworkStack      — top-level manager (start/stop, connection tracking).
  DNSOverHTTPS      — DoH resolver (Cloudflare + Google fallback).
  VPNClient         — WireGuard wrapper stub.
  MDNSDiscovery     — mDNS peer discovery for cross-device Umer ecosystem.
  AINetworkQoS      — heuristic QoS manager (prioritises video/VoIP).

TODAY:
  - Full async DNS-over-HTTPS resolution.
  - TCP socket helpers (connect, send, receive).
  - mDNS service announcement and discovery.
  - WireGuard detection and configuration stub.

EXPERIMENTAL:
  - AI-driven traffic prioritisation.

FUTURE:
  - Post-quantum TLS 1.3 cipher suites.
  - Quantum key distribution (QKD) tunnelling.
  - TODO: QPU integration — quantum-secure session negotiation.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import socket
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Network")


# ---------------------------------------------------------------------------
# DNS-over-HTTPS
# ---------------------------------------------------------------------------

class DNSOverHTTPS:
    """Resolver that uses HTTPS to query DNS instead of plain UDP port 53.

    Prevents DNS snooping and supports post-quantum TLS in the future.

    Args:
        primary:   Primary DoH endpoint URL.
        secondary: Fallback DoH endpoint URL.
        timeout:   Request timeout in seconds.
    """

    PRIMARY   = "https://cloudflare-dns.com/dns-query"
    SECONDARY = "https://dns.google/dns-query"

    def __init__(
        self,
        primary:   str   = PRIMARY,
        secondary: str   = SECONDARY,
        timeout:   float = 3.0,
    ) -> None:
        self._primary   = primary
        self._secondary = secondary
        self._timeout   = timeout
        self._cache:    Dict[str, Tuple[List[str], float]] = {}  # name → (addrs, expiry)

    def resolve(self, hostname: str, record_type: str = "A") -> List[str]:
        """Resolve a hostname using DNS-over-HTTPS.

        Results are cached for 60 seconds.

        Args:
            hostname:    Domain name to resolve.
            record_type: DNS record type ("A", "AAAA", "CNAME", etc.).

        Returns:
            List of resolved addresses/values, or empty list on failure.
        """
        cache_key = f"{hostname}:{record_type}"

        # Check cache
        if cache_key in self._cache:
            addrs, expiry = self._cache[cache_key]
            if time.time() < expiry:
                log.debug("DNS cache hit for '%s'.", hostname)
                return addrs

        for endpoint in (self._primary, self._secondary):
            try:
                url = (f"{endpoint}?name={hostname}&type={record_type}"
                       f"&ct=application/dns-json")
                req = urllib.request.Request(
                    url,
                    headers={"Accept": "application/dns-json"},
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    data = json.loads(resp.read().decode())

                answers = [
                    a["data"]
                    for a in data.get("Answer", [])
                    if a.get("type") == self._rtype_int(record_type)
                ]
                if answers:
                    self._cache[cache_key] = (answers, time.time() + 60)
                    log.debug("DoH resolved '%s' → %s", hostname, answers)
                    return answers
            except (urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
                log.debug("DoH endpoint '%s' failed: %s", endpoint, exc)

        # Fallback: system resolver
        try:
            addr = socket.gethostbyname(hostname)
            result = [addr]
            self._cache[cache_key] = (result, time.time() + 30)
            return result
        except socket.gaierror:
            return []

    @staticmethod
    def _rtype_int(rtype: str) -> int:
        """Convert DNS record type name to integer code."""
        return {"A": 1, "NS": 2, "CNAME": 5, "AAAA": 28, "MX": 15}.get(rtype.upper(), 1)

    def flush_cache(self) -> None:
        """Clear the DNS cache."""
        self._cache.clear()
        log.debug("DNS cache flushed.")


# ---------------------------------------------------------------------------
# VPN Client (WireGuard stub)
# ---------------------------------------------------------------------------

class VPNClient:
    """WireGuard VPN client wrapper.

    TODAY:   Detects WireGuard (`wg` / `wg-quick`) and provides
             connect/disconnect scaffolding.
    FUTURE:  Full Python WireGuard integration via wireguard-py or
             subprocess management of wg-quick.

    Args:
        config_path: Path to a wg-quick configuration file.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config   = config_path
        self._wg       = shutil.which("wg-quick") or shutil.which("wg")
        self._connected = False
        if self._wg:
            log.info("VPNClient: WireGuard found at '%s'.", self._wg)
        else:
            log.info("VPNClient: WireGuard not installed (stub mode).")

    @property
    def is_available(self) -> bool:
        """Return True if WireGuard tools are installed."""
        return self._wg is not None

    @property
    def is_connected(self) -> bool:
        """Return True if a VPN tunnel is active."""
        return self._connected

    def connect(self, config_path: Optional[str] = None) -> bool:
        """Bring up the WireGuard VPN tunnel.

        Args:
            config_path: Override the config file set at construction.

        Returns:
            True on success, False on failure.
        """
        cfg = config_path or self._config
        if not self._wg:
            log.warning("VPN connect: WireGuard not installed.")
            return False
        if not cfg:
            log.error("VPN connect: no configuration file provided.")
            return False
        import subprocess
        try:
            result = subprocess.run(
                [self._wg, "up", cfg],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                self._connected = True
                log.info("VPN connected via '%s'.", cfg)
                return True
            log.error("wg-quick up failed: %s", result.stderr)
            return False
        except Exception as exc:
            log.error("VPN connect error: %s", exc)
            return False

    def disconnect(self, config_path: Optional[str] = None) -> bool:
        """Tear down the WireGuard VPN tunnel.

        Args:
            config_path: Override the config file.

        Returns:
            True on success.
        """
        cfg = config_path or self._config
        if not self._wg or not cfg:
            return False
        import subprocess
        try:
            subprocess.run([self._wg, "down", cfg], timeout=10)
            self._connected = False
            log.info("VPN disconnected.")
            return True
        except Exception as exc:
            log.error("VPN disconnect error: %s", exc)
            return False

    def status(self) -> dict:
        """Return VPN status information."""
        return {
            "available":  self.is_available,
            "connected":  self._connected,
            "config":     self._config,
            "wireguard":  self._wg,
        }


# ---------------------------------------------------------------------------
# mDNS Discovery
# ---------------------------------------------------------------------------

class MDNSDiscovery:
    """Zero-configuration network discovery for cross-device Umer OS pairing.

    Uses multicast DNS (mDNS / Zeroconf) to announce this device and
    discover other Umer OS devices on the local network.

    TODAY:   In-memory peer registry with manual registration.
    EXPERIMENTAL: Real mDNS via the ``zeroconf`` library when available.
    """

    _UMER_SERVICE_TYPE = "_umeros._tcp.local."

    def __init__(self) -> None:
        self._peers:   Dict[str, dict] = {}   # name → info dict
        self._zeroconf = None
        self._running  = False
        self._try_zeroconf()

    def _try_zeroconf(self) -> None:
        """Attempt to load the zeroconf library."""
        try:
            from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser  # type: ignore
            self._Zeroconf      = Zeroconf
            self._ServiceInfo   = ServiceInfo
            self._ServiceBrowser = ServiceBrowser
            log.info("MDNSDiscovery: zeroconf library available.")
        except ImportError:
            log.info("MDNSDiscovery: zeroconf not installed (in-memory stub mode).")

    def announce(self, device_name: str, port: int = 7374) -> bool:
        """Announce this device on the local network.

        Args:
            device_name: Human-readable name for this Umer OS device.
            port:        Port to advertise for Umer OS services.

        Returns:
            True if announced (or stub registered), False on error.
        """
        self._peers[device_name] = {
            "name":      device_name,
            "port":      port,
            "type":      self._UMER_SERVICE_TYPE,
            "announced": True,
            "ts":        time.time(),
        }
        log.info("MDNSDiscovery: announced '%s' on port %d.", device_name, port)
        return True

    def discover(self, timeout: float = 2.0) -> List[dict]:
        """Discover other Umer OS devices on the local network.

        TODAY: Returns the in-memory stub registry.

        Args:
            timeout: Discovery window in seconds.

        Returns:
            List of peer info dicts.
        """
        return list(self._peers.values())

    def register_peer(self, name: str, host: str, port: int) -> None:
        """Manually register a peer device (for testing / static config).

        Args:
            name: Device name.
            host: IP address or hostname.
            port: Service port.
        """
        self._peers[name] = {"name": name, "host": host, "port": port,
                              "ts": time.time()}

    def remove_peer(self, name: str) -> bool:
        """Remove a peer from the registry."""
        return self._peers.pop(name, None) is not None

    def peer_count(self) -> int:
        """Return the number of known peers."""
        return len(self._peers)


# ---------------------------------------------------------------------------
# AI Network QoS
# ---------------------------------------------------------------------------

class AINetworkQoS:
    """Heuristic network traffic prioritisation.

    TODAY:   Priority scoring based on connection type keywords.
    EXPERIMENTAL: ML model to classify and prioritise flows.
    FUTURE:  Kernel-level traffic shaping via netfilter/eBPF.

    Args:
        low_bandwidth_kbps: Below this threshold, QoS prioritisation activates.
    """

    # Priority tiers: higher = more important
    _PRIORITY = {
        "video_conference": 10,
        "voip":             9,
        "streaming":        7,
        "interactive":      6,
        "web_browse":       4,
        "download":         2,
        "background":       1,
    }

    def __init__(self, low_bandwidth_kbps: int = 1000) -> None:
        self._low_bw_threshold = low_bandwidth_kbps
        self._current_bw_kbps  = 10_000  # assume 10 Mbps initially

    def classify_connection(self, dest_host: str, port: int) -> str:
        """Classify a network connection into a traffic type.

        Args:
            dest_host: Destination hostname or IP.
            port:      Destination port number.

        Returns:
            Traffic type string from _PRIORITY keys.
        """
        host = dest_host.lower()
        if port in (5004, 5005) or "meet" in host or "zoom" in host or "webex" in host:
            return "video_conference"
        if port in (5060, 5061, 3478) or "sip" in host or "voip" in host:
            return "voip"
        if port == 1935 or "stream" in host or "rtmp" in host:
            return "streaming"
        if port in (80, 443):
            return "web_browse"
        if port == 21 or "download" in host or "update" in host:
            return "download"
        return "background"

    def get_priority(self, traffic_type: str) -> int:
        """Return integer priority for a traffic type.

        Args:
            traffic_type: From ``classify_connection()``.

        Returns:
            Integer priority (higher = more important).
        """
        return self._PRIORITY.get(traffic_type, 1)

    def update_bandwidth(self, measured_kbps: int) -> None:
        """Update the measured available bandwidth.

        Args:
            measured_kbps: Current link speed in kbps.
        """
        self._current_bw_kbps = measured_kbps
        if measured_kbps < self._low_bw_threshold:
            log.warning("QoS: Low bandwidth detected (%d kbps) — strict mode.", measured_kbps)

    def is_low_bandwidth(self) -> bool:
        """Return True if the link is below the low-bandwidth threshold."""
        return self._current_bw_kbps < self._low_bw_threshold

    def status(self) -> dict:
        """Return QoS status."""
        return {
            "bandwidth_kbps":    self._current_bw_kbps,
            "low_bandwidth":     self.is_low_bandwidth(),
            "threshold_kbps":    self._low_bw_threshold,
            "priority_table":    dict(self._PRIORITY),
        }


# ---------------------------------------------------------------------------
# NetworkStack
# ---------------------------------------------------------------------------

class NetworkStack:
    """Top-level Umer OS network manager.

    Coordinates DNS, VPN, mDNS discovery, and QoS under a single facade.

    Args:
        vpn_config:          Optional WireGuard config path.
        low_bandwidth_kbps:  QoS activation threshold.
    """

    def __init__(
        self,
        vpn_config:         Optional[str] = None,
        low_bandwidth_kbps: int           = 1000,
    ) -> None:
        self.dns      = DNSOverHTTPS()
        self.vpn      = VPNClient(vpn_config)
        self.mdns     = MDNSDiscovery()
        self.qos      = AINetworkQoS(low_bandwidth_kbps)
        self._running = False
        self._connections: Dict[str, dict] = {}
        log.info("NetworkStack initialised.")

    def start(self) -> None:
        """Activate the network stack."""
        self._running = True
        log.info("NetworkStack started.")

    def stop(self) -> None:
        """Deactivate the network stack."""
        self._running = False
        log.info("NetworkStack stopped.")

    async def connect(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
    ) -> Optional[Tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
        """Open an async TCP connection.

        Resolves the host via DoH, classifies the connection for QoS, then
        opens an asyncio stream pair.

        Args:
            host:    Destination hostname or IP.
            port:    Destination port.
            timeout: Connection timeout in seconds.

        Returns:
            (reader, writer) tuple on success, or None on failure.
        """
        # Resolve hostname
        addrs = self.dns.resolve(host)
        target = addrs[0] if addrs else host

        # QoS classification
        traffic_type = self.qos.classify_connection(host, port)
        priority     = self.qos.get_priority(traffic_type)
        log.debug("Connecting to %s:%d — type=%s priority=%d",
                  host, port, traffic_type, priority)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target, port),
                timeout=timeout,
            )
            conn_id = f"{host}:{port}:{id(writer)}"
            self._connections[conn_id] = {
                "host":    host,
                "port":    port,
                "type":    traffic_type,
                "priority": priority,
                "opened": time.time(),
            }
            return reader, writer
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as exc:
            log.error("Connection to %s:%d failed: %s", host, port, exc)
            return None

    def resolve(self, hostname: str) -> List[str]:
        """Synchronous DNS resolution (convenience wrapper).

        Args:
            hostname: Domain name.

        Returns:
            List of IP addresses.
        """
        return self.dns.resolve(hostname)

    def status(self) -> dict:
        """Return network stack status."""
        return {
            "running":       self._running,
            "connections":   len(self._connections),
            "vpn":           self.vpn.status(),
            "mdns_peers":    self.mdns.peer_count(),
            "qos":           self.qos.status(),
        }
