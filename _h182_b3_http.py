BLOCK = '''
async def _selftest_async() -> bool:
    """Self-test for URL validation, the SSRF classifier and a real fetch.

    The round-trip runs against a throwaway ``http.server`` on an ephemeral
    loopback port, so the test never touches the internet -- it only needs
    loopback TCP, the same assumption every other test in this repo makes.
    """

    def fail(message: str) -> bool:
        print(f"http_client selftest: {message}")
        return False

    # -- URL validation -----------------------------------------------------
    for bad in ("", "   ", "ftp://example.com/x", "http://", "https:///x", "file:///etc/passwd"):
        try:
            HTTPClient._validate_url(bad)
        except ValueError:
            continue
        return fail(f"_validate_url accepted {bad!r}")
    if HTTPClient._validate_url("https://example.com/a?b=1") != "https://example.com/a?b=1":
        return fail("_validate_url did not round-trip a valid URL")

    # -- SSRF defense-in-depth ----------------------------------------------
    for scope in ("is_private", "is_loopback", "is_link_local", "is_reserved", "is_multicast"):
        if scope not in _SSRF_BLOCKED_SCOPES:
            return fail(f"the SSRF scope table lost {scope!r}")
    for internal in (
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.1",
        "172.16.0.9",
        "169.254.169.254",
        "224.0.0.1",
        "0.0.0.0",
        "",
        "[::1]",
    ):
        if not _host_is_internal(internal):
            return fail(f"{internal!r} must be classified as internal")
    if _host_is_internal("8.8.8.8"):
        return fail("a public address must not be classified as internal")
    if not _host_is_internal("no such host"):
        return fail("an unresolvable host must be treated as internal (fail-closed)")

    # -- HTTPResponse normalisation ------------------------------------------
    good = HTTPResponse(200, '{"value": 42}', {"Content-Type": "application/json"}, "http://x/")
    if not good.ok or good.json() != {"value": 42}:
        return fail("HTTPResponse.ok/json() disagree with the body")
    if HTTPResponse(404, "", {}, "http://x/").ok:
        return fail("a 404 must not be reported as ok")
    as_dict = good.as_dict()
    if as_dict["status"] != 200 or as_dict["ok"] is not True:
        return fail("as_dict() lost the response fields")
    if as_dict["body"] != '{"value": 42}' or as_dict["url"] != "http://x/":
        return fail("as_dict() lost the body or url")

    # -- real loopback round-trip ---------------------------------------------
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class _Handler(BaseHTTPRequestHandler):
        """Tiny fixture: /health, /data.json, /echo (POST), everything else 404."""

        def _send(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header(
                "Content-Type",
                "application/json" if body.startswith(b"{") else "text/plain",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            if self.path == "/health":
                self._send(200, b"pong")
            elif self.path == "/data.json":
                self._send(200, b'{"value": 42}')
            else:
                self._send(404, b"not found")

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            self._send(200, b"posted:" + body)

        def log_message(self, *_args: object) -> None:
            """Silence the per-request stderr noise."""

    fixture = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = fixture.server_address[1]
    worker = threading.Thread(target=fixture.serve_forever, daemon=True)
    worker.start()
    try:
        client = HTTPClient()
        base = f"http://127.0.0.1:{port}"
        health = await client.get(f"{base}/health")
        if health["status"] != 200 or health["body"] != "pong":
            return fail(f"GET /health returned {health!r}")
        if await client.fetch_json(f"{base}/data.json") != {"value": 42}:
            return fail("fetch_json() did not parse the fixture body")
        posted = await client.post_json(f"{base}/echo", {"a": 1})
        if posted["status"] != 200 or posted["body"] != 'posted:{"a": 1}':
            return fail(f"post_json() round-trip failed: {posted!r}")
        missing = await client.get(f"{base}/missing")
        if missing["status"] != 404:
            return fail(f"an unknown path should be a 404, got {missing['status']}")

        # the response size cap must bite before the body is handed over
        capped = await HTTPClient(max_response_bytes=2).get(f"{base}/health")
        if capped["status"] != 0 or "size limit" not in capped["body"]:
            return fail(f"the response size cap did not bite: {capped!r}")

        # a bad scheme is refused before any socket is opened
        try:
            await client.get("ftp://example.com/")
        except ValueError:
            pass
        else:
            return fail("request() accepted a non-HTTP scheme")
    finally:
        fixture.shutdown()
        fixture.server_close()
        worker.join(timeout=5)

    return True


def _selftest() -> bool:
    """Run the module self-test (async body driven through ``asyncio.run``)."""
    return asyncio.run(_selftest_async())


if __name__ == "__main__":
    import sys as _sys

    _ok = _selftest()
    print("http_client selftest:", "OK" if _ok else "FAIL")
    _sys.exit(0 if _ok else 1)
'''
