"""
UmerOS /sbin Network Commands
==============================
Network configuration command implementations.
ifconfig, ip, route
"""

from __future__ import annotations
import os
import sys
from abc import abstractmethod
from typing import Any, Dict, List, Optional


class SbinCommand:
    """Base class for /sbin commands."""

    name: str = ""
    description: str = ""
    usage: str = ""

    @abstractmethod
    def execute(self, args: Optional[List[str]] = None) -> int:
        pass

    def help(self) -> str:
        return f"Usage: {self.usage}\n{self.description}"


# ─── Network Commands ───────────────────────────────────────────────────────

class IfconfigCommand(SbinCommand):
    """Configure network interfaces."""
    name = "ifconfig"
    description = "Configure network interfaces"
    usage = "ifconfig [-a] [-v] [-s] [interface] [address]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            # Show all interfaces
            print("eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500")
            print("        inet 192.168.1.100  netmask 255.255.255.0  broadcast 192.168.1.255")
            print("        ether 00:1a:2b:3c:4d:5e")
            print("")
            print("lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536")
            print("        inet 127.0.0.1  netmask 255.0.0.0")
            return 0
        iface = args[0]
        print(f"ifconfig: configuring interface '{iface}'")
        return 0


class IpCommand(SbinCommand):
    """IP configuration and routing."""
    name = "ip"
    description = "IP configuration and routing"
    usage = "ip [-4|-6] addr {add|del} IFADDR dev IFACE"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            args = ["address"]

        cmd = args[0] if args else "address"

        if cmd in ("a", "addr", "address"):
            print("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536")
            print("    inet 127.0.0.1/8 scope host lo")
            print("2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500")
            print("    inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0")
            return 0

        if cmd in ("r", "route"):
            print("default via 192.168.1.1 dev eth0")
            print("192.168.1.0/24 dev eth0 src 192.168.1.100")
            return 0

        if cmd in ("l", "link"):
            print("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536")
            print("2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500")
            return 0

        print(f"ip: unknown command '{cmd}'", file=sys.stderr)
        return 1


class RouteCommand(SbinCommand):
    """Routing table manipulation."""
    name = "route"
    description = "Show or manipulate the IP routing table"
    usage = "route [-n] [-v] [-A family] {add|del|flush|change|print}"

    def execute(self, args: Optional[List[str]] = None) -> int:
        show = not args or args[0] in ("-n", "print")
        if show or args[0] == "-n":
            print("Kernel IP routing table")
            print("Destination     Gateway         Genmask         Flags Metric Ref    Use Iface")
            print("0.0.0.0         192.168.1.1     0.0.0.0         UG    100    0        0 eth0")
            print("192.168.1.0     0.0.0.0         255.255.255.0   U     100    0        0 eth0")
            return 0
        print(f"route: operation '{args[0]}' not implemented", file=sys.stderr)
        return 1
