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
UmerOS Netlink Module
======================
Kernel netlink socket API interface.
Implements netlink protocols, message passing, and multicast groups.

Reference: docs.kernel.org/userspace-api/netlink.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple
import struct
import threading


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOENT: int = 2
EACCES: int = 13
ECONNREFUSED: int = 111
EMSGSIZE: int = 90

NETLINK_ROUTE: int = 0
NETLINK_USERSOCK: int = 2
NETLINK_FIREWALL: int = 3
NETLINK_SOCK_DIAG: int = 4
NETLINK_NFLOG: int = 5
NETLINK_XFRM: int = 6
NETLINK_SELINUX: int = 7
NETLINK_ISCSI: int = 8
NETLINK_AUDIT: int = 9
NETLINK_FIB_LOOKUP: int = 10
NETLINK_CONNECTOR: int = 11
NETLINK_NETFILTER: int = 12
NETLINK_IP6_FW: int = 13
NETLINK_DNRTMSG: int = 14
NETLINK_KOBJECT_UEVENT: int = 15
NETLINK_GENERIC: int = 16
NETLINK_SCSITRANSPORT: int = 18
NETLINK_ECRYPTFS: int = 19
NETLINK_RDMA: int = 20
NETLINK_CRYPTO: int = 21
NETLINK_SMC: int = 22

NETLINK_ADD_MEMBERSHIP: int = 1
NETLINK_DROP_MEMBERSHIP: int = 2
NETLINK_PKTINFO: int = 3
NETLINK_BROADCAST_ERROR: int = 4
NETLINK_NO_ENOBUFS: int = 5
NETLINK_LISTEN_ALL_NSID: int = 6
NETLINK_LIST_MEMBERSHIPS: int = 7
NETLINK_CAP_ACK: int = 10


# ============================================================================
# Netlink Message Types
# ============================================================================

class NetlinkMsgType(IntEnum):
    """Netlink message types."""
    NLMSG_NOOP: int = 1
    NLMSG_ERROR: int = 2
    NLMSG_DONE: int = 3
    NLMSG_OVERRUN: int = 4


class NetlinkFlags(IntEnum):
    """Netlink message flags."""
    NLM_F_REQUEST: int = 0x01
    NLM_F_MULTI: int = 0x02
    NLM_F_ACK: int = 0x04
    NLM_F_ECHO: int = 0x08
    NLM_F_DUMP_INTR: int = 0x10
    NLM_F_DUMP_FILTERED: int = 0x20
    NLM_F_ROOT: int = 0x400
    NLM_F_MATCH: int = 0x800
    NLM_F_ATOMIC: int = 0x1000
    NLM_F_REPLACE: int = 0x100
    NLM_F_CREATE: int = 0x400
    NLM_F_APPEND: int = 0x800
    NLM_F_EXCL: int = 0x200


# ============================================================================
# Netlink Route Constants
# ============================================================================

class RtMsgType(IntEnum):
    """Route message types (RTM_*)."""
    RTM_NEWLINK: int = 16
    RTM_DELLINK: int = 17
    RTM_GETLINK: int = 18
    RTM_NEWADDR: int = 20
    RTM_DELADDR: int = 21
    RTM_GETADDR: int = 22
    RTM_NEWROUTE: int = 24
    RTM_DELROUTE: int = 25
    RTM_GETROUTE: int = 26
    RTM_NEWNEIGH: int = 28
    RTM_DELNEIGH: int = 29
    RTM_GETNEIGH: int = 30
    RTM_NEWQDISC: int = 32
    RTM_DELQDISC: int = 33
    RTM_GETQDISC: int = 34
    RTM_NEWTCLASS: int = 36
    RTM_DELTCLASS: int = 37
    RTM_GETTCLASS: int = 38
    RTM_NEWTFILTER: int = 40
    RTM_DELTFILTER: int = 41
    RTM_GETTFILTER: int = 42
    RTM_NEWACTION: int = 48
    RTM_DELACTION: int = 49
    RTM_GETACTION: int = 50
    RTM_NEWPREFIX: int = 52
    RTM_GETPREFIX: int = 54


class RtFamily(IntEnum):
    """Address families."""
    AF_UNSPEC: int = 0
    AF_UNIX: int = 1
    AF_INET: int = 2
    AF_INET6: int = 10
    AF_NETLINK: int = 16


class RtScope(IntEnum):
    """Route scopes."""
    RT_SCOPE_UNIVERSE: int = 0
    RT_SCOPE_SITE: int = 200
    RT_SCOPE_LINK: int = 253
    RT_SCOPE_HOST: int = 254
    RT_SCOPE_NOWHERE: int = 255


class RtTable(IntEnum):
    """Routing tables."""
    RT_TABLE_UNSPEC: int = 0
    RT_TABLE_COMPAT: int = 252
    RT_TABLE_DEFAULT: int = 253
    RT_TABLE_MAIN: int = 254
    RT_TABLE_LOCAL: int = 255


class RtProtocol(IntEnum):
    """Routing protocols."""
    RTPROT_UNSPEC: int = 0
    RTPROT_REDIRECT: int = 1
    RTPROT_KERNEL: int = 2
    RTPROT_BOOT: int = 3
    RTPROT_STATIC: int = 4


class RtType(IntEnum):
    """Route types."""
    RTN_UNSPEC: int = 0
    RTN_UNICAST: int = 1
    RTN_LOCAL: int = 2
    RTN_BROADCAST: int = 3
    RTN_ANYCAST: int = 4
    RTN_MULTICAST: int = 5
    RTN_BLACKHOLE: int = 6
    RTN_UNREACHABLE: int = 7
    RTN_PROHIBIT: int = 8
    RTN_THROW: int = 9
    RTN_NAT: int = 10


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class NetlinkHeader:
    """Netlink message header."""
    length: int = 0
    msg_type: int = 0
    flags: int = 0
    seq: int = 0
    pid: int = 0

    HEADER_FORMAT: str = "IHHII"
    HEADER_SIZE: int = 16

    def pack(self) -> bytes:
        """Pack header to bytes."""
        return struct.pack(
            self.HEADER_FORMAT,
            self.length, self.msg_type, self.flags, self.seq, self.pid
        )

    @classmethod
    def unpack(cls, data: bytes) -> NetlinkHeader:
        """Unpack header from bytes."""
        if len(data) < cls.HEADER_SIZE:
            raise ValueError("Data too short for netlink header")
        length, msg_type, flags, seq, pid = struct.unpack(
            cls.HEADER_FORMAT, data[:cls.HEADER_SIZE]
        )
        return cls(length=length, msg_type=msg_type, flags=flags, seq=seq, pid=pid)


@dataclass
class NetlinkMessage:
    """A complete netlink message."""
    header: NetlinkHeader = field(default_factory=NetlinkHeader)
    payload: bytes = b""
    attributes: Dict[int, bytes] = field(default_factory=dict)

    def pack(self) -> bytes:
        """Pack complete message."""
        attr_data = self._pack_attributes()
        self.header.length = NetlinkHeader.HEADER_SIZE + len(self.payload) + len(attr_data)
        return self.header.pack() + self.payload + attr_data

    @classmethod
    def unpack(cls, data: bytes) -> NetlinkMessage:
        """Unpack message from bytes."""
        header = NetlinkHeader.unpack(data)
        payload_start = NetlinkHeader.HEADER_SIZE
        payload = data[payload_start:header.length]
        msg = cls(header=header, payload=payload)
        msg._unpack_attributes(payload)
        return msg

    def _pack_attributes(self) -> bytes:
        """Pack netlink attributes."""
        result = b""
        for attr_type, attr_data in self.attributes.items():
            attr_len = 4 + len(attr_data)
            attr_len_aligned = (attr_len + 3) & ~3
            result += struct.pack("HH", attr_len, attr_type)
            result += attr_data
            result += b"\x00" * (attr_len_aligned - attr_len)
        return result

    def _unpack_attributes(self, data: bytes) -> None:
        """Unpack netlink attributes."""
        offset = 0
        while offset < len(data):
            if offset + 4 > len(data):
                break
            attr_len, attr_type = struct.unpack("HH", data[offset:offset + 4])
            if attr_len < 4 or offset + attr_len > len(data):
                break
            self.attributes[attr_type] = data[offset + 4:offset + attr_len]
            offset += (attr_len + 3) & ~3

    def add_attribute(self, attr_type: int, data: bytes) -> None:
        """Add a netlink attribute."""
        self.attributes[attr_type] = data

    def get_attribute(self, attr_type: int) -> Optional[bytes]:
        """Get a netlink attribute."""
        return self.attributes.get(attr_type)


@dataclass
class NetlinkRouteAttr:
    """Route netlink attribute (RTA)."""
    rta_len: int = 0
    rta_type: int = 0
    data: bytes = b""

    ROUTE_ATTR_FORMAT: str = "HH"

    def pack(self) -> bytes:
        """Pack route attribute."""
        self.rta_len = 4 + len(self.data)
        return struct.pack(self.ROUTE_ATTR_FORMAT, self.rta_len, self.rta_type) + self.data

    @classmethod
    def unpack(cls, data: bytes) -> NetlinkRouteAttr:
        """Unpack route attribute."""
        if len(data) < 4:
            raise ValueError("Data too short for route attribute")
        rta_len, rta_type = struct.unpack(cls.ROUTE_ATTR_FORMAT, data[:4])
        return cls(rta_len=rta_len, rta_type=rta_type, data=data[4:rta_len])


@dataclass
class NetlinkSocket:
    """Netlink socket representation."""
    protocol: int = 0
    pid: int = 0
    bound: bool = False
    seq: int = 0
    multicast_groups: List[int] = field(default_factory=list)
    msg_handlers: Dict[int, Callable[[NetlinkMessage], NetlinkMessage]] = field(default_factory=dict)

    def next_seq(self) -> int:
        """Get next sequence number."""
        self.seq += 1
        return self.seq

    def register_handler(self, msg_type: int, handler: Callable[[NetlinkMessage], NetlinkMessage]) -> None:
        """Register a message handler."""
        self.msg_handlers[msg_type] = handler

    def handle_message(self, msg: NetlinkMessage) -> Optional[NetlinkMessage]:
        """Handle an incoming message."""
        handler = self.msg_handlers.get(msg.header.msg_type)
        if handler:
            return handler(msg)
        return None

    def join_group(self, group: int) -> int:
        """Join a multicast group."""
        if group not in self.multicast_groups:
            self.multicast_groups.append(group)
        return SUCCESS

    def leave_group(self, group: int) -> int:
        """Leave a multicast group."""
        if group in self.multicast_groups:
            self.multicast_groups.remove(group)
        return SUCCESS


@dataclass
class NetlinkRouteLink:
    """Network link (RTM_NEWLINK)."""
    ifindex: int = 0
    ifname: str = ""
    flags: int = 0
    mtu: int = 1500
    link_type: int = 0
    addr_len: int = 0
    hw_addr: bytes = b""
    oper_state: int = 0

    def pack(self) -> bytes:
        """Pack link info."""
        result = struct.pack("BxHiII", 0, 0, self.ifindex, self.flags, self.mtu)
        result += self.hw_addr.ljust(8, b"\x00")[:8]
        result += struct.pack("H", len(self.ifname.encode()))
        result += self.ifname.encode()
        return result


@dataclass
class NetlinkRouteAddr:
    """Network address (RTM_NEWADDR)."""
    ifindex: int = 0
    family: int = 0
    prefix_len: int = 0
    flags: int = 0
    scope: int = 0
    addr: bytes = b""

    def pack(self) -> bytes:
        """Pack address info."""
        result = struct.pack("BBBBi", self.family, self.prefix_len, self.flags, self.scope, self.ifindex)
        result += self.addr.ljust(16, b"\x00")[:16]
        return result


@dataclass
class NetlinkRouteEntry:
    """Route table entry (RTM_NEWROUTE)."""
    family: int = 0
    dst_len: int = 0
    src_len: int = 0
    tos: int = 0
    table: int = 0
    protocol: int = 0
    scope: int = 0
    type: int = 0
    flags: int = 0
    dst: bytes = b""
    src: bytes = b""
    gateway: bytes = b""
    oif: int = 0

    def pack(self) -> bytes:
        """Pack route entry."""
        result = struct.pack(
            "BBBBBBBBiI",
            self.family, self.dst_len, self.src_len, self.tos,
            self.table, self.protocol, self.scope, self.type,
            self.flags, self.oif
        )
        return result


# ============================================================================
# Netlink Subsystem
# ============================================================================

class Netlink:
    """Netlink socket subsystem."""
    def __init__(self) -> None:
        self.sockets: Dict[int, NetlinkSocket] = {}
        self.routes: List[NetlinkRouteEntry] = []
        self.links: Dict[int, NetlinkRouteLink] = {}
        self.addresses: List[NetlinkRouteAddr] = []
        self.lock: threading.Lock = threading.Lock()
        self._next_pid: int = 1
        self._next_ifindex: int = 1

    def create_socket(self, protocol: int) -> NetlinkSocket:
        """Create a netlink socket."""
        with self.lock:
            pid = self._next_pid
            self._next_pid += 1
            sock = NetlinkSocket(protocol=protocol, pid=pid, bound=True)
            self.sockets[pid] = sock
        return sock

    def close_socket(self, pid: int) -> int:
        """Close a netlink socket."""
        with self.lock:
            self.sockets.pop(pid, None)
        return SUCCESS

    def send_message(self, msg: NetlinkMessage, dest_pid: int = 0) -> int:
        """Send a netlink message."""
        data = msg.pack()
        if len(data) > 4096:
            return EMSGSIZE
        return SUCCESS

    def recv_message(self, pid: int) -> Optional[NetlinkMessage]:
        """Receive a netlink message."""
        return None

    def add_route(self, entry: NetlinkRouteEntry) -> int:
        """Add a route entry."""
        with self.lock:
            self.routes.append(entry)
        return SUCCESS

    def delete_route(self, entry: NetlinkRouteEntry) -> int:
        """Delete a route entry."""
        with self.lock:
            for i, r in enumerate(self.routes):
                if r.family == entry.family and r.dst == entry.dst:
                    self.routes.pop(i)
                    return SUCCESS
        return ENOENT

    def get_routes(self, family: int = 0) -> List[NetlinkRouteEntry]:
        """Get route entries."""
        if family:
            return [r for r in self.routes if r.family == family]
        return list(self.routes)

    def add_link(self, link: NetlinkRouteLink) -> int:
        """Add a network link."""
        with self.lock:
            if link.ifindex == 0:
                link.ifindex = self._next_ifindex
                self._next_ifindex += 1
            self.links[link.ifindex] = link
        return SUCCESS

    def delete_link(self, ifindex: int) -> int:
        """Delete a network link."""
        with self.lock:
            self.links.pop(ifindex, None)
        return SUCCESS

    def get_link(self, ifindex: int) -> Optional[NetlinkRouteLink]:
        """Get a network link by index."""
        return self.links.get(ifindex)

    def get_link_by_name(self, ifname: str) -> Optional[NetlinkRouteLink]:
        """Get a network link by name."""
        for link in self.links.values():
            if link.ifname == ifname:
                return link
        return None

    def add_address(self, addr: NetlinkRouteAddr) -> int:
        """Add a network address."""
        with self.lock:
            self.addresses.append(addr)
        return SUCCESS

    def delete_address(self, addr: NetlinkRouteAddr) -> int:
        """Delete a network address."""
        with self.lock:
            for i, a in enumerate(self.addresses):
                if a.ifindex == addr.ifindex and a.addr == addr.addr:
                    self.addresses.pop(i)
                    return SUCCESS
        return ENOENT

    def get_addresses(self, ifindex: int = 0) -> List[NetlinkRouteAddr]:
        """Get network addresses."""
        if ifindex:
            return [a for a in self.addresses if a.ifindex == ifindex]
        return list(self.addresses)

    def get_stats(self) -> Dict[str, int]:
        """Get netlink statistics."""
        return {
            "sockets": len(self.sockets),
            "routes": len(self.routes),
            "links": len(self.links),
            "addresses": len(self.addresses),
        }


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_netlink: Optional[Netlink] = None


def get_global_netlink() -> Netlink:
    """Get global Netlink instance."""
    global _global_netlink
    if _global_netlink is None:
        _global_netlink = Netlink()
    return _global_netlink
