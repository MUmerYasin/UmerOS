"""
UmerOS /lib/iptables — Netfilter Shared Library Manager
=========================================================
Implements the FHS subdirectory ``/lib/iptables`` which holds the
iptables / nftables shared library files used by ``xtables-multi`` (the
binary that dispatches to ``iptables``, ``ip6tables``, ``arptables`` and
``ebtables``).

Real shared objects follow the naming convention::

    libipt_XXX.so   — iptables match/target extension
    libip6t_XXX.so  — ip6tables match/target extension
    libxt_XXX.so    — xtables (IPv4 + IPv6) shared extension
    libebt_XXX.so   — ebtables (bridge) extension
    libarpt_XXX.so  — arptables extension

The actual .so files are tiny C glue libraries that the corresponding
``iptables-XXX`` user-space tool pulls in at startup.  UmerOS models the
catalogue here so that the firewall subsystem can ask which extensions
are available without shipping the real C code.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

log = logging.getLogger("UmerOS.Lib.IptablesLibs")


class ExtensionFamily(str, Enum):
    IPT  = "ipt"    # IPv4
    IP6T = "ip6t"   # IPv6
    XT   = "xt"     # family-agnostic
    EBT  = "ebt"    # bridge
    ARPT = "arpt"   # ARP


class ExtensionKind(str, Enum):
    MATCH  = "match"
    TARGET = "target"
    CHECKSUM = "checksum"


@dataclass
class IptablesExtension:
    """A single extension shared library."""
    name: str                       # e.g. "libxt_conntrack.so"
    family: ExtensionFamily
    kind: ExtensionKind
    path: str
    size: int = 0
    description: str = ""
    version: str = "1.8.10"
    md5: str = ""
    depends_on: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)  # extensions this enables


# Stock iptables extensions — the same set shipped by upstream iptables
_STOCK_EXTENSIONS: List[IptablesExtension] = [
    # Core / xtables
    IptablesExtension("libxt_conntrack.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_conntrack.so", size=12_288,
        description="Connection tracking state match", provides=["-m conntrack"]),
    IptablesExtension("libxt_state.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_state.so", size=10_240,
        description="Connection state match (legacy)", provides=["-m state"]),
    IptablesExtension("libxt_mark.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_mark.so", size=8_192,
        description="Match packet mark", provides=["-m mark"]),
    IptablesExtension("libxt_multiport.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_multiport.so", size=10_240,
        description="Match multiple ports", provides=["-m multiport"]),
    IptablesExtension("libxt_recent.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_recent.so", size=16_384,
        description="Match recent source addresses", provides=["-m recent"]),
    IptablesExtension("libxt_limit.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_limit.so", size=8_192,
        description="Rate-limit match", provides=["-m limit"]),
    IptablesExtension("libxt_mac.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_mac.so", size=6_144,
        description="Match MAC address", provides=["-m mac"]),
    IptablesExtension("libxt_owner.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_owner.so", size=8_192,
        description="Match packet owner", provides=["-m owner"]),
    IptablesExtension("libxt_tcp.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_tcp.so", size=12_288,
        description="TCP header match", provides=["-p tcp"]),
    IptablesExtension("libxt_udp.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_udp.so", size=10_240,
        description="UDP header match", provides=["-p udp"]),
    IptablesExtension("libxt_icmp.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_icmp.so", size=10_240,
        description="ICMP header match", provides=["-p icmp"]),
    IptablesExtension("libxt_LOG.so", ExtensionFamily.XT, ExtensionKind.TARGET,
        path="/lib/iptables/libxt_LOG.so", size=8_192,
        description="LOG target", provides=["-j LOG"]),
    IptablesExtension("libxt_REJECT.so", ExtensionFamily.XT, ExtensionKind.TARGET,
        path="/lib/iptables/libxt_REJECT.so", size=10_240,
        description="REJECT target", provides=["-j REJECT"]),
    IptablesExtension("libxt_DROP.so", ExtensionFamily.XT, ExtensionKind.TARGET,
        path="/lib/iptables/libxt_DROP.so", size=6_144,
        description="DROP target", provides=["-j DROP"]),
    IptablesExtension("libxt_ACCEPT.so", ExtensionFamily.XT, ExtensionKind.TARGET,
        path="/lib/iptables/libxt_ACCEPT.so", size=6_144,
        description="ACCEPT target", provides=["-j ACCEPT"]),
    IptablesExtension("libxt_NFLOG.so", ExtensionFamily.XT, ExtensionKind.TARGET,
        path="/lib/iptables/libxt_NFLOG.so", size=8_192,
        description="NFLOG target", provides=["-j NFLOG"]),
    IptablesExtension("libxt_TCPMSS.so", ExtensionFamily.XT, ExtensionKind.TARGET,
        path="/lib/iptables/libxt_TCPMSS.so", size=8_192,
        description="TCPMSS target (clamp MSS)", provides=["-j TCPMSS"]),
    IptablesExtension("libxt_addrtype.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_addrtype.so", size=8_192,
        description="Match address type", provides=["-m addrtype"]),
    IptablesExtension("libxt_comment.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_comment.so", size=6_144,
        description="Match packet comments", provides=["-m comment"]),
    IptablesExtension("libxt_pkttype.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_pkttype.so", size=6_144,
        description="Match packet type", provides=["-m pkttype"]),
    IptablesExtension("libxt_length.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_length.so", size=6_144,
        description="Match packet length", provides=["-m length"]),
    IptablesExtension("libxt_iprange.so", ExtensionFamily.XT, ExtensionKind.MATCH,
        path="/lib/iptables/libxt_iprange.so", size=8_192,
        description="Match IP range", provides=["-m iprange"]),
    # IPv4 only
    IptablesExtension("libipt_ecn.so", ExtensionFamily.IPT, ExtensionKind.MATCH,
        path="/lib/iptables/libipt_ecn.so", size=8_192,
        description="IPv4 ECN match"),
    # IPv6 only
    IptablesExtension("libip6t_hbh.so", ExtensionFamily.IP6T, ExtensionKind.MATCH,
        path="/lib/iptables/libip6t_hbh.so", size=8_192,
        description="IPv6 Hop-by-Hop match"),
    # Bridge
    IptablesExtension("libebt_802_3.so", ExtensionFamily.EBT, ExtensionKind.MATCH,
        path="/lib/iptables/libebt_802_3.so", size=8_192,
        description="802.3 frame match (ebtables)"),
    IptablesExtension("libebt_log.so", ExtensionFamily.EBT, ExtensionKind.TARGET,
        path="/lib/iptables/libebt_log.so", size=6_144,
        description="Bridge log target"),
    # ARP
    IptablesExtension("libarpt_mangle.so", ExtensionFamily.ARPT, ExtensionKind.TARGET,
        path="/lib/iptables/libarpt_mangle.so", size=8_192,
        description="ARP mangle target"),
]


class IptablesLibraryManager:
    """
    Manages ``/lib/iptables`` shared libraries.

    UmerOS can also physically place stub files there (the on-disk
    representation in the host FS) and load metadata about them.
    """

    def __init__(self, lib_path: str = "/lib", iptables_path: str = "/lib/iptables") -> None:
        self.lib_path = Path(lib_path)
        self.iptables_path = Path(iptables_path)
        self._extensions: Dict[str, IptablesExtension] = {
            e.name: e for e in _STOCK_EXTENSIONS
        }

    # ── listing / lookup ──────────────────────────────────────────

    def list_extensions(self) -> List[IptablesExtension]:
        return list(self._extensions.values())

    def list_by_family(self, family: ExtensionFamily) -> List[IptablesExtension]:
        return [e for e in self._extensions.values() if e.family == family]

    def list_by_kind(self, kind: ExtensionKind) -> List[IptablesExtension]:
        return [e for e in self._extensions.values() if e.kind == kind]

    def find_extension(self, name: str) -> Optional[IptablesExtension]:
        # Allow callers to pass either the full filename or the suffix
        if name in self._extensions:
            return self._extensions[name]
        if not name.startswith("lib"):
            name = "lib" + name
        if not name.endswith(".so"):
            name = name + ".so"
        return self._extensions.get(name)

    def find_by_capability(self, capability: str) -> List[IptablesExtension]:
        """
        Return every extension that provides a given iptables capability
        (e.g. ``-m conntrack`` or ``-j LOG``).
        """
        return [e for e in self._extensions.values() if capability in e.provides]

    def register_extension(
        self,
        name: str,
        family: ExtensionFamily,
        kind: ExtensionKind,
        description: str = "",
        provides: Optional[List[str]] = None,
        depends_on: Optional[List[str]] = None,
    ) -> IptablesExtension:
        """Register a new iptables extension (or replace an existing one)."""
        if not name.startswith("lib"):
            name = "lib" + name
        if not name.endswith(".so"):
            name = name + ".so"
        ext = IptablesExtension(
            name=name,
            family=family,
            kind=kind,
            path=f"/lib/iptables/{name}",
            description=description,
            provides=list(provides or []),
            depends_on=list(depends_on or []),
        )
        self._extensions[name] = ext
        return ext

    def unregister_extension(self, name: str) -> bool:
        return self._extensions.pop(name, None) is not None

    # ── on-disk materialisation ──────────────────────────────────

    def materialise_stubs(self, root: str = "/") -> int:
        """
        Write tiny placeholder files into the real filesystem so the directory
        actually looks like ``/lib/iptables`` would on a real system.
        Returns the number of files written.
        """
        target = Path(root) / "lib" / "iptables"
        target.mkdir(parents=True, exist_ok=True)
        written = 0
        for ext in self._extensions.values():
            p = target / ext.name
            if not p.exists():
                # ELF-like magic so it looks at least vaguely like a shared obj
                p.write_bytes(
                    b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
                    + f"UmerOS stub for {ext.name} ({ext.description})\n".encode()
                )
                written += 1
        return written

    # ── summary ──────────────────────────────────────────────────

    def get_summary(self) -> Dict:
        families = {f.value: len(self.list_by_family(f)) for f in ExtensionFamily}
        kinds    = {k.value: len(self.list_by_kind(k))    for k in ExtensionKind}
        return {
            "total_extensions": len(self._extensions),
            "by_family": families,
            "by_kind": kinds,
            "total_size_bytes": sum(e.size for e in self._extensions.values()),
            "directory": str(self.iptables_path),
        }
