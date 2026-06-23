#!/usr/bin/env python3
"""
Umer OS Async TCP Server & Client

Provides non-blocking TCP socket management built on asyncio.
Equivalent to Linux's net/ipv4/tcp.c but in pure Python.
"""

import asyncio


class TCPServer:
    """Lightweight asyncio TCP server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self.host = host
        self.port = port
        self._server = None
        self._connections: list = []

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        print(f"[TCP] Connection from {addr}")
        self._connections.append(writer)
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                message = data.decode(errors='replace')
                print(f"[TCP] Received from {addr}: {message[:80]}")
                writer.write(b"ACK:" + data)
                await writer.drain()
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            writer.close()
            self._connections.remove(writer)
            print(f"[TCP] Connection closed: {addr}")

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        print(f"[TCP] Server listening on {self.host}:{self.port}")

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            print("[TCP] Server stopped.")


class TCPClient:
    """Simple asyncio TCP client."""

    async def connect(self, host: str, port: int, message: bytes) -> bytes:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.write(message)
            await writer.drain()
            response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            writer.close()
            return response
        except (OSError, asyncio.TimeoutError) as e:
            print(f"[TCP Client] Connection failed: {e}")
            return b""
