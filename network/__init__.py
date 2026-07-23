"""UmerOS network subsystem public API."""

from .dns_resolver import DNSResolver
from .http_client import HTTPClient, HTTPResponse
from .network_stack import (
    AINetworkQoS,
    DNSOverHTTPS,
    InternetAccessManager,
    MDNSDiscovery,
    NetworkStack,
    VPNClient,
)
from .tcp_server import TCPClient, TCPServer
from .vpn_tunnel import VPNTunnel

__all__ = [
    "AINetworkQoS",
    "DNSOverHTTPS",
    "DNSResolver",
    "HTTPClient",
    "HTTPResponse",
    "InternetAccessManager",
    "MDNSDiscovery",
    "NetworkStack",
    "TCPClient",
    "TCPServer",
    "VPNClient",
    "VPNTunnel",
]
