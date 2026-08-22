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
