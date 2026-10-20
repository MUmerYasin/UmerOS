BLOCK = '''
async def _selftest_async() -> bool:
    """Self-test for the abuse controls and a real loopback round-trip.

    Three guards are exercised end to end: the per-IP connection cap, the
    rate-limit window rollover, and the maximum message size.  The round-trip
    binds an ephemeral port on 127.0.0.1 so nothing leaves the host.
    """

    def fail(message: str) -> bool:
        print(f"tcp_server selftest: {message}")
        return False

    # -- abuse control 1: the per-IP connection cap ---------------------------
    limiter = TCPServer(port=0)
    for _ in range(TCPServer.MAX_CONNECTIONS_PER_IP):
        if not await limiter._check_rate_limit("203.0.113.9"):
            return fail("the per-IP cap rejected a connection inside the limit")
    if await limiter._check_rate_limit("203.0.113.9"):
        return fail("the per-IP connection cap is not enforced")

    # The window must roll over on its own, without any sleeping.
    record = limiter._connection_counts["203.0.113.9"]
    record["reset_time"] = time.time() - (TCPServer.RATE_LIMIT_WINDOW + 1.0)
    if not await limiter._check_rate_limit("203.0.113.9"):
        return fail("the rate-limit window never resets")

    # -- the default handler still ACKs ---------------------------------------
    if TCPServer._default_handler(b"ping", "127.0.0.1") != b"ACK:ping":
        return fail("the default handler lost its b'ACK:' prefix")

    # -- a live server on an ephemeral port ------------------------------------
    live = TCPServer(host="127.0.0.1", port=0)
    await live.start()
    if not live.is_running or live.port <= 0:
        return fail("the live server did not bind an ephemeral port")
    try:
        if await TCPClient().connect(live.host, live.port, b"ping") != b"ACK:ping":
            return fail("the loopback echo round-trip failed")

        # abuse control 2: an oversized message is refused, not buffered.
        oversized = await TCPClient().connect(
            live.host, live.port, b"x" * (TCPServer.MAX_MESSAGE_SIZE + 1)
        )
        if oversized != b"Message too large.\\n":
            return fail(f"an oversized message was not refused: {oversized!r}")

        # abuse control 3: the cap is enforced over real sockets.  Two
        # connections (echo + oversized) already consumed this window.
        for _ in range(TCPServer.MAX_CONNECTIONS_PER_IP - 2):
            await TCPClient().connect(live.host, live.port, b"")
        refused = await TCPClient().connect(live.host, live.port, b"")
        if refused != b"Rate limit exceeded.\\n":
            return fail(f"the per-IP cap was not enforced over sockets: {refused!r}")
    finally:
        await live.stop()
    if live.is_running:
        return fail("stop() left the server in the running state")

    # -- the client fails soft when nothing is listening -----------------------
    if await TCPClient().connect(live.host, live.port, b"") != b"":
        return fail("a client to a closed port should return b''")

    # -- the global cap must stay above the per-IP cap --------------------------
    if TCPServer.MAX_CONNECTIONS_PER_IP >= TCPServer.MAX_CONNECTIONS:
        return fail("the per-IP cap must stay below the global connection cap")

    return True


def _selftest() -> bool:
    """Run the module self-test (async body driven through ``asyncio.run``)."""
    return asyncio.run(_selftest_async())


if __name__ == "__main__":
    import sys as _sys

    _ok = _selftest()
    print("tcp_server selftest:", "OK" if _ok else "FAIL")
    _sys.exit(0 if _ok else 1)
'''
