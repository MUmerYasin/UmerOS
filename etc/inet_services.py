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

"""
UmerOS /etc Network Services
==============================
Manages network service name-to-port mappings and protocol definitions.

FHS 3.0 entries:
  /etc/services    — Network service name-to-port mapping
  /etc/protocols   — Protocol number definitions
  /etc/rpc         — RPC program number definitions

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.InetServices")


@dataclass
class ServiceEntry:
    """Represents a service name-to-port mapping."""
    name: str
    port: int
    protocol: str = "tcp"
    aliases: List[str] = None

    def __post_init__(self) -> None:
        if self.aliases is None:
            self.aliases = []


@dataclass
class ProtocolEntry:
    """Represents a protocol number definition."""
    name: str
    number: int
    aliases: List[str] = None

    def __post_init__(self) -> None:
        if self.aliases is None:
            self.aliases = []


@dataclass
class RPCEntry:
    """Represents an RPC program number definition."""
    name: str
    number: int
    aliases: List[str] = None

    def __post_init__(self) -> None:
        if self.aliases is None:
            self.aliases = []


class InetServicesManager:
    """
    Manages network services, protocols, and RPC definitions.

    Handles /etc/services, /etc/protocols, and /etc/rpc.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)

    def initialize(self) -> bool:
        """Create all network service files with defaults."""
        try:
            self._create_services()
            self._create_protocols()
            self._create_rpc()
            log.info("Initialized network services files")
            return True
        except Exception as e:
            log.error("Failed to initialize network services: %s", e)
            return False

    # ── /etc/services ────────────────────────────────────────────────────

    def _create_services(self) -> None:
        """Create /etc/services with common network services."""
        filepath = self.etc_path / "services"
        if filepath.exists():
            return
        content = """# /etc/services - Network service name-to-port mapping
# UmerOS Network Services
# Format: name port/protocol [aliases...]
#
# Each line describes a service, with the format:
#   service-name  port/protocol  [aliases...]

# Well-known services
ftp-data        20/tcp
ftp-data        20/udp
ftp             21/tcp
ftp             21/udp
ssh             22/tcp
ssh             22/udp
telnet          23/tcp
telnet          23/udp
smtp            25/tcp
smtp            25/udp
domain          53/tcp
domain          53/udp
dhcp-server     67/tcp
dhcp-server     67/udp
dhcp-client     68/tcp
dhcp-client     68/udp
tftp            69/tcp
tftp            69/udp
gopher          70/tcp
gopher          70/udp
http            80/tcp
http            80/udp
kerberos        88/tcp
kerberos        88/udp
pop2            109/tcp
pop2            109/udp
pop3            110/tcp
pop3            110/udp
sunrpc          111/tcp
sunrpc          111/udp
imap            143/tcp
imap            143/udp
ntp             123/tcp
ntp             123/udp
netbios-ns      137/tcp
netbios-ns      137/udp
netbios-dgm     138/tcp
netbios-dgm     138/udp
netbios-ssn     139/tcp
netbios-ssn     139/udp
imap3           220/tcp
imap3           220/udp
https           443/tcp
https           443/udp
samby           445/tcp
samby           445/udp
rsync           873/tcp
rsync           873/udp
ftps            990/tcp
ftps            990/udp
telnets         992/tcp
telnets         992/udp
imaps           993/tcp
imaps           993/udp
pop3s           995/tcp
pop3s           995/udp

# Common application ports
mysql           3306/tcp
mysql           3306/udp
postgres        5432/tcp
postgres        5432/udp
redis           6379/tcp
redis           6379/udp
memcached       11211/tcp
memcached       11211/udp
rabbitmq        5672/tcp
rabbitmq        5672/udp
mongodb         27017/tcp
mongodb         27017/udp
elasticsearch   9300/tcp
elasticsearch   9300/udp

# X11
x11             6000/tcp
x11             6000/udp

# Kerberos
klogin          543/tcp
kshell          544/tcp
kerberos-adm    749/tcp
kerberos-adm    749/udp

# Printing
printer         515/tcp
spooler         515/tcp

# NFS
nfs             2049/tcp
nfs             2049/udp
lockd           4045/tcp
lockd           4045/udp
mountd          892/tcp
mountd          892/udp
statd           993/tcp
statd           993/udp

# Logging
syslog          514/udp
syslog          514/tcp

# Time
time            37/tcp
time            37/udp
timed           37/udp
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/services")

    # ── /etc/protocols ───────────────────────────────────────────────────

    def _create_protocols(self) -> None:
        """Create /etc/protocols with common IP protocols."""
        filepath = self.etc_path / "protocols"
        if filepath.exists():
            return
        content = """# /etc/protocols - Protocol number definitions
# UmerOS Protocol Definitions
# Format: name number [aliases...]

ip          0       IP          # Internet protocol, pseudo protocol number
icmp        1       ICMP        # Internet Control Message Protocol
igmp        2       IGMP        # Internet Group Management
ggp         3       GGP         # Gateway-gateway protocol
tcp         6       TCP         # Transmission Control Protocol
egp         8       EGP         # Exterior Gateway Protocol
pup         12      PUP         # PARC universal packet protocol
udp         17      UDP         # User Datagram Protocol
hmp         20      HMP         # Host Monitoring Protocol
xns-idp     22      XNS-IDP     # Xerox NS IDP
rdp         27      RDP         # "reliable datagram" protocol
iso-tp4     29      ISO-TP4     # ISO Transport Protocol class 4
xnet        42      XNET        # Cross Net Internet Protocol
ipip        47      IPIP        # IPIP tunnels
egg         50      EGP         # Exterior Gateway Protocol
st          41      ST          # STREAM protocol
ipv6        41      IPv6        # Internet Protocol version 6
ipv6-route  43      IPv6-Route  # Routing Header for IPv6
ipv6-frag   44      IPv6-Frag   # Fragment Header for IPv6
ipv6-icmp   58      ICMPv6      # ICMP for IPv6
ipv6-noNxt  59      IPv6-NoNxt  # No Next Header for IPv6
ipv6-opts   60      IPv6-Opts   # Destination Options for IPv6
rspf        73      RSPF        # Radio Shortest Path First
vmtp        81      VMTP        # Versatile Message Transport
ospf        89      OSPF        # Open Shortest Path First
ipip-encap  94      IPIP-encap  # IP in IP encapsulation
anyprivate  119     Any private encryption scheme
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/protocols")

    # ── /etc/rpc ─────────────────────────────────────────────────────────

    def _create_rpc(self) -> None:
        """Create /etc/rpc with common RPC program numbers."""
        filepath = self.etc_path / "rpc"
        if filepath.exists():
            return
        content = """# /etc/rpc - RPC program number definitions
# UmerOS RPC Program Numbers
# Format: name number [aliases...]

portmapper      100000  portmap sunrpc
rstatd          100001  rstat rstat_svc rup
rusersd         100002  rusers
nfs             100003  nfsprog
yppasswdd       100004  yppasswd
yppoll          100006  ypbind
ypserv          100007  ypserv
rwalld          100008  rwall rwall_svc
rquotad         100009  rquotaprog quota rquotad
sprayd          100012  spray
pcnfsd          100021  pcnfsd
bwnfsd          100024
ypupdated       100028  ypupdate
keyserv         100029  keyserver
ttdbserverd     100036  ttdbserver
lockd           100045  lockd mountd
rpcbind         100050
statd           100051
rpcstatd        100051
nfsACLd         100053
rexd            100056
ypserv          100069
ypserv          100069
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/rpc")

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_services(self) -> List[ServiceEntry]:
        """Parse /etc/services into a list of entries."""
        filepath = self.etc_path / "services"
        if not filepath.exists():
            return []
        entries = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[0]
            port_proto = parts[1]
            if "/" not in port_proto:
                continue
            port_str, proto = port_proto.split("/", 1)
            try:
                port = int(port_str)
            except ValueError:
                continue
            aliases = parts[2:] if len(parts) > 2 else []
            entries.append(ServiceEntry(name=name, port=port, protocol=proto, aliases=aliases))
        return entries

    def parse_protocols(self) -> List[ProtocolEntry]:
        """Parse /etc/protocols into a list of entries."""
        filepath = self.etc_path / "protocols"
        if not filepath.exists():
            return []
        entries = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[0]
            try:
                number = int(parts[1])
            except ValueError:
                continue
            aliases = parts[2:] if len(parts) > 2 else []
            entries.append(ProtocolEntry(name=name, number=number, aliases=aliases))
        return entries

    def parse_rpc(self) -> List[RPCEntry]:
        """Parse /etc/rpc into a list of entries."""
        filepath = self.etc_path / "rpc"
        if not filepath.exists():
            return []
        entries = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[0]
            try:
                number = int(parts[1])
            except ValueError:
                continue
            aliases = parts[2:] if len(parts) > 2 else []
            entries.append(RPCEntry(name=name, number=number, aliases=aliases))
        return entries

    def find_service(self, name: str) -> Optional[ServiceEntry]:
        """Find a service by name or alias."""
        for entry in self.parse_services():
            if entry.name == name or name in entry.aliases:
                return entry
        return None

    def find_service_by_port(self, port: int, protocol: str = "tcp") -> Optional[ServiceEntry]:
        """Find a service by port number and protocol."""
        for entry in self.parse_services():
            if entry.port == port and entry.protocol == protocol:
                return entry
        return None

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of network services configuration."""
        services = self.parse_services()
        protocols = self.parse_protocols()
        rpc = self.parse_rpc()
        return {
            "services_exists": (self.etc_path / "services").exists(),
            "protocols_exists": (self.etc_path / "protocols").exists(),
            "rpc_exists": (self.etc_path / "rpc").exists(),
            "services_count": len(services),
            "protocols_count": len(protocols),
            "rpc_count": len(rpc),
        }
