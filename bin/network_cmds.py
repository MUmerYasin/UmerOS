"""
UmerOS /bin Network Commands
=============================
Implements network utility commands.

TLDP Optional / Recommended:
  ifconfig - configure network interfaces
  ip       - show/manipulate routing, devices, policy routing
  route    - show/manipulate IP routing table
  arp      - manipulate the system ARP cache
"""

from __future__ import annotations

import re
from typing import List, Tuple, Any


class IfconfigCommand:
    """
    Configure network interfaces.

    Displays or configures network interface parameters.
    """

    description = "configure a network interface"

    def execute(self, args: List[str], stdin: Any = None, stdout: Any = None) -> Tuple[int, str]:
        if not args or args[0] in ("-a", "--all"):
            return self._show_all()

        iface = args[0]
        if iface == "-s":
            return self._show_short()

        if len(args) == 1:
            return self._show_interface(iface)

        return self._configure(iface, args[1:])

    def _show_all(self) -> Tuple[int, str]:
        lines = [
            "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500",
            "        inet 192.168.1.100  netmask 255.255.255.0  broadcast 192.168.1.255",
            "        inet6 fe80::1  prefixlen 64  scopeid 0x20<link>",
            "        ether 00:11:22:33:44:55  txqueuelen 1000  (Ethernet)",
            "        RX packets 12345  bytes 12345678 (12.3 MB)",
            "        RX errors 0  dropped 0  overruns 0  frame 0",
            "        TX packets 9876  bytes 9876543 (9.8 MB)",
            "        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0",
            "",
            "lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536",
            "        inet 127.0.0.1  netmask 255.0.0.0",
            "        loop  txqueuelen 1000  (Local Loopback)",
            "        RX packets 1234  bytes 123456 (123.4 KB)",
            "        TX packets 1234  bytes 123456 (123.4 KB)",
        ]
        return 0, "\n".join(lines)

    def _show_interface(self, iface: str) -> Tuple[int, str]:
        if iface == "lo":
            lines = [
                "lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536",
                "        inet 127.0.0.1  netmask 255.0.0.0",
                "        loop  txqueuelen 1000  (Local Loopback)",
            ]
        elif iface == "eth0":
            lines = [
                "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500",
                "        inet 192.168.1.100  netmask 255.255.255.0  broadcast 192.168.1.255",
                "        ether 00:11:22:33:44:55  txqueuelen 1000  (Ethernet)",
            ]
        else:
            return 1, f"ifconfig: {iface}: error fetching interface information: No such device"
        return 0, "\n".join(lines)

    def _show_short(self) -> Tuple[int, str]:
        lines = [
            "Iface   MTU   Met   RX-OK RX-ERR RX-DRP RX-OVR   TX-OK TX-ERR TX-DRP TX-OVR Flg",
            "eth0    1500  0     12345 0      0      0        9876  0      0      0      BMRU",
            "lo      65536 0     1234  0      0      0        1234  0      0      0      LRU",
        ]
        return 0, "\n".join(lines)

    def _configure(self, iface: str, options: List[str]) -> Tuple[int, str]:
        return 0, ""

    def _help(self) -> str:
        return (
            "Usage: ifconfig [-a] [-s] [INTERFACE]\n"
            "       ifconfig INTERFACE ADDRESSFamily ADDRESS [netmask MASK] [broadcast ADDR]\n"
            "\n"
            "Display or configure network interface parameters."
        )


class IpCommand:
    """
    Show/manipulate routing, devices, policy routing and tunnels.

    Unified network configuration utility (replacement for ifconfig/route/arp).
    """

    description = "show and manipulate routing, devices, and tunnels"

    def execute(self, args: List[str], stdin: Any = None, stdout: Any = None) -> Tuple[int, str]:
        if not args:
            return self._show_help()

        obj = args[0]
        cmd = args[1] if len(args) > 1 else "show"

        dispatch = {
            "addr": self._addr,
            "link": self._link,
            "route": self._route,
            "neigh": self._neigh,
            "br": self._br,
        }

        if obj in dispatch:
            return dispatch[obj](cmd, args[2:])
        elif obj in ("-V", "--version"):
            return 0, "ip utility, iproute2-ss210101"
        elif obj in ("-h", "--help"):
            return self._show_help()
        else:
            return 2, f"ip: unknown object \"{obj}\""

    def _addr(self, cmd: str, args: List[str]) -> Tuple[int, str]:
        if cmd == "show" or not cmd:
            lines = [
                "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 state UNKNOWN",
                "    inet 127.0.0.1/8 scope host lo",
                "       valid_lft forever preferred_lft forever",
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 state UP",
                "    inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0",
                "       valid_lft forever preferred_lft forever",
            ]
            return 0, "\n".join(lines)
        return 0, ""

    def _link(self, cmd: str, args: List[str]) -> Tuple[int, str]:
        if cmd == "show" or not cmd:
            lines = [
                "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 state UNKNOWN mode DEFAULT",
                "    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00",
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 state UP mode DEFAULT",
                "    link/ether 00:11:22:33:44:55 brd ff:ff:ff:ff:ff:ff",
            ]
            return 0, "\n".join(lines)
        return 0, ""

    def _route(self, cmd: str, args: List[str]) -> Tuple[int, str]:
        if cmd == "show" or not cmd:
            lines = [
                "default via 192.168.1.1 dev eth0 proto dhcp metric 100",
                "192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.100 metric 100",
            ]
            return 0, "\n".join(lines)
        return 0, ""

    def _neigh(self, cmd: str, args: List[str]) -> Tuple[int, str]:
        if cmd == "show" or not cmd:
            lines = [
                "192.168.1.1 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE",
            ]
            return 0, "\n".join(lines)
        return 0, ""

    def _br(self, cmd: str, args: List[str]) -> Tuple[int, str]:
        return 0, ""

    def _show_help(self) -> Tuple[int, str]:
        return 0, (
            "Usage: ip [ OPTIONS ] OBJECT { COMMAND | help }\n"
            "       ip [ -force ] -batch { FILE | - }\n"
            "\n"
            "OBJECT := { addr | link | route | neigh | br }"
        )


class RouteCommand:
    """
    Show/manipulate IP routing table.

    Displays or modifies the kernel routing table.
    """

    description = "show and manipulate the IP routing table"

    def execute(self, args: List[str], stdin: Any = None, stdout: Any = None) -> Tuple[int, str]:
        show_all = "-a" in args or "--all" in args
        show_numeric = "-n" in args or "--numeric" in args
        show_verbose = "-v" in args or "--verbose" in args

        lines = [
            "Kernel IP routing table",
            "Destination     Gateway         Genmask         Flags Metric Ref    Use Iface",
            "default         192.168.1.1     0.0.0.0         UG    100    0        0 eth0",
            "192.168.1.0     *               255.255.255.0   U     100    0        0 eth0",
            "127.0.0.0       *               255.0.0.0       U     0      0        0 lo",
        ]
        return 0, "\n".join(lines)


class ArpCommand:
    """
    Manipulate the system ARP cache.

    Displays and modifies the kernel's ARP table.
    """

    description = "manipulate the system ARP cache"

    def execute(self, args: List[str], stdin: Any = None, stdout: Any = None) -> Tuple[int, str]:
        show_all = "-a" in args or "--all" in args
        show_verbose = "-v" in args or "--verbose" in args

        lines = [
            "Address                  HWtype  HWaddress           Flags Mask            Iface",
            "192.168.1.1              ether   00:11:22:33:44:55   C                     eth0",
            "192.168.1.100            ether   AA:BB:CC:DD:EE:FF   C                     eth0",
        ]

        if "-a" in args or "--all" in args:
            lines = [
                "? (192.168.1.1) at 00:11:22:33:44:55 [ether] on eth0",
                "? (192.168.1.100) at AA:BB:CC:DD:EE:FF [ether] on eth0",
            ]

        return 0, "\n".join(lines)


def _selftest() -> bool:
    """Run self-tests for network_cmds module."""
    try:
        # IfconfigCommand
        ifc = IfconfigCommand()
        code, out = ifc.execute([])
        assert code == 0
        assert "eth0" in out or "lo" in out
        code2, out2 = ifc.execute(["-a"])
        assert code2 == 0

        # IpCommand
        ipc = IpCommand()
        code3, out3 = ipc.execute(["addr"])
        assert code3 == 0
        assert "inet" in out3
        code4, out4 = ipc.execute(["route"])
        assert code4 == 0
        code5, out5 = ipc.execute(["neigh"])
        assert code5 == 0
        code6, _ = ipc.execute([])
        assert code6 == 0

        # RouteCommand
        rc = RouteCommand()
        code7, out7 = rc.execute([])
        assert code7 == 0
        assert "Kernel IP routing table" in out7
        code8, _ = rc.execute(["-n"])
        assert code8 == 0

        # ArpCommand
        ac = ArpCommand()
        code9, out9 = ac.execute([])
        assert code9 == 0
        assert "HWtype" in out9
        code10, out10 = ac.execute(["-a"])
        assert code10 == 0

        return True
    except Exception as e:
        print(f"_selftest FAILED: {e}")
        return False
