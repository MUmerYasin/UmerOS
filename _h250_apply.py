"""H250 applier: relabel the toy firewall honestly and fix its fail-open bug.

Premise (drift-recon): TRUE, and worse than stated.
  * `analyze_packet` blocks `dst_port == 22` from any source - then records the
    source and **allows every later packet from it**, SSH included. It fails
    open one packet after doing its job.
  * `add_rule` appends to `self.rules`, which `analyze_packet` never reads.
  * No inspection, no state, no egress: the method is handed only src_ip and
    dst_port.
  * "AI-driven" is false; the module has no docstring at all.
  * `security/firewall.py` is **dead code** - nothing imports it. The
    `AIFirewall` in ai/, kernel/ and the docs is a different class.
  * "merged from Deepseek code" is unsubstantiated: no upstream, revision or
    licence anywhere, and `THIRD_PARTY_NOTICES.md` never mentions DeepSeek.
"""
from __future__ import annotations

import io

FW = "security/firewall.py"
NOTICES = "THIRD_PARTY_NOTICES.md"


def read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def eol_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


# ---------------------------------------------------------------------------
# 1. security/firewall.py
# ---------------------------------------------------------------------------
fw = read(FW)
original = fw
eol = eol_of(fw)


def block(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", eol)


START = "\nclass AIFirewall:"
assert fw.count(START) == 1, "exactly one class definition"
start = fw.index(START) + 1
header = fw[:start]
assert "GNU General Public License" in header, "GPL header must be preserved"
assert header.count("class ") == 0

NEW = block('''"""
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
''')

fw = header + NEW
assert fw != original
OLD_DOCSTRING = '    """AI-driven firewall (simple packet filter) merged from Deepseek code."""'
assert OLD_DOCSTRING not in fw, "the old class docstring must be gone"
assert "UmerOS /security - heuristic packet deny-list." in fw
assert "print(" not in fw, "print() must be replaced by logging"
assert "Author:  Umer OS Project" in fw
assert "License: GPL-3.0 (GNU General Public License v3)" in fw
assert "from __future__ import annotations" in fw
assert fw.count("class AIFirewall") == 1
write(FW, fw)
print("firewall.py: %d -> %d chars" % (len(original), len(fw)))

# ---------------------------------------------------------------------------
# 2. THIRD_PARTY_NOTICES.md - answer the licence question where the repo
#    already documents provenance
# ---------------------------------------------------------------------------
notices = read(NOTICES)
notices_original = notices
eol2 = eol_of(notices)

ANCHOR = "## Adding a vendored component"
assert notices.count(ANCHOR) == 1, "notices anchor"

SECTION = (
    "## Provenance notes\n"
    "\n"
    "**No DeepSeek source is vendored.** `security/firewall.py` used to carry the\n"
    "docstring claim \"AI-driven firewall (simple packet filter) merged from\n"
    "Deepseek code\". No upstream URL, pinned revision or license was ever\n"
    "recorded alongside it, so the claim could not be substantiated: it appears\n"
    "to describe *AI-assisted authoring* (code drafted with a language model)\n"
    "rather than source copied from a DeepSeek repository. AI-assisted authoring\n"
    "does not vendor third-party source, so no additional license attaches to it\n"
    "and no row is needed in the table above. The claim has been removed from the\n"
    "module, which was rewritten in this tree and is covered by GPL-3.0 like the\n"
    "rest of UmerOS.\n"
    "\n"
)
if "No DeepSeek source is vendored" in notices:
    print("notices: already applied, skipping")
else:
    notices = notices.replace(ANCHOR, SECTION.replace("\n", eol2) + ANCHOR, 1)
    assert notices != notices_original
    assert notices.count("No DeepSeek source is vendored") == 1
    write(NOTICES, notices)
    print("THIRD_PARTY_NOTICES.md: %d -> %d chars" % (len(notices_original), len(notices)))

# ---------------------------------------------------------------------------
# 3. verify
# ---------------------------------------------------------------------------
for path in (FW, NOTICES):
    raw = open(path, "rb").read()
    if path == FW:
        assert raw.count(b"\n") == raw.count(b"\r\n"), "bare LF in %s" % path
        compile(raw, path, "exec")
        print("%s: %d lines, CRLF intact, compiles" % (path, raw.count(b"\r\n")))
    else:
        assert raw.count(b"\r") == 0, "notices should stay LF"
        print("%s: %d lines, LF intact" % (path, raw.count(b"\n")))

print("OK")
