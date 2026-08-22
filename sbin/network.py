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
            print("ip: missing command", file=sys.stderr)
            return 1

        cmd = args[0]

        if cmd in ("-h", "--help", "help"):
            return 0

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
        if not args:
            args = ["-n"]

        if args[0] in ("-h", "--help"):
            return 0

        if args[0] == "add":
            print(f"route: adding route (args: {args[1:]})")
            return 0

        if args[0] == "del":
            print(f"route: deleting route (args: {args[1:]})")
            return 0

        show = args[0] in ("-n", "print")
        if show:
            print("Kernel IP routing table")
            print("Destination     Gateway         Genmask         Flags Metric Ref    Use Iface")
            print("0.0.0.0         192.168.1.1     0.0.0.0         UG    100    0        0 eth0")
            print("192.168.1.0     0.0.0.0         255.255.255.0   U     100    0        0 eth0")
            return 0
        print(f"route: operation '{args[0]}' not implemented", file=sys.stderr)
        return 1


def _selftest() -> bool:
    """Run self-tests for /sbin network commands."""
    tests_passed = 0
    tests_failed = 0

    def check(condition: bool, msg: str):
        nonlocal tests_passed, tests_failed
        if condition:
            tests_passed += 1
        else:
            tests_failed += 1
            print(f"  FAIL: {msg}")

    cmd = IfconfigCommand()
    check(cmd.name == "ifconfig", "ifconfig name")
    check(cmd.execute() == 0, "ifconfig no args -> 0")
    check(cmd.execute(["eth0"]) == 0, "ifconfig eth0 -> 0")

    cmd = IpCommand()
    check(cmd.name == "ip", "ip name")
    check(cmd.execute() == 1, "ip no args -> 1")
    check(cmd.execute(["address"]) == 0, "ip address -> 0")
    check(cmd.execute(["route"]) == 0, "ip route -> 0")
    check(cmd.execute(["link"]) == 0, "ip link -> 0")
    check(cmd.execute(["-h"]) == 0, "ip -h -> 0")
    check(cmd.execute(["help"]) == 0, "ip help -> 0")
    check(cmd.execute(["bad"]) == 1, "ip bad -> 1")

    cmd = RouteCommand()
    check(cmd.name == "route", "route name")
    check(cmd.execute() == 0, "route no args -> 0")
    check(cmd.execute(["-n"]) == 0, "route -n -> 0")
    check(cmd.execute(["add"]) == 0, "route add -> 0")
    check(cmd.execute(["del"]) == 0, "route del -> 0")
    check(cmd.execute(["-h"]) == 0, "route -h -> 0")
    check(cmd.execute(["bad"]) == 1, "route bad -> 1")

    print(f"sbin/network.py: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0
