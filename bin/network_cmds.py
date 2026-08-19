"""Network configuration commands: ifconfig, ip, route, arp."""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Tuple


class IfconfigCommand:
    """Configure network interfaces."""

    name = "ifconfig"
    description = "configure a network interface"

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if "--help" in args or "-h" in args:
            print(self._usage(), file=stdout or sys.stdout)
            return 0
        if "--version" in args:
            print("ifconfig (UmerOS) 1.0", file=stdout or sys.stdout)
            return 0
        if not args or args[0] in ("-a", "--all"):
            self._show_all(stdout)
            return 0
        if args[0] == "-s":
            self._show_short(stdout)
            return 0
        if args[0] in ("--help", "-h"):
            print(self._usage(), file=stdout or sys.stdout)
            return 0
        self._show_all(stdout)
        return 0

    def _show_all(self, output: Any = None) -> None:
        out = output or sys.stdout
        print("eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500", file=out)
        print("        inet 192.168.1.100  netmask 255.255.255.0  broadcast 192.168.1.255", file=out)
        print("        inet6 fe80::1  prefixlen 64  scopeid 0x20<link>", file=out)
        print("        ether 00:11:22:33:44:55  txqueuelen 1000  (Ethernet)", file=out)
        print("", file=out)
        print("lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536", file=out)
        print("        inet 127.0.0.1  netmask 255.0.0.0", file=out)
        print("        loop  txqueuelen 1000  (Local Loopback)", file=out)

    def _show_short(self, output: Any = None) -> None:
        out = output or sys.stdout
        print("eth0  UP  192.168.1.100  255.255.255.0", file=out)

    def _usage(self) -> str:
        return (
            "Usage: ifconfig [interface] [-a] [-s]\n"
            "Configure network interfaces.\n\n"
            "  -a, --all    display all interfaces\n"
            "  -s           brief summary\n"
            "  -h, --help   display this help"
        )


class IpCommand:
    """IP configuration utility."""

    name = "ip"
    description = "show / manipulate routing, devices, policy routing and tunnels"

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if "--help" in args or "-h" in args:
            print(self._usage(), file=stdout or sys.stdout)
            return 0
        if "--version" in args:
            print("ip (UmerOS) 1.0", file=stdout or sys.stdout)
            return 0
        if not args:
            self._show_addr(stdout)
            return 0
        subcmd = args[0]
        if subcmd == "addr":
            self._show_addr(stdout)
        elif subcmd == "link":
            self._show_link(stdout)
        elif subcmd == "route":
            self._show_route(stdout)
        elif subcmd == "neigh":
            self._show_neigh(stdout)
        elif subcmd == "br":
            self._show_bridge(stdout)
        else:
            self._show_addr(stdout)
        return 0

    def _show_addr(self, output: Any = None) -> None:
        out = output or sys.stdout
        print("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN", file=out)
        print("    inet 127.0.0.1/8 scope host lo", file=out)
        print("2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP", file=out)
        print("    inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0", file=out)

    def _show_link(self, output: Any = None) -> None:
        out = output or sys.stdout
        print("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN", file=out)
        print("    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00", file=out)
        print("2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP", file=out)
        print("    link/ether 00:11:22:33:44:55 brd ff:ff:ff:ff:ff:ff", file=out)

    def _show_route(self, output: Any = None) -> None:
        out = output or sys.stdout
        print("default via 192.168.1.1 dev eth0", file=out)
        print("192.168.1.0/24 dev eth0 src 192.168.1.100", file=out)

    def _show_neigh(self, output: Any = None) -> None:
        out = output or sys.stdout
        print("192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE", file=out)

    def _show_bridge(self, output: Any = None) -> None:
        out = output or sys.stdout
        print("bridge name  bridge id          STP enabled  interfaces", file=out)

    def _usage(self) -> str:
        return (
            "Usage: ip [ addr | link | route | neigh | br ]\n"
            "Show / manipulate routing, devices, policy routing and tunnels.\n\n"
            "  addr       show IP addresses\n"
            "  link       show network interfaces\n"
            "  route      show routing table\n"
            "  neigh      show ARP table\n"
            "  br         show bridges\n"
            "  -h, --help display this help"
        )


class RouteCommand:
    """Show or manipulate the IP routing table."""

    name = "route"
    description = "show / manipulate the IP routing table"

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if "--help" in args or "-h" in args:
            print(self._usage(), file=stdout or sys.stdout)
            return 0
        if "--version" in args:
            print("route (UmerOS) 1.0", file=stdout or sys.stdout)
            return 0
        if not args:
            self._show_route(stdout)
            return 0
        if args[0] == "-n":
            self._show_route(stdout)
            return 0
        if args[0] == "add":
            return 0
        if args[0] == "del":
            return 0
        self._show_route(stdout)
        return 0

    def _show_route(self, output: Any = None) -> None:
        out = output or sys.stdout
        print("Kernel IP routing table", file=out)
        print("Destination     Gateway         Genmask         Metric Ref    Use Iface", file=out)
        print("0.0.0.0         192.168.1.1     0.0.0.0         0      0        0 eth0", file=out)
        print("192.168.1.0     0.0.0.0         255.255.255.0   0      0        0 eth0", file=out)

    def _usage(self) -> str:
        return (
            "Usage: route [-n] [add|del]\n"
            "Show or manipulate the IP routing table.\n\n"
            "  -n         numeric output\n"
            "  add        add a route\n"
            "  del        delete a route\n"
            "  -h, --help display this help"
        )


class ArpCommand:
    """Manipulate the ARP cache."""

    name = "arp"
    description = "manipulate the ARP cache"

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if "--help" in args or "-h" in args:
            print(self._usage(), file=stdout or sys.stdout)
            return 0
        if "--version" in args:
            print("arp (UmerOS) 1.0", file=stdout or sys.stdout)
            return 0
        if not args:
            self._show_arp(stdout)
            return 0
        if args[0] == "-a":
            self._show_arp(stdout)
            return 0
        if args[0] == "-n":
            self._show_arp(stdout)
            return 0
        self._show_arp(stdout)
        return 0

    def _show_arp(self, output: Any = None) -> None:
        out = output or sys.stdout
        print("Address                  HWtype  HWaddress           Flags Mask            Iface", file=out)
        print("192.168.1.1              ether   00:11:22:33:44:55   C                     eth0", file=out)

    def _usage(self) -> str:
        return (
            "Usage: arp [-a] [-n]\n"
            "Manipulate the ARP cache.\n\n"
            "  -a         display all entries\n"
            "  -n         numeric output\n"
            "  -h, --help display this help"
        )
