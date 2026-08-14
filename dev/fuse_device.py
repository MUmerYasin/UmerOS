"""
UmerOS /dev/fuse — Filesystem in Userspace.

/dev/fuse (major 10, minor 229):
  FUSE allows implementing filesystems in userspace. The kernel
  communicates with the FUSE daemon via /dev/fuse using a
  request/response protocol. Each mount creates a new FUSE
  connection with its own /dev/fuse file descriptor.

  Used by: sshfs, NTFS-3G, Flatpak, Snap, Android storage,
  vmhgfs-fuse (VMware), vboxsf (VirtualBox).

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import struct
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.FuseDevice")


FUSE_LOOKUP = 1
FUSE_GETATTR = 3
FUSE_OPEN = 14
FUSE_READ = 15
FUSE_WRITE = 16
FUSE_STATFS = 17
FUSE_RELEASE = 18
FUSE_INIT = 26
FUSE_OPENDIR = 27
FUSE_READDIR = 28
FUSE_DESTROY = 38


class FuseRequest:
    def __init__(self, opcode: int, node_id: int, unique: int,
                 arg: bytes = b""):
        self.opcode = opcode
        self.node_id = node_id
        self.unique = unique
        self.arg = arg

    def encode_header(self) -> bytes:
        return struct.pack(
            "=IIQQQQII",
            40 + len(self.arg),
            self.opcode,
            self.unique,
            self.node_id,
            0, 0, 0, 0,
        ) + self.arg


class FuseResponse:
    def __init__(self, unique: int, error: int = 0, data: bytes = b""):
        self.unique = unique
        self.error = error
        self.data = data

    def encode(self) -> bytes:
        return struct.pack(
            "=IIiI",
            16 + len(self.data),
            self.error,
            0,
            len(self.data),
        ) + self.data


class FuseConnection:
    def __init__(self, conn_id: int, mountpoint: str):
        self.conn_id = conn_id
        self.mountpoint = mountpoint
        self.request_queue: List[FuseRequest] = []
        self.response_queue: List[FuseResponse] = []
        self.unique_counter = 0
        self.initialized = False
        self.proto_major = 7
        self.proto_minor = 8
        self.max_read = 128 * 1024
        self.max_write = 128 * 1024
        self.max_background = 32
        self.congestion_threshold = 24
        self.mounted = True

    def next_unique(self) -> int:
        self.unique_counter += 1
        return self.unique_counter

    def queue_request(self, opcode: int, node_id: int,
                      arg: bytes = b"") -> FuseRequest:
        req = FuseRequest(opcode, node_id, self.next_unique(), arg)
        self.request_queue.append(req)
        return req

    def queue_response(self, unique: int, error: int = 0,
                       data: bytes = b"") -> FuseResponse:
        resp = FuseResponse(unique, error, data)
        self.response_queue.append(resp)
        return resp

    def process_init(self, max_read: int = 0, max_write: int = 0) -> None:
        self.initialized = True
        if max_read:
            self.max_read = min(max_read, 128 * 1024)
        if max_write:
            self.max_write = min(max_write, 128 * 1024)
        log.info("FUSE conn %d: initialized (proto=%d.%d)", self.conn_id,
                 self.proto_major, self.proto_minor)

    def unmount(self) -> None:
        self.mounted = False
        self.queue_request(FUSE_DESTROY, 1)
        log.info("FUSE conn %d: unmounted from %s", self.conn_id, self.mountpoint)


class FuseDevice:
    MAJOR = 10
    MINOR = 229
    MAX_CONNECTIONS = 64

    def __init__(self):
        self._connections: Dict[int, FuseConnection] = {}
        self._next_conn_id = 0
        self._register()
        log.info("FuseDevice /dev/fuse created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="fuse", path="/dev/fuse",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o666,
            description="Filesystem in Userspace",
            read_callback=self._read,
            write_callback=self._write,
            ioctl_callback=self._ioctl,
        ))

    def _open(self, flags: int) -> int:
        if len(self._connections) >= self.MAX_CONNECTIONS:
            log.warning("FUSE: max connections reached")
            return -1
        conn_id = self._next_conn_id
        self._next_conn_id += 1
        self._connections[conn_id] = FuseConnection(conn_id, "")
        log.info("FUSE: opened connection %d", conn_id)
        return conn_id

    def _release(self) -> int:
        for conn_id, conn in list(self._connections.items()):
            if not conn.mounted:
                del self._connections[conn_id]
        return 0

    def _read(self, size: int, offset: int = 0) -> bytes:
        for conn in self._connections.values():
            if conn.mounted and conn.request_queue:
                req = conn.request_queue.pop(0)
                data = req.encode_header()
                return data[:size]
        return b"\x00" * size

    def _write(self, data: bytes, offset: int = 0) -> int:
        if len(data) < 16:
            return -1
        _total, _error, _pad, datalen = struct.unpack("=IIiI", data[:16])
        _ = datalen
        return len(data)

    def _ioctl(self, request: int, arg: Any) -> int:
        return 0

    def mount(self, mountpoint: str) -> int:
        conn_id = self._next_conn_id
        self._next_conn_id += 1
        conn = FuseConnection(conn_id, mountpoint)
        conn.process_init()
        self._connections[conn_id] = conn
        log.info("FUSE: mounted on %s (conn=%d)", mountpoint, conn_id)
        return conn_id

    def unmount(self, conn_id: int) -> bool:
        if conn_id not in self._connections:
            return False
        self._connections[conn_id].unmount()
        return True

    def get_connection(self, conn_id: int) -> Optional[FuseConnection]:
        return self._connections.get(conn_id)

    def get_info(self) -> Dict[str, Any]:
        active = [c for c in self._connections.values() if c.mounted]
        return {
            "path": "/dev/fuse",
            "max_connections": self.MAX_CONNECTIONS,
            "active_connections": len(active),
            "connection_ids": [c.conn_id for c in active],
            "mountpoints": [c.mountpoint for c in active if c.mountpoint],
        }
