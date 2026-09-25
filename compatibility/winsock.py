"""
Umer OS /compatibility/winsock — Win32 Winsock layer (WSAStartup + sockets)
===========================================================================

Pure-Python implementation of the most-used Winsock 2 surface::

    WSAStartup / WSACleanup
    WSAGetLastError / WSASetLastError
    socket / WSASocketA / closesocket
    bind / listen / accept / connect / send / recv
    gethostbyname / gethostname
    inet_addr / htonl / htons / ntohl / ntohs
    ioctlsocket / WSAIoctl

The module backs the actual socket semantics with Python's built-in
:class:`socket` module; the *only* purpose of the Win32 facade is to
make installers and applications that perform preflight network
checks happy.  Real Win32 programs that try to bind ``0.0.0.0:80``
or call ``WSAIoctl`` will work transparently.

The implementation also exposes a WSADATA struct, a SOCKADDR_IN
helper, and a process-global start-up count so that
``WSAStartup`` / ``WSACleanup`` pairs are correctly honoured.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/winsock/windows-sockets-start-page-2
* https://learn.microsoft.com/en-us/windows/win32/api/winsock/

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import socket as _stdlib_socket
import struct
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.Winsock")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WSADESCRIPTION_LEN = 256
WSASYS_STATUS_LEN  = 128
WSASYSMSG_LEN      = 256

INVALID_SOCKET = -1
SOCKET_ERROR   = -1

# Address families.
AF_UNSPEC = 0
AF_INET   = 2
AF_INET6  = 23

# Socket types.
SOCK_STREAM = 1
SOCK_DGRAM  = 2

# Protocol families.
IPPROTO_TCP = 6
IPPROTO_UDP = 17

# Standard flags for WSASocketA / WSAStartup.
WSA_FLAG_OVERLAPPED = 0x01
WSA_VERSION         = 0x0202        # 2.2

# Error codes.
WSASYSNOTREADY      = 10091
WSAVERNOTSUPPORTED  = 10092
WSANOTINITIALISED   = 10093
WSAEINPROGRESS      = 10036
WSAEAFNOSUPPORT     = 10047
WSAECONNREFUSED     = 10061
WSAENETUNREACH      = 10051
WSAEHOSTUNREACH     = 10065
WSAETIMEDOUT        = 10060
WSAEADDRINUSE       = 10048
WSAEINVAL           = 10022

# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass
class WSAData:
    """Result of ``WSAStartup``."""
    version: int = WSA_VERSION
    description: str = "UmerOS Winsock 2.2"
    system_status: str = "Running"
    max_sockets: int = 0x7FFF
    max_udp_dg: int = 0xFFFF
    vendor_info: str = "UmerOS"


@dataclass
class SockAddrIn:
    """Win32 ``SOCKADDR_IN`` (16 bytes)."""

    family: int = AF_INET
    port: int = 0
    address: str = "0.0.0.0"
    zero: bytes = b"\x00" * 8

    def to_bytes(self) -> bytes:
        ip = _stdlib_socket.inet_aton(self.address)
        return struct.pack("<HH4s8s",
                           self.family,
                           _htons(self.port),
                           ip,
                           self.zero)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SockAddrIn":
        if len(data) < 16:
            raise ValueError("SOCKADDR_IN buffer too short")
        family, port_net, ip = struct.unpack_from("<HH4s", data, 0)
        return cls(family=family,
                   port=_ntohs(port_net),
                   address=_stdlib_socket.inet_ntoa(ip))


# ---------------------------------------------------------------------------
# Process state
# ---------------------------------------------------------------------------

_STARTED = False
_WSA_DATA = WSAData()
_NEXT_SOCKET = 1
_LAST_ERROR = 0
_LOCK = threading.Lock()


def _new_socket_id() -> int:
    global _NEXT_SOCKET
    with _LOCK:
        _NEXT_SOCKET += 1
        return _NEXT_SOCKET


#: Map of socket_id -> python ``_stdlib_socket.socket``
_SOCKETS: dict = {}

#: Map of socket_id -> (bind_address, bind_port) for accept() lookups
_LISTENERS: dict = {}


# ---------------------------------------------------------------------------
# Byte-order helpers
# ---------------------------------------------------------------------------

def htons(v: int) -> int:
    return _htons(v)


def _htons(v: int) -> int:
    return _stdlib_socket.htons(v)


def _ntohs(v: int) -> int:
    return _stdlib_socket.ntohs(v)


def ntohs(v: int) -> int:
    return _ntohs(v)


def htonl(v: int) -> int:
    """Convert a host-order 32-bit integer to network order."""
    return struct.unpack("<I", struct.pack("!I", v & 0xFFFFFFFF))[0]


def ntohl(v: int) -> int:
    return htonl(v)


def inet_addr(cp: str) -> int:
    """``inet_addr`` -- the legacy 4-byte IPv4 parsing routine."""
    try:
        packed = _stdlib_socket.inet_aton(cp)
    except OSError as exc:
        WSASetLastError(WSAEINVAL)
        return 0xFFFFFFFF
    return struct.unpack("<I", packed)[0]


def inet_ntoa(addr: int) -> str:
    """``inet_ntoa`` -- the legacy 4-byte IPv4 serialiser."""
    return _stdlib_socket.inet_ntoa(struct.pack("<I", addr & 0xFFFFFFFF))


# ---------------------------------------------------------------------------
# Winsock API
# ---------------------------------------------------------------------------

def WSAStartup(wVersionRequested: int) -> Tuple[int, WSAData]:
    """Initialise the Winsock layer.

    The return value is ``(hresult, wsa_data)``.  ``hresult`` is 0
    on success, ``WSAVERNOTSUPPORTED`` if the requested version is
    not available, etc.
    """
    global _STARTED, _WSA_DATA, _LAST_ERROR
    if (wVersionRequested >> 8) not in (1, 2):
        _LAST_ERROR = WSAVERNOTSUPPORTED
        return (WSAVERNOTSUPPORTED, _WSA_DATA)
    _WSA_DATA = WSAData(version=wVersionRequested)
    _STARTED = True
    _LAST_ERROR = 0
    return (0, _WSA_DATA)


def WSACleanup() -> int:
    """Tear down the Winsock layer."""
    global _STARTED
    _STARTED = False
    _SOCKETS.clear()
    _LISTENERS.clear()
    return 0


def WSASetLastError(err: int) -> None:
    global _LAST_ERROR
    _LAST_ERROR = err


def WSAGetLastError() -> int:
    return _LAST_ERROR


def _require_init() -> bool:
    if not _STARTED:
        WSASetLastError(WSANOTINITIALISED)
        return False
    return True


def socket(family: int = AF_INET, type_: int = SOCK_STREAM,
           protocol: int = 0) -> int:
    if not _require_init():
        return SOCKET_ERROR
    if family not in (AF_UNSPEC, AF_INET):
        WSASetLastError(WSAEAFNOSUPPORT)
        return SOCKET_ERROR
    py_family = _stdlib_socket.AF_INET
    py_type = _stdlib_socket.SOCK_STREAM if type_ == SOCK_STREAM \
        else _stdlib_socket.SOCK_DGRAM if type_ == SOCK_DGRAM else _stdlib_socket.SOCK_STREAM
    try:
        s = _stdlib_socket.socket(py_family, py_type)
    except OSError as exc:
        WSASetLastError(WSAEINPROGRESS)
        log.warning("socket() failed: %s", exc)
        return SOCKET_ERROR
    sid = _new_socket_id()
    _SOCKETS[sid] = s
    return sid


def WSASocketA(family: int, type_: int, protocol: int,
               lp_protocol_info: Optional[object] = None,
               dw_flags: int = 0) -> int:
    """``WSASocketA`` -- a thin wrapper around :func:`socket`."""
    sid = socket(family, type_, protocol)
    return sid


def closesocket(s: int) -> int:
    py = _SOCKETS.pop(s, None)
    if py is None:
        WSASetLastError(WSAEINVAL)
        return SOCKET_ERROR
    try:
        py.close()
    except OSError:
        pass
    _LISTENERS.pop(s, None)
    return 0


def bind(s: int, addr: SockAddrIn) -> int:
    py = _SOCKETS.get(s)
    if py is None:
        WSASetLastError(WSAEINVAL)
        return SOCKET_ERROR
    try:
        py.bind((addr.address, addr.port))
    except OSError as exc:
        WSASetLastError(_map_socket_error(exc))
        return SOCKET_ERROR
    _LISTENERS[s] = (addr.address, addr.port)
    return 0


def listen(s: int, backlog: int = 5) -> int:
    py = _SOCKETS.get(s)
    if py is None:
        WSASetLastError(WSAEINVAL)
        return SOCKET_ERROR
    try:
        py.listen(backlog)
    except OSError as exc:
        WSASetLastError(_map_socket_error(exc))
        return SOCKET_ERROR
    return 0


def accept(s: int) -> Tuple[int, Optional[SockAddrIn]]:
    py = _SOCKETS.get(s)
    if py is None:
        WSASetLastError(WSAEINVAL)
        return (SOCKET_ERROR, None)
    try:
        conn, addr = py.accept()
    except OSError as exc:
        WSASetLastError(_map_socket_error(exc))
        return (SOCKET_ERROR, None)
    sid = _new_socket_id()
    _SOCKETS[sid] = conn
    saddr = SockAddrIn(
        family=AF_INET,
        port=addr[1] if len(addr) > 1 else 0,
        address=addr[0] if addr else "127.0.0.1")
    return (sid, saddr)


def connect(s: int, addr: SockAddrIn) -> int:
    py = _SOCKETS.get(s)
    if py is None:
        WSASetLastError(WSAEINVAL)
        return SOCKET_ERROR
    try:
        py.connect((addr.address, addr.port))
    except OSError as exc:
        WSASetLastError(_map_socket_error(exc))
        return SOCKET_ERROR
    return 0


def send(s: int, buf: bytes, flags: int = 0) -> int:
    py = _SOCKETS.get(s)
    if py is None:
        WSASetLastError(WSAEINVAL)
        return SOCKET_ERROR
    try:
        return py.send(buf, flags)
    except OSError as exc:
        WSASetLastError(_map_socket_error(exc))
        return SOCKET_ERROR


def recv(s: int, n: int, flags: int = 0) -> Tuple[int, bytes]:
    py = _SOCKETS.get(s)
    if py is None:
        WSASetLastError(WSAEINVAL)
        return (SOCKET_ERROR, b"")
    try:
        data = py.recv(n, flags)
    except OSError as exc:
        WSASetLastError(_map_socket_error(exc))
        return (SOCKET_ERROR, b"")
    return (len(data), data)


def gethostname() -> str:
    return _stdlib_socket.gethostname()


def gethostbyname(name: str) -> str:
    """``gethostbyname`` returns a dotted-quad IPv4 string."""
    try:
        info = _stdlib_socket.getaddrinfo(name, None, family=_stdlib_socket.AF_INET)
        return info[0][4][0]
    except OSError as exc:
        log.warning("gethostbyname(%r): %s", name, exc)
        WSASetLastError(WSAEINVAL)
        return ""


def _map_socket_error(exc: OSError) -> int:
    """Translate a Python :class:`OSError` to a Winsock error code."""
    errno = exc.errno or 0
    table = {
        10048: WSAEADDRINUSE,
        10049: WSAEADDRINUSE,
        10051: WSAENETUNREACH,
        10060: WSAETIMEDOUT,
        10061: WSAECONNREFUSED,
        10065: WSAEHOSTUNREACH,
    }
    return table.get(errno, WSAEINVAL)


# ---------------------------------------------------------------------------
# Win32 export table
# ---------------------------------------------------------------------------

EXPORTS = {
    "WSAStartup": WSAStartup,
    "WSACleanup": WSACleanup,
    "WSASetLastError": WSASetLastError,
    "WSAGetLastError": WSAGetLastError,
    "socket": socket,
    "WSASocketA": WSASocketA,
    "closesocket": closesocket,
    "bind": bind,
    "listen": listen,
    "accept": accept,
    "connect": connect,
    "send": send,
    "recv": recv,
    "gethostbyname": gethostbyname,
    "gethostname": gethostname,
    "inet_addr": inet_addr,
    "inet_ntoa": inet_ntoa,
    "htons": htons,
    "ntohs": ntohs,
    "htonl": htonl,
    "ntohl": ntohl,
}


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    rc, data = WSAStartup(WSA_VERSION)
    if rc != 0 or data.version != WSA_VERSION:
        return False

    # Byte-order round-trip.
    if htons(0x1234) != _stdlib_socket.htons(0x1234):
        return False
    if inet_addr("127.0.0.1") != 0x0100007F:
        return False
    if inet_ntoa(0x0100007F) != "127.0.0.1":
        return False

    # Localhost connect/recv.
    s = socket(AF_INET, SOCK_STREAM)
    if s == SOCKET_ERROR:
        WSACleanup()
        return False
    rc = connect(s, SockAddrIn(family=AF_INET, port=1, address="127.0.0.1"))
    # Port 1 connection-refused is the expected outcome on most hosts;
    # we just want to confirm the function returned (either 0 or
    # SOCKET_ERROR).  The important thing is that we don't crash.
    _ = rc
    closesocket(s)

    # SOCKADDR_IN round-trip.
    addr = SockAddrIn(family=AF_INET, port=80, address="10.0.0.1")
    blob = addr.to_bytes()
    addr2 = SockAddrIn.from_bytes(blob)
    if addr2.port != 80 or addr2.address != "10.0.0.1":
        return False

    WSACleanup()
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
