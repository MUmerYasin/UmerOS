BLOCK = '''
async def _selftest_async() -> bool:
    """Self-test for the whole stack without leaving the loopback interface.

    Covers the H180 fail-closed DoH contract, the DoH helpers, the mDNS peer
    registry, the QoS classifier, the WireGuard wrapper and the full stack
    lifecycle.  No upstream network is contacted: the DoH endpoints point at
    two closed loopback ports so resolution must fail closed.
    """

    def fail(message: str) -> bool:
        print(f"network_stack selftest: {message}")
        return False

    # -- H180: DoH must fail closed, not silently degrade --------------------
    doh = DNSOverHTTPS(
        primary="http://127.0.0.1:1/dns-query",
        secondary="http://127.0.0.1:2/dns-query",
    )
    try:
        doh.resolve("example.com")
    except PermissionError:
        pass
    else:
        return fail("DoH degraded silently instead of failing closed")
    if doh.dnssec_status("example.com") is not None:
        return fail("dnssec_status() must be None before any successful answer")
    doh.flush_cache()  # must be a no-op on an empty cache

    # -- DoH helpers -----------------------------------------------------------
    if DNSOverHTTPS._normalize_hostname("  EXAMPLE.com.  ") != "example.com":
        return fail("DoH hostname normalization is wrong")
    if DNSOverHTTPS._rtype_int("a") != 1 or DNSOverHTTPS._rtype_int("aaaa") != 28:
        return fail("the DoH record-type mapping is wrong")
    if DNSOverHTTPS._rtype_int("NOPE") != 1:
        return fail("an unknown record type must default to A")
    if DNSOverHTTPS._dedupe(["1.1.1.1", "1.1.1.1", "8.8.8.8"]) != ["1.1.1.1", "8.8.8.8"]:
        return fail("DoH dedupe lost its order or dropped duplicates")

    # -- mDNS peer registry ------------------------------------------------------
    mdns = MDNSDiscovery()
    mdns.announce("node-a", "127.0.0.1", 7000)
    mdns.register_peer("node-b", "127.0.0.2", 7001)
    if mdns.peer_count() != 2 or len(mdns.discover()) != 2:
        return fail("the peer registry did not record both peers")
    if not mdns.remove_peer("node-b") or mdns.remove_peer("node-b"):
        return fail("remove_peer() must report whether a peer was removed")
    if mdns.status()["peers"] != 1:
        return fail("mdns.status() disagrees with the registry")
    if mdns.status()["service_type"] != MDNSDiscovery.SERVICE_TYPE:
        return fail("mdns.status() lost the service type")
    for blank in ("", "   "):
        try:
            mdns.announce(blank)
        except ValueError:
            continue
        return fail(f"announce() accepted a blank device name {blank!r}")
    try:
        mdns.register_peer("peer-c", "  ", 7002)
    except ValueError:
        pass
    else:
        return fail("register_peer() accepted a blank host")

    # -- heuristic QoS -------------------------------------------------------------
    qos = AINetworkQoS(low_bandwidth_kbps=1000)
    expectations = (
        (("zoom.us", 443), "video_conference"),
        (("sip.example", 5060), "voip"),
        (("live.stream", 1935), "streaming"),
        (("shell.example", 22), "interactive"),
        (("example.com", 443), "web_browse"),
        (("mirror.example", 21), "download"),
        (("example.com", 9999), "background"),
    )
    for (host, port), expected in expectations:
        got = qos.classify_connection(host, port)
        if got != expected:
            return fail(f"QoS classified {host}:{port} as {got!r}, want {expected!r}")
    if qos.get_priority("video_conference") <= qos.get_priority("background"):
        return fail("video_conference must outrank background traffic")
    if qos.get_priority("not-a-type") != 1:
        return fail("an unknown traffic type must fall back to priority 1")
    qos.update_bandwidth(500)
    if not qos.is_low_bandwidth() or qos.status()["bandwidth_kbps"] != 500:
        return fail("bandwidth bookkeeping is wrong")
    try:
        qos.update_bandwidth(-1)
    except ValueError:
        pass
    else:
        return fail("update_bandwidth() accepted a negative measurement")

    # -- the WireGuard wrapper without wg tooling -----------------------------------
    vpn = VPNClient("/etc/wireguard/wg0.conf")
    if vpn.is_connected:
        return fail("a fresh VPNClient cannot be connected")
    if set(vpn.status()) != {"available", "connected", "config", "wg", "wg_quick"}:
        return fail("VPNClient.status() lost a field")
    if vpn.status()["config"] != "/etc/wireguard/wg0.conf":
        return fail("VPNClient.status() lost the config path")

    # -- full stack lifecycle ---------------------------------------------------------
    stack = NetworkStack()
    if stack.running:
        return fail("a fresh NetworkStack must not be running")
    stack.start()
    if not stack.running:
        return fail("start() did not activate the stack")
    if await stack.resolve_async("127.0.0.1") != ["127.0.0.1"]:
        return fail("the stack could not resolve a literal address")
    if not await stack.internet.can_resolve("127.0.0.1"):
        return fail("InternetAccessManager.can_resolve() failed on a literal")
    status = stack.status()
    if status["running"] is not True:
        return fail("NetworkStack.status() disagrees with the running flag")
    if set(status) != {"running", "connections", "vpn", "mdns", "qos"}:
        return fail(f"NetworkStack.status() is malformed: {sorted(status)}")
    if stack.connection_table() != []:
        return fail("an idle stack must report an empty connection table")
    await stack.stop()
    if stack.running:
        return fail("stop() did not deactivate the stack")
    if stack.connection_table() != []:
        return fail("stop() left connection metadata behind")

    return True


def _selftest() -> bool:
    """Run the module self-test (async body driven through ``asyncio.run``)."""
    return asyncio.run(_selftest_async())


if __name__ == "__main__":
    import sys as _sys

    _ok = _selftest()
    print("network_stack selftest:", "OK" if _ok else "FAIL")
    _sys.exit(0 if _ok else 1)
'''
