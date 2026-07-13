"""
Umer OS IPC Bus  [TODAY - HMAC-signed async message passing]
============================================================
Provides secure, signed inter-process communication for the Umer OS
microkernel.

Design:
  - Every message is HMAC-SHA256 signed with a per-bus secret key.
  - Messages are delivered to per-PID asyncio queues.
  - Named channels support pub/sub broadcast (subscribe / broadcast).
  - ``start()``       — activate the bus (no-op, lifecycle hook).
  - ``register(pid)`` — create a queue for a PID.
  - ``subscribe(pid, channel)`` — synchronous pub/sub registration.
  - ``send(src, dst, payload)`` — directed async send.
  - ``broadcast(src, channel, payload)`` — async fan-out to all channel subscribers.
  - ``receive(pid)``  — async blocking receive with HMAC verification.
  - ``try_receive(pid)`` — non-blocking receive (returns None if empty).
  - ``sign(payload)`` — compute HMAC-SHA256 hex for an arbitrary dict.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac as _hmac
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.IPCBus")


# ---------------------------------------------------------------------------
# IPCMessage
# ---------------------------------------------------------------------------

@dataclass
class IPCMessage:
    """A single IPC message.

    Attributes:
        src:     Sender PID.
        dst:     Recipient PID (0 = broadcast / kernel).
        channel: Named pub/sub channel (default = "default").
        payload: Arbitrary JSON-serialisable dict.
        ts:      Unix timestamp of creation.
        sig:     HMAC-SHA256 hex digest (set by IPCBus.send / broadcast).
    """

    src:     int
    dst:     int
    channel: str  = "default"
    payload: Any  = field(default_factory=dict)
    ts:      float = field(default_factory=time.time)
    sig:     str  = ""

    def _signable_bytes(self) -> bytes:
        """Return a canonical byte representation for signing.

        Returns:
            UTF-8-encoded JSON of (src, dst, channel, payload, ts).
        """
        obj = {
            "src":     self.src,
            "dst":     self.dst,
            "channel": self.channel,
            "payload": self.payload,
            "ts":      self.ts,
        }
        return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

    def sign(self, key: bytes) -> None:
        """Compute and store HMAC-SHA256 over this message.

        Args:
            key: Secret key bytes used for signing.
        """
        self.sig = _hmac.new(key, self._signable_bytes(), hashlib.sha256).hexdigest()

    def verify(self, key: bytes) -> bool:
        """Verify the stored HMAC-SHA256 signature.

        Args:
            key: Secret key bytes.

        Returns:
            True if the signature is valid, False otherwise.
        """
        expected = _hmac.new(key, self._signable_bytes(), hashlib.sha256).hexdigest()
        return _hmac.compare_digest(expected, self.sig)


# ---------------------------------------------------------------------------
# IPCBus
# ---------------------------------------------------------------------------

class IPCBus:
    """Secure message-passing bus for the Umer OS microkernel.

    Each IPCBus instance generates a random per-bus HMAC key at construction.
    All messages are signed before queuing and verified before delivery.
    """

    def __init__(self) -> None:
        self._key:         bytes                    = os.urandom(32)
        self._queues:      Dict[int, asyncio.Queue] = {}
        self._subscribers: Dict[str, List[int]]     = defaultdict(list)
        self._lock:        asyncio.Lock             = asyncio.Lock()
        log.info("IPCBus initialised with fresh HMAC key.")

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Activate the bus.

        No-op today — the bus is usable immediately after construction.
        Exists as a clear lifecycle hook for the kernel's start-up sequence.
        """
        log.info("IPCBus started.")

    # ── Registration ─────────────────────────────────────────────────────────

    def register(self, pid: int) -> None:
        """Create a message queue for a process.

        Idempotent — re-registering an existing PID is a no-op.

        Args:
            pid: Process ID.
        """
        if pid not in self._queues:
            self._queues[pid] = asyncio.Queue()
            log.debug("IPCBus: PID %d registered.", pid)

    def unregister(self, pid: int) -> None:
        """Remove a process's queue and all pub/sub subscriptions.

        Args:
            pid: Process ID.
        """
        self._queues.pop(pid, None)
        for subs in self._subscribers.values():
            try:
                subs.remove(pid)
            except ValueError:
                pass
        log.debug("IPCBus: PID %d unregistered.", pid)

    # ── Pub/Sub ───────────────────────────────────────────────────────────────

    def subscribe(self, pid: int, channel: str) -> None:  # synchronous on purpose
        """Subscribe a PID to a named broadcast channel.

        Synchronous so it can be called from both sync and async contexts.
        Idempotent — subscribing twice has no extra effect.

        Args:
            pid:     Subscribing process ID.
            channel: Named channel.
        """
        if pid not in self._subscribers[channel]:
            self._subscribers[channel].append(pid)
        log.debug("PID %d subscribed to channel '%s'.", pid, channel)

    def unsubscribe(self, pid: int, channel: str) -> None:
        """Remove a PID from a channel.

        Args:
            pid:     Process ID.
            channel: Channel to leave.
        """
        subs = self._subscribers.get(channel, [])
        try:
            subs.remove(pid)
        except ValueError:
            pass

    # ── Sending ───────────────────────────────────────────────────────────────

    def _build_message(
        self,
        src: int,
        dst: int,
        payload: Any,
        channel: str = "default",
    ) -> IPCMessage:
        """Construct and sign an IPCMessage.

        Args:
            src:     Sender PID.
            dst:     Recipient PID.
            payload: JSON-serialisable payload.
            channel: Pub/sub channel name.

        Returns:
            Signed IPCMessage ready for queuing.
        """
        msg = IPCMessage(src=src, dst=dst, channel=channel, payload=payload)
        msg.sign(self._key)
        return msg

    async def send(
        self,
        src: int,
        dst: int,
        payload: Any,
        channel: str = "default",
    ) -> bool:
        """Send a directed message to a specific PID.

        Args:
            src:     Sender PID.
            dst:     Recipient PID.
            payload: JSON-serialisable message body.
            channel: Channel label (informational).

        Returns:
            True if the message was queued, False if dst is not registered.
        """
        if dst not in self._queues:
            log.warning("send: PID %d not registered; message dropped.", dst)
            return False
        msg = self._build_message(src, dst, payload, channel)
        await self._queues[dst].put(msg)
        log.debug("Message src=%d → dst=%d queued.", src, dst)
        return True

    async def broadcast(
        self,
        src: int,
        channel: str,
        payload: Any,
    ) -> int:
        """Fan a message out to all subscribers of a named channel.

        Args:
            src:     Sender PID.
            channel: Pub/sub channel name.
            payload: JSON-serialisable message body.

        Returns:
            Number of subscribers that received the message.
        """
        async with self._lock:
            subscribers = list(self._subscribers.get(channel, []))

        delivered = 0
        for pid in subscribers:
            if pid in self._queues:
                msg = self._build_message(src, pid, payload, channel)
                await self._queues[pid].put(msg)
                delivered += 1
        log.debug("Broadcast on '%s': delivered to %d subscriber(s).", channel, delivered)
        return delivered

    # ── Receiving ─────────────────────────────────────────────────────────────

    async def receive(
        self,
        pid: int,
        timeout: Optional[float] = None,
    ) -> Optional[IPCMessage]:
        """Async blocking receive with HMAC verification.

        Args:
            pid:     Recipient PID.
            timeout: Optional seconds to wait; None = wait forever.

        Returns:
            Verified IPCMessage, or None on timeout / unknown PID.
        """
        queue = self._queues.get(pid)
        if queue is None:
            log.warning("receive: PID %d not registered.", pid)
            return None
        try:
            if timeout is not None:
                msg = await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                msg = await queue.get()
        except (asyncio.TimeoutError, asyncio.CancelledError):
            return None

        if not msg.verify(self._key):
            log.error("SECURITY: Dropped message with invalid HMAC (channel '%s').",
                      msg.channel)
            return None
        return msg

    def try_receive(self, pid: int) -> Optional[IPCMessage]:
        """Non-blocking receive — returns next message or None.

        Does *not* verify HMAC so it can be called without an event loop.
        For production, prefer ``receive()`` which awaits and verifies.

        Args:
            pid: Recipient PID.

        Returns:
            Next IPCMessage, or None if queue is empty or PID is unknown.
        """
        queue = self._queues.get(pid)
        if queue is None:
            return None
        try:
            return queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def pending(self, pid: int) -> int:
        """Return the number of messages queued for a PID.

        Args:
            pid: Process ID.

        Returns:
            Queue depth, or 0 if PID is unknown.
        """
        q = self._queues.get(pid)
        return q.qsize() if q else 0

    # ── Signing utility ───────────────────────────────────────────────────────

    def sign(self, payload: dict) -> str:
        """Return HMAC-SHA256 hex digest for an arbitrary payload dict.

        Useful for callers that want to sign dicts without building IPCMessage.

        Args:
            payload: Dictionary to sign.

        Returns:
            Hex HMAC-SHA256 string.
        """
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return _hmac.new(self._key, raw, hashlib.sha256).hexdigest()
