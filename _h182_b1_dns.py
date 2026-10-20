BLOCK = '''
async def _selftest_async() -> bool:
    """Self-test for the resolver: normalization, literals, cache, validation.

    Everything here is deterministic; the only real socket work is a loopback
    ``getaddrinfo`` for ``"localhost"``, which every supported platform
    answers from its own hosts file.
    """

    def fail(message: str) -> bool:
        print(f"dns_resolver selftest: {message}")
        return False

    # -- hostname normalization -------------------------------------------
    if DNSResolver._normalize_hostname("  Example.COM.  ") != "example.com":
        return fail("hostname is not stripped / lower-cased / un-dotted")
    for bad in ("", "   ", "bad host", "two words"):
        try:
            DNSResolver._normalize_hostname(bad)
        except ValueError:
            continue
        return fail(f"_normalize_hostname accepted {bad!r}")

    # -- literal addresses never reach the resolver ------------------------
    resolver = DNSResolver()
    if await resolver.resolve("127.0.0.1") != "127.0.0.1":
        return fail("a literal IPv4 was not returned verbatim")
    if await resolver.resolve_all("::1") != ["::1"]:
        return fail("a literal IPv6 was not returned verbatim")
    if resolver.cache_size() != 0:
        return fail("a literal answer must not occupy a cache slot")

    # -- the TTL cache is actually consulted --------------------------------
    resolver._cache[("cached.test", socket.AF_UNSPEC)] = DNSCacheEntry(
        ("192.0.2.10",), time.time() + 60.0
    )
    if await resolver.resolve_all("cached.test") != ["192.0.2.10"]:
        return fail("a live cache entry was not served")
    if resolver.cache_size() != 1:
        return fail("cache_size() ignored the seeded entry")
    resolver.flush_cache()
    if resolver.cache_size() != 0:
        return fail("flush_cache() left entries behind")

    # -- reverse lookup validates its input before any egress ----------------
    for bad in ("", "not-an-ip", "999.1.1.1", "localhost"):
        try:
            await resolver.reverse_lookup(bad)
        except ValueError:
            continue
        return fail(f"reverse_lookup accepted {bad!r}")

    # -- order-preserving de-duplication -------------------------------------
    if DNSResolver._dedupe(["a", "b", "a", "c", "b", "a"]) != ["a", "b", "c"]:
        return fail("dedupe did not preserve first-seen order")

    # -- the real chokepoint: loopback getaddrinfo through the gate -----------
    loopback = await resolver.resolve_all("localhost", family=socket.AF_INET)
    if "127.0.0.1" not in loopback:
        return fail(f"localhost did not resolve to a loopback address: {loopback!r}")
    if any(not ipaddress.ip_address(a).is_loopback for a in loopback):
        return fail("a non-loopback address came back for localhost")

    return True


def _selftest() -> bool:
    """Run the module self-test (async body driven through ``asyncio.run``)."""
    return asyncio.run(_selftest_async())


if __name__ == "__main__":
    import sys as _sys

    _ok = _selftest()
    print("dns_resolver selftest:", "OK" if _ok else "FAIL")
    _sys.exit(0 if _ok else 1)
'''
