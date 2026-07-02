#!/usr/bin/env python3
"""
Umer OS Async TCP Server & Client

Provides non-blocking TCP socket management built on asyncio.
Equivalent to Linux's net/ipv4/tcp.c but in pure Python.
"""

import asyncio
import time
from collections import defaultdict


class TCPServer:
    """Lightweight asyncio TCP server with DoS protection."""
    
    # Security limits
    MAX_CONNECTIONS = 100
    MAX_CONNECTIONS_PER_IP = 10
    READ_TIMEOUT = 30.0
    MAX_MESSAGE_SIZE = 65536
    RATE_LIMIT_WINDOW = 60  # seconds

    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self.host = host
        self.port = port
        self._server = None
        self._connections = set()
        self._connection_counts = defaultdict(lambda: {'count': 0, 'reset_time': time.time()})
        self._lock = asyncio.Lock()

    async def _check_rate_limit(self, ip: str) -> bool:
        """Check if IP has exceeded rate limit."""
        now = time.time()
        record = self._connection_counts[ip]
        
        if now - record['reset_time'] > self.RATE_LIMIT_WINDOW:
            record['count'] = 0
            record['reset_time'] = now
        
        if record['count'] >= self.MAX_CONNECTIONS_PER_IP:
            return False
        
        record['count'] += 1
        return True

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        ip = addr[0] if isinstance(addr, tuple) else 'unknown'
        
        # Rate limiting check
        if not await self._check_rate_limit(ip):
            print(f"[TCP] Rate limit exceeded for {ip}")
            writer.write(b"Rate limit exceeded.\n")
            await writer.drain()
            writer.close()
            return
        
        # Connection limit check
        async with self._lock:
            if len(self._connections) >= self.MAX_CONNECTIONS:
                print(f"[TCP] Server at capacity, rejecting {addr}")
                writer.write(b"Server at capacity.\n")
                await writer.drain()
                writer.close()
                return
            self._connections.add(writer)
        
        print(f"[TCP] Connection from {addr}")
        
        try:
            while True:
                # Use wait_for for timeout protection
                data = await asyncio.wait_for(
                    reader.read(4096), 
                    timeout=self.READ_TIMEOUT
                )
                
                if not data:
                    break
                
                # Check message size
                if len(data) > self.MAX_MESSAGE_SIZE:
                    print(f"[TCP] Message too large from {addr}")
                    writer.write(b"Message too large.\n")
                    await writer.drain()
                    break
                
                message = data.decode(errors='replace')
                print(f"[TCP] Received from {addr}: {message[:80]}")
                writer.write(b"ACK:" + data)
                await writer.drain()
                
        except asyncio.TimeoutError:
            print(f"[TCP] Connection timeout: {addr}")
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            writer.close()
            async with self._lock:
                self._connections.discard(writer)
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
