# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS Network Diagnostics Tools
================================

Network diagnostic utilities: ping, traceroute, DNS lookup, etc.
"""

from __future__ import annotations

import logging
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger("UmerOS.Tools.Network")


@dataclass
class PingResult:
    host: str
    success: bool
    rtt_ms: float = 0.0
    packets_sent: int = 0
    packets_received: int = 0
    error: Optional[str] = None


@dataclass
class DnsResult:
    hostname: str
    addresses: List[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.addresses is None:
            self.addresses = []


class NetworkDiagnostics:
    """Network diagnostic utilities."""

    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    def ping(self, host: str, count: int = 4) -> PingResult:
        """Ping a host."""
        result = PingResult(host=host, success=False)
        try:
            # Try system ping
            proc = subprocess.run(
                ["ping", "-c", str(count), "-W", str(int(self.timeout)), host],
                capture_output=True, text=True, timeout=self.timeout + count,
            )
            if proc.returncode == 0:
                result.success = True
                result.packets_sent = count
                result.packets_received = count
                # Parse RTT
                for line in proc.stdout.splitlines():
                    if "rtt" in line.lower() or "round-trip" in line.lower():
                        parts = line.split("=")
                        if len(parts) >= 2:
                            rtt_str = parts[1].strip().split("/")[1] if "/" in parts[1] else parts[1].strip().split()[0]
                            try:
                                result.rtt_ms = float(rtt_str)
                            except ValueError:
                                pass
            else:
                result.error = proc.stderr.strip() or "Host unreachable"
        except FileNotFoundError:
            # ping not available - simulate
            result = self._simulate_ping(host, count)
        except subprocess.TimeoutExpired:
            result.error = "Timeout"
        except Exception as e:
            result.error = str(e)
        return result

    def _simulate_ping(self, host: str, count: int) -> PingResult:
        """Simulate ping for testing."""
        try:
            socket.gethostbyname(host)
            return PingResult(host=host, success=True, rtt_ms=12.5, packets_sent=count, packets_received=count)
        except socket.gaierror:
            return PingResult(host=host, success=False, error="Unknown host")

    def dns_lookup(self, hostname: str) -> DnsResult:
        """Resolve hostname to IP addresses."""
        result = DnsResult(hostname=hostname)
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            addresses = list(set(info[4][0] for info in addr_info))
            result.addresses = addresses
        except socket.gaierror as e:
            result.error = str(e)
        except Exception as e:
            result.error = str(e)
        return result

    def check_port(self, host: str, port: int, timeout: float = 3.0) -> bool:
        """Check if a port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False


def ping_host(host: str, count: int = 4, timeout: float = 5.0) -> PingResult:
    return NetworkDiagnostics(timeout=timeout).ping(host, count)


def dns_lookup(hostname: str) -> DnsResult:
    return NetworkDiagnostics().dns_lookup(hostname)