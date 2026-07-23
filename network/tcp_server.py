#!/usr/bin/env python3
"""Async TCP server and client utilities for UmerOS.

TODAY:
    Provides local service sockets and outbound TCP clients using asyncio.

EXPERIMENTAL:
    Kernel-level traffic accounting can later feed the AI QoS model.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Awaitable, Callable, DefaultDict, Optional

log = logging.getLogger("UmerOS.Network.TCP")

TCPHandler = Callable[[bytes, tuple[str, int] | str], bytes | Awaitable[bytes]]


class TCPServer:
    """Lightweight asyncio TCP server with basic abuse controls."""

    MAX_CONNECTIONS = 100
    MAX_CONNECTIONS_PER_IP = 10
    READ_TIMEOUT = 30.0
    MAX_MESSAGE_SIZE = 65_536
    RATE_LIMIT_WINDOW = 60.0

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9000,
        handler: Optional[TCPHandler] = None,
    ) -> None:
        """Initialize a TCP server.

        Args:
            host: Bind address.
            port: Bind port. Use ``0`` for an ephemeral test port.
            handler: Optional callback. Defaults to echoing ``b"ACK:" + data``.
        """
        self.host = host
        self.port = port
        self.handler = handler or self._default_handler
        self._server: asyncio.AbstractServer | None = None
        self._connections: set[asyncio.StreamWriter] = set()
        self._connection_counts: DefaultDict[str, dict[str, float]] = defaultdict(
            lambda: {"count": 0.0, "reset_time": time.time()}
        )
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        """Return True while the server is listening."""
        return self._server is not None

    async def start(self) -> None:
        """Start listening for TCP clients."""
        if self._server is not None:
            return
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        sockets = self._server.sockets or []
        if sockets:
            bound = sockets[0].getsockname()
            if isinstance(bound, tuple):
                self.host = str(bound[0])
                self.port = int(bound[1])
        log.info("TCP server listening on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Stop listening and close active clients."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

        writers = list(self._connections)
        for writer in writers:
            writer.close()
        for writer in writers:
            try:
                await writer.wait_closed()
            except OSError:
                pass
        self._connections.clear()
        log.info("TCP server stopped")

    async def _check_rate_limit(self, ip: str) -> bool:
        """Return False when an IP exceeds the per-window connection cap."""
        now = time.time()
        record = self._connection_counts[ip]
        if now - record["reset_time"] > self.RATE_LIMIT_WINDOW:
            record["count"] = 0.0
            record["reset_time"] = now
        if record["count"] >= self.MAX_CONNECTIONS_PER_IP:
            return False
        record["count"] += 1.0
        return True

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle one client connection."""
        peer = writer.get_extra_info("peername") or "unknown"
        ip = peer[0] if isinstance(peer, tuple) else "unknown"

        if not await self._check_rate_limit(ip):
            await self._send_and_close(writer, b"Rate limit exceeded.\n")
            return

        async with self._lock:
            if len(self._connections) >= self.MAX_CONNECTIONS:
                await self._send_and_close(writer, b"Server at capacity.\n")
                return
            self._connections.add(writer)

        try:
            data = await asyncio.wait_for(
                reader.read(self.MAX_MESSAGE_SIZE + 1),
                timeout=self.READ_TIMEOUT,
            )
            if not data:
                return
            if len(data) > self.MAX_MESSAGE_SIZE:
                await self._send_and_close(writer, b"Message too large.\n")
                return

            response = self.handler(data, peer)
            if asyncio.iscoroutine(response):
                response = await response
            writer.write(response)
            await writer.drain()
        except asyncio.TimeoutError:
            log.warning("TCP client timed out: %s", peer)
        except (ConnectionError, OSError) as exc:
            log.debug("TCP client disconnected: %s (%s)", peer, exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
            async with self._lock:
                self._connections.discard(writer)

    @staticmethod
    def _default_handler(data: bytes, _peer: tuple[str, int] | str) -> bytes:
        """Return the default ACK response."""
        return b"ACK:" + data

    @staticmethod
    async def _send_and_close(writer: asyncio.StreamWriter, data: bytes) -> None:
        """Send a final message and close a stream writer."""
        writer.write(data)
        try:
            await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass


class TCPClient:
    """Simple asyncio TCP client."""

    def __init__(self, timeout: float = 5.0) -> None:
        """Initialize the client."""
        self.timeout = timeout

    async def connect(self, host: str, port: int, message: bytes = b"") -> bytes:
        """Open a connection, optionally send a message, and read a response."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.timeout,
            )
            if message:
                writer.write(message)
                await writer.drain()
            response = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
            writer.close()
            await writer.wait_closed()
            return response
        except (OSError, asyncio.TimeoutError) as exc:
            log.warning("TCP client connection failed for %s:%d: %s", host, port, exc)
            return b""
