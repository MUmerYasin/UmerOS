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
UmerOS /security - heuristic packet deny-list.

**This is not a firewall.** It is a small demonstration of a deny-list that sees
exactly two facts about a packet - the source address and the destination port -
and nothing else:

  * no payload or header inspection (the payload is never passed in);
  * no connection state; each packet is judged alone, apart from a sticky block
    list;
  * no direction, protocol or destination address, so no egress filtering;
  * nothing calls it and nothing enforces its verdict - it returns the string
    ``"DROP"`` to whoever asked.

It is kept because the deny-list itself is correct and tested, and because
deleting it would remove the only worked example of the rule format. Anything
that needs a real filter must live where the packets actually are (see
``kernel/`` and ``lib/iptables_libs.py``).

The historical docstring called this an "AI-driven firewall ... merged from
Deepseek code". Both claims were wrong and have been removed: there is no model
here, and no third-party source was ever vendored - see
``THIRD_PARTY_NOTICES.md``. The class name is kept because three other,
unrelated ``AIFirewall`` classes exist elsewhere in the tree (``ai/``,
``kernel/``) and renaming a dead class would add churn without removing a live
mislabel.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Iterable, Sequence
from typing import List, Set, Tuple, Union

log = logging.getLogger("UmerOS.Security.Firewall")

Rule = Tuple[str, Union[int, str], str]


class AIFirewall:
    """Heuristic packet deny-list. Not AI, and not a firewall.

    Decision order for one inbound packet:

    1. a source address already blocked is dropped - a DROP is **sticky**;
    2. the first matching rule in :attr:`rules` decides (insertion order, first
       match wins, so order is significant);
    3. otherwise a destination port in :attr:`heuristic_ports` is dropped;
    4. otherwise the packet is allowed.

    Step 3 is the "heuristic": on a host that has no business accepting SSH it
    is a reasonable default, but it is a port match, not a judgement about the
    traffic. Step 1 exists because the previous implementation recorded the
    source and then **allowed it on the next packet** - it failed open one
    packet after doing its job.
    """

    ALLOW = "ALLOW"
    DROP = "DROP"

    HEURISTIC_PORTS: Tuple[int, ...] = (22,)  # SSH

    def __init__(self, heuristic_ports: Iterable[int] = HEURISTIC_PORTS) -> None:
        self.heuristic_ports: Tuple[int, ...] = tuple(int(p) for p in heuristic_ports)
        self.rules: List[Rule] = []
        self.blocked_ips: Set[str] = set()
        self._lock = threading.Lock()

    # -- rules ----------------------------------------------------------
    def add_rule(self, rule: Sequence) -> Rule:
        """Add an ``(ip, port, action)`` rule and return it as stored.

        ``ip`` may be ``"*"`` (any source) and ``port`` may be ``"*"`` (any
        destination port). Rules are consulted by :meth:`analyze_packet` in
        insertion order; the first match wins.

        Raises:
            ValueError: for a malformed rule. The previous implementation
                appended whatever it was handed to a list nothing read, so a
                typo was silently inert.
        """
        if isinstance(rule, (str, bytes)) or not isinstance(rule, Sequence):
            raise ValueError("rule must be a 3-tuple (ip, port, action)")
        if len(rule) != 3:
            raise ValueError("rule must be a 3-tuple (ip, port, action)")
        ip, port, action = rule
        if not isinstance(ip, str) or not ip:
            raise ValueError("rule ip must be a non-empty string")
        if port != "*":
            if isinstance(port, bool) or not isinstance(port, int):
                raise ValueError("rule port must be '*' or an int")
            if not 0 <= port <= 65535:
                raise ValueError("rule port must be in 0..65535")
        if not isinstance(action, str) or action.upper() not in (self.ALLOW, self.DROP):
            raise ValueError("rule action must be ALLOW or DROP")
        stored: Rule = (ip, port, action.upper())
        with self._lock:
            self.rules.append(stored)
        return stored

    def clear_rules(self) -> int:
        """Remove every rule; return how many were dropped."""
        with self._lock:
            count = len(self.rules)
            self.rules.clear()
        return count

    # -- evaluation -----------------------------------------------------
    def analyze_packet(self, src_ip: str, dst_port: int) -> str:
        """Return :attr:`DROP` or :attr:`ALLOW` for one inbound packet.

        Only *src_ip* and *dst_port* are considered - see the module docstring
        for what that means this method cannot do.
        """
        with self._lock:
            if src_ip in self.blocked_ips:
                return self.DROP
            for ip, port, action in self.rules:
                if ip != "*" and ip != src_ip:
                    continue
                if port != "*" and port != dst_port:
                    continue
                if action == self.DROP:
                    self.blocked_ips.add(src_ip)
                    log.warning("Deny rule dropped %s -> port %s.", src_ip, dst_port)
                    return self.DROP
                return self.ALLOW
            if dst_port in self.heuristic_ports:
                self.blocked_ips.add(src_ip)
                log.warning(
                    "Heuristic deny: port %s from %s (no rule matched).",
                    dst_port,
                    src_ip,
                )
                return self.DROP
            return self.ALLOW

    # -- block list -----------------------------------------------------
    def is_blocked(self, src_ip: str) -> bool:
        """Return True when *src_ip* has been dropped and is now sticky."""
        with self._lock:
            return src_ip in self.blocked_ips

    def unblock(self, src_ip: str) -> bool:
        """Clear a sticky block. Returns True when it had been blocked."""
        with self._lock:
            if src_ip not in self.blocked_ips:
                return False
            self.blocked_ips.discard(src_ip)
        log.info("Unblocked %s.", src_ip)
        return True
