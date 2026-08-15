"""/proc/net/* — networking tables.

All entries expose live kernel networking state.  When a real
``NetworkStack`` is attached to the adapter its connections and
interfaces are merged; otherwise coherent simulated data is served.

Covers: dev, tcp, udp, route, arp, unix, wireless, sockstat, icmp,
ipv6 (partial — udp6, tcp6, if_inet6), and per-bond directories.
"""
from __future__ import annotations

import socket
from typing import TYPE_CHECKING

from proc.nodes import ProcDir, ProcFile, ProcSymlink

if TYPE_CHECKING:
    from proc.procfs import ProcFileSystem


def _ifindex_map(adapter):
    return {"lo": 1, "quantum0": 2}


def _addr_to_hex(ip: str) -> str:
    try:
        return "".join(f"{int(o):02X}" for o in ip.split("."))
    except Exception:
        return "00000000"


def _format_sock(addr: str, port: int) -> str:
    return f"{_addr_to_hex(addr)}:{port:04X}"


def _header_ipv6(adapter) -> str:
    return (
        "  sl  local_address                         remote_address                        st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
    )


def register_net_entries(fs: "ProcFileSystem") -> None:
    adapter = fs.adapter

    net = ProcDir("net")
    fs.root.add(net)

    # ── dev — per-interface byte/packet/error stats ──────────────
    def _dev() -> str:
        ifaces = adapter.net_interfaces()
        hdr = (f"{'Inter-|   Receive':>35} "
               f"{'|  Transmit':>35}\n"
               f"{' face |bytes packets errs drop ...':>35} "
               f"{'|bytes packets errs drop ...':>35}")
        lines = [hdr]
        for iface in ifaces:
            n = iface["name"].ljust(10)
            rx = (f"{iface['rx_bytes']:>8} {iface['rx_packets']:>8} "
                  f"{iface['rx_errs']:>5} {iface['rx_drop']:>5} "
                  f"{iface['rx_fifo']:>5} {iface['rx_frame']:>5} "
                  f"{iface['rx_frame']:>5} {iface['rx_frame']:>5}")
            tx = (f"{iface['tx_bytes']:>8} {iface['tx_packets']:>8} "
                  f"{iface['tx_errs']:>5} {iface['tx_drop']:>5} "
                  f"{iface['tx_fifo']:>5} {iface['tx_colls']:>5} "
                  f"{iface['tx_carrier']:>5} {iface['tx_carrier']:>5}")
            lines.append(f"{n}|{rx}|{tx}")
        return "\n".join(lines) + "\n"

    net.add(ProcFile("dev", _dev))

    # ── tcp — TCP connections ─────────────────────────────────────
    def _tcp() -> str:
        lines = [
            "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode",
        ]
        local = _format_sock("0.0.0.0", 22)
        remote = _format_sock("0.0.0.0", 0)
        lines.append(f"   0: {local:<22} {remote:<22} 0A 00000000:00000000 00:00000000 00000000     0        0 12345 1 0000000000000000 100 0 0 10 0")
        local2 = _format_sock("0.0.0.0", 80)
        lines.append(f"   1: {local2:<22} {remote:<22} 0A 00000000:00000000 00:00000000 00000000     0        0 12346 1 0000000000000000 100 0 0 10 0")
        for conn in adapter.net_connections():
            dst = conn.get("host", "0.0.0.0")
            dport = int(conn.get("port", 0))
            l = _format_sock("0.0.0.0", dport)
            r = _format_sock(dst, dport)
            lines.append(f"   {len(lines)}: {l:<22} {r:<22} 01 00000000:00000000 00:00000000 00000000  1000        0 12347 1 0000000000000000 20 0 0 10 0")
        return "\n".join(lines) + "\n"

    net.add(ProcFile("tcp", _tcp))

    # ── udp ─────────────────────────────────────────────────────
    def _udp() -> str:
        hdr = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode"
        lines = [hdr]
        l = _format_sock("0.0.0.0", 68)
        r = _format_sock("0.0.0.0", 0)
        lines.append(f"   0: {l:<22} {r:<22} 07 00000000:00000000 00:00000000 00000000     0        0 54321 1 0000000000000000 0 0 0 10 0")
        l2 = _format_sock("0.0.0.0", 5353)
        lines.append(f"   1: {l2:<22} {r:<22} 07 00000000:00000000 00:00000000 00000000     0        0 54322 1 0000000000000000 0 0 0 10 0")
        return "\n".join(lines) + "\n"

    net.add(ProcFile("udp", _udp))

    # ── route ───────────────────────────────────────────────────
    def _route() -> str:
        return (
            "Iface\tDestination\tGateway \t\tFlags\tRefCnt\tUse\tMetric\tMask\t\t\tMTU\tWindow\tIRTT\n"
            "quantum0\t00000000\t0100A8C0\t\t0003\t0\t0\t0\t00000000\t1500\t0\t0\n"
            "quantum0\t0000A8C0\t00000000\t\t0001\t0\t0\t100\t00FFFFFF\t1500\t0\t0\n"
            "lo\t\t00000000\t0100A8C0\t\t0003\t0\t0\t0\t00000000\t65536\t0\t0\n"
        )

    net.add(ProcFile("route", _route))

    # ── arp ─────────────────────────────────────────────────────
    net.add(ProcFile("arp", lambda: (
        "IP address       HW type     Flags       HW address            Mask     Device\n"
        "10.0.2.2         0x1         0x2         52:55:0a:00:02:02     *        quantum0\n"
        "10.0.2.3         0x1         0x2         52:55:0a:00:02:03     *        quantum0\n"
    )))

    # ── unix — AF_UNIX domain sockets ───────────────────────────
    net.add(ProcFile("unix", lambda: (
        "Num       RefCount Protocol Flags    Type St Inode Path\n"
        "00000000 00000002 00000000 00000000 0001 01  1234 /run/systemd/private\n"
        "00000000 00000003 00000000 00000000 0001 01  5678 /var/run/umer.sock\n"
        "00000000 00000001 00000000 00010000 0001 01  91011\n"
    )))

    # ── wireless ─────────────────────────────────────────────────
    net.add(ProcFile("wireless", lambda: (
        "Inter-| sta-|   Quality   |   Discarded packets    | Missed | WE  |   TX\n"
        " face | tus | link level cnt| retry   frag  misc   | beacon | cnt | power\n"
        "quantum0: 0000   100.   100.     0      0      0      0     0   0   0 dBm\n"
    )))

    # ── sockstat ────────────────────────────────────────────────
    def _sockstat() -> str:
        tasks = adapter.tasks()
        n = len(tasks)
        return (
            f"sockets: used {n + 6}\n"
            f"TCP: inuse {max(n // 2, 1)} orphan 0 tw 0 alloc {n} mem 0\n"
            f"UDP: inuse {max(n // 4, 1)} mem 0\n"
            f"UDPLITE: inuse 0\n"
            f"RAW: inuse 0\n"
            f"FRAG: inuse 0 memory 0\n"
        )

    net.add(ProcFile("sockstat", _sockstat))

    # ── icmp ────────────────────────────────────────────────────
    def _icmp() -> str:
        uptime = max(adapter.uptime(), 1.0)
        return (
            "Icmp: msg 0 error 0\n"
            f"Icmp: InMsgs {int(uptime * 2)} InErrors 0 InCsumErrors 0 DestUnreachs 0 TimeExcds 0 ParmProbs 0 SrcQuenchs 0 Redirects 0 EchoReps 0 TimestampReps 0\n"
            f"Icmp: OutMsgs {int(uptime)} OutErrors 0 OutDestUnreachs 0 OutTimeExcds 0 OutParmProbs 0 OutSrcQuenchs 0 OutRedirects 0 OutEchoReps 0 OutTimestampReps 0\n"
        )

    net.add(ProcFile("icmp", _icmp))

    # ── snmp ────────────────────────────────────────────────────
    net.add(ProcFile("snmp", lambda: (
        "Ip: Forwarding DefaultTTL 64 InReceives 0 InHdrErrors 0 InAddrErrors 0 InUnknownProtos 0 InDiscards 0 InDelivers 0 OutRequests 0 OutDiscards 0 OutNoRoutes 0 ReasmTimeout 0 ReasmReqds 0 ReasmOKs 0 ReasmFails 0 FragOKs 0 FragFails 0 FragCreates 0\n"
        "Icmp: InMsgs 0 InErrors 0 InDestUnreachs 0 InTimeExcds 0 InParmProbs 0 InSrcQuenchs 0 InRedirects 0 InEchos 0 InEchoReps 0 OutMsgs 0 OutErrors 0 OutDestUnreachs 0 OutTimeExcds 0 OutParmProbs 0 OutSrcQuenchs 0 OutRedirects 0 OutEchos 0 OutEchoReps 0\n"
        "Tcp: RtoAlgorithm 1 RtoMin 200 RtoMax 120000 MaxConn -1 ActiveOpens 0 PassiveOpens 0 AttemptFails 0 EstabResets 0 CurrEstab 0 InSegs 0 OutSegs 0 RetransSegs 0 InErrs 0 OutRsts 0\n"
        "Udp: InDatagrams 0 NoPorts 0 InErrors 0 OutDatagrams 0\n"
    )))

    # ── IPv6 (partial, simulated) ──────────────────────────────
    net.add(ProcFile("if_inet6", lambda: (
        "00000000000000000000000000000001 01 80 10 80       lo\n"
        "fe800000000000000022a1a13bfa8ab1c 02 80 20 80     quantum0\n"
    )))

    def _tcp6() -> str:
        return _header_ipv6(adapter) + (
            "   0: 00000000000000000000000000000000:0000 00000000000000000000000000000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 0 0 0\n"
        )

    net.add(ProcFile("tcp6", _tcp6))
    net.add(ProcFile("udp6", lambda: _header_ipv6(adapter) +
        "   0: 00000000000000000000000000000000:1F90 00000000000000000000000000000000:0000 07 00000000:00000000 00:00000000 00000000     0        0 0 0 0\n"
    ))

    # ── /proc/net/rpc/ (NFS state stubs) ───────────────────────
    rpc = ProcDir("rpc")
    rpc.add(ProcFile("nfs", lambda: (
        "proc 2 0 1 2\n"
        "clnt 0 0 0 0\n"
    )))
    rpc.add(ProcFile("nfsd", lambda: (
        "rc 0 0 0 0 0 0 0 0 fh 0 0 0 0 0 0 0 0 0 io 0 0 th 0 0 0 0 0 0 0 0 0 ra 0 0 0 0 0 0\n"
    )))
    net.add(rpc)

    # ── /proc/net/bond0/ ────────────────────────────────────────
    bond0 = ProcDir("bond0")
    bond0.add(ProcFile("slaves", lambda: "\n"))
    bond0.add(ProcFile("link", lambda: "0\n"))
    bond0.add(ProcFile("fail_over_mac", lambda: "0\n"))
    bond0.add(ProcFile("mode", lambda: "balance-rr\n"))
    net.add(bond0)
