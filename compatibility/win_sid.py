"""
Umer OS /compatibility/win_sid — Windows Security Identifiers
============================================================

A Windows Security Identifier (SID) is a variable-length binary
structure used by the NT security subsystem.  The textual form is::

    S-<revision>-<authority>-<subauth1>-<subauth2>-...-<subauthN>

where the authority is encoded as a 48-bit integer (commonly
``5`` for "NT Authority").  The subauthorities are 32-bit little-endian
integers; there must be at least one.

This module:

* decodes and encodes SIDs in both their binary and textual forms,
* exposes the most commonly-used well-known SIDs (``LocalSystem``,
  ``LocalService``, ``NetworkService``, ``Admins``, ``Users``,
  ``Everyone``, ``Authenticated User``, ...),
* maps the textual SID to a friendly name (and back) via the small
  :class:`SidDatabase` helper.

References
----------

* https://learn.microsoft.com/en-us/windows/security/identity-protection/access-control/security-identifiers
* https://www.microsoft.com/en-us/download/details.aspx?id=9803

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


_SID_RE = re.compile(
    r"^S-(\d+)-(\d+)(?:-(\d+))+$"
)

#: S-1-5-18 = NT AUTHORITY\SYSTEM
SECURITY_LOCAL_SYSTEM_RID = (18,)
#: S-1-5-19 = NT AUTHORITY\LocalService
SECURITY_LOCAL_SERVICE_RID = (19,)
#: S-1-5-20 = NT AUTHORITY\NetworkService
SECURITY_NETWORK_SERVICE_RID = (20,)
#: S-1-5-32-544 = BUILTIN\Administrators
SECURITY_BUILTIN_DOMAIN_RID = 32
SECURITY_ADMINISTRATORS_RID = 544
SECURITY_USERS_RID = 545
SECURITY_GUESTS_RID = 546
SECURITY_POWER_USERS_RID = 547
SECURITY_AUTHENTICATED_USER_RID = 11
SECURITY_LOCAL_RID = 0
SECURITY_CREATOR_OWNER_RID = 4
SECURITY_WORLD_RID = 0  # the 0th subauthority in S-1-1-0 (Everyone)

#: S-1-1-0: Everyone
SECURITY_EVERYONE_SUBAUTH = (1, 0)


@dataclass(frozen=True, order=True)
class Sid:
    """A Windows Security Identifier.

    Attributes:
        revision: SID revision (always 1 in current Windows).
        authority: 48-bit identifier authority.
        subauthorities: tuple of 32-bit sub-authority values, at least one.
    """

    revision: int = 1
    authority: int = 5
    subauthorities: Tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.revision != 1:
            raise ValueError(f"SID revision must be 1 (got {self.revision!r})")
        if not (0 <= self.authority <= 0xFFFFFFFFFFFF):
            raise ValueError("SID authority must fit in 48 bits")
        if not self.subauthorities:
            raise ValueError("SID must have at least one sub-authority")
        for sa in self.subauthorities:
            if not (0 <= sa <= 0xFFFFFFFF):
                raise ValueError("sub-authority must fit in 32 bits")

    # ------------------------------------------------------------------
    # Binary (Win32 PSID) form
    # ------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, blob: bytes) -> "Sid":
        """Parse a Windows binary SID (the ``PSID`` layout).

        Layout (Microsoft order, little-endian)::

            UCHAR Revision;          // 1 byte
            UCHAR SubAuthorityCount;  // 1 byte
            USHORT IdentifierAuthority;  // 6 bytes, big-endian
            ULONG SubAuthority[];     // 4 * count bytes
        """
        if len(blob) < 8:
            raise ValueError(f"SID too short ({len(blob)} bytes)")
        revision = blob[0]
        if revision != 1:
            raise ValueError(f"unsupported SID revision {revision}")
        nsub = blob[1]
        # Authority is a 6-byte big-endian value.
        if nsub < 1 or nsub > 15:
            raise ValueError(f"implausible sub-authority count {nsub}")
        expected = 8 + 4 * nsub
        if len(blob) < expected:
            raise ValueError(
                f"SID truncated: header says {nsub} subauthorities, "
                f"have {len(blob) - 8} bytes"
            )
        # Authority: bytes 2..8, big-endian.
        authority = int.from_bytes(blob[2:8], "big")
        subs = []
        for i in range(nsub):
            sa = int.from_bytes(blob[8 + 4 * i:12 + 4 * i], "little")
            subs.append(sa)
        return cls(revision=revision, authority=authority,
                   subauthorities=tuple(subs))

    def to_bytes(self) -> bytes:
        """Encode this SID to the Windows binary layout (PSID)."""
        if not 1 <= len(self.subauthorities) <= 15:
            raise ValueError("sub-authority count out of range")
        header = bytes([self.revision, len(self.subauthorities)]) + \
            self.authority.to_bytes(6, "big")
        return header + b"".join(
            sa.to_bytes(4, "little") for sa in self.subauthorities
        )

    # ------------------------------------------------------------------
    # Textual form
    # ------------------------------------------------------------------

    @classmethod
    def from_string(cls, s: str) -> "Sid":
        """Parse a textual SID (e.g. ``"S-1-5-18"``)."""
        if not isinstance(s, str):
            raise TypeError("Sid.from_string expects str")
        s = s.strip()
        m = _SID_RE.match(s)
        if not m:
            raise ValueError(f"not a textual SID: {s!r}")
        rev = int(m.group(1))
        auth = int(m.group(2))
        subs = tuple(int(x) for x in m.group(3).split("-"))
        return cls(revision=rev, authority=auth, subauthorities=subs)

    def __str__(self) -> str:
        body = "-".join(str(s) for s in (self.revision,
                                          self.authority,
                                          *self.subauthorities))
        return f"S-{body}"


# ---------------------------------------------------------------------------
# Well-known SIDs
# ---------------------------------------------------------------------------

#: S-1-1-0 Everyone.
SID_EVERYONE = Sid(authority=1, subauthorities=SECURITY_EVERYONE_SUBAUTH)
#: S-1-5-11 Authenticated User.
SID_AUTHENTICATED_USER = Sid(authority=5, subauthorities=(11,))
#: S-1-5-18 LocalSystem.
SID_LOCAL_SYSTEM = Sid(authority=5, subauthorities=SECURITY_LOCAL_SYSTEM_RID)
#: S-1-5-19 LocalService.
SID_LOCAL_SERVICE = Sid(authority=5, subauthorities=SECURITY_LOCAL_SERVICE_RID)
#: S-1-5-20 NetworkService.
SID_NETWORK_SERVICE = Sid(authority=5, subauthorities=SECURITY_NETWORK_SERVICE_RID)
#: S-1-5-32-544 BUILTIN\Administrators.
SID_ADMINISTRATORS = Sid(
    authority=5, subauthorities=(SECURITY_BUILTIN_DOMAIN_RID, SECURITY_ADMINISTRATORS_RID),
)
#: S-1-5-32-545 BUILTIN\Users.
SID_USERS = Sid(
    authority=5, subauthorities=(SECURITY_BUILTIN_DOMAIN_RID, SECURITY_USERS_RID),
)
#: S-1-5-32-546 BUILTIN\Guests.
SID_GUESTS = Sid(
    authority=5, subauthorities=(SECURITY_BUILTIN_DOMAIN_RID, SECURITY_GUESTS_RID),
)
#: S-1-5-32-547 BUILTIN\Power Users.
SID_POWER_USERS = Sid(
    authority=5, subauthorities=(SECURITY_BUILTIN_DOMAIN_RID, SECURITY_POWER_USERS_RID),
)
#: S-1-3-0 Creator Owner.
SID_CREATOR_OWNER = Sid(authority=3, subauthorities=(0,))
#: S-1-3-1 Creator Group.
SID_CREATOR_GROUP = Sid(authority=3, subauthorities=(1,))
#: S-1-5-4 Interactive.
SID_INTERACTIVE = Sid(authority=5, subauthorities=(4,))
#: S-1-5-2 Network.
SID_NETWORK = Sid(authority=5, subauthorities=(2,))
#: S-1-5-7 Anonymous.
SID_ANONYMOUS = Sid(authority=5, subauthorities=(7,))
#: S-1-5-1 Dialup.
SID_DIALUP = Sid(authority=5, subauthorities=(1,))


# ---------------------------------------------------------------------------
# Database of well-known SIDs (name -> SID, SID -> name)
# ---------------------------------------------------------------------------

_DEFAULT_DB: Dict[str, Sid] = {
    "Everyone": SID_EVERYONE,
    "AuthenticatedUser": SID_AUTHENTICATED_USER,
    "LocalSystem": SID_LOCAL_SYSTEM,
    "NT AUTHORITY\\SYSTEM": SID_LOCAL_SYSTEM,
    "LocalService": SID_LOCAL_SERVICE,
    "NT AUTHORITY\\LocalService": SID_LOCAL_SERVICE,
    "NetworkService": SID_NETWORK_SERVICE,
    "NT AUTHORITY\\NetworkService": SID_NETWORK_SERVICE,
    "BUILTIN\\Administrators": SID_ADMINISTRATORS,
    "Administrators": SID_ADMINISTRATORS,
    "BUILTIN\\Users": SID_USERS,
    "Users": SID_USERS,
    "BUILTIN\\Guests": SID_GUESTS,
    "Guests": SID_GUESTS,
    "BUILTIN\\Power Users": SID_POWER_USERS,
    "PowerUsers": SID_POWER_USERS,
    "CreatorOwner": SID_CREATOR_OWNER,
    "CreatorGroup": SID_CREATOR_GROUP,
    "Interactive": SID_INTERACTIVE,
    "Network": SID_NETWORK,
    "Anonymous": SID_ANONYMOUS,
    "Dialup": SID_DIALUP,
}


@dataclass
class SidDatabase:
    """Bidirectional map of well-known SIDs to friendly names.

    The Windows API has a small built-in set of well-known SIDs
    (returned by ``LookupAccountSid``); this dataclass is the
    pure-Python equivalent.  Tests can register additional entries
    with :meth:`register`.
    """

    _to_name: Dict[Sid, str] = field(default_factory=dict)
    _to_sid: Dict[str, Sid] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, sid in _DEFAULT_DB.items():
            self.register(name, sid, overwrite=False)

    def register(self, name: str, sid: Sid, *, overwrite: bool = True) -> None:
        """Add or replace a (name, SID) entry."""
        if not overwrite and name in self._to_sid:
            return
        self._to_sid[name] = sid
        self._to_name[sid] = name

    def lookup_name(self, sid: Sid) -> Optional[str]:
        """Return the friendly name for ``sid``, or ``None``."""
        return self._to_name.get(sid)

    def lookup_sid(self, name: str) -> Optional[Sid]:
        """Return the SID for a friendly ``name``, or ``None``."""
        return self._to_sid.get(name)

    def all_names(self) -> List[str]:
        return sorted(self._to_sid.keys())


# A process-wide default database.
DEFAULT_DB = SidDatabase()


__all__ = [
    "Sid",
    "SidDatabase",
    "DEFAULT_DB",
    "SID_EVERYONE", "SID_AUTHENTICATED_USER", "SID_LOCAL_SYSTEM",
    "SID_LOCAL_SERVICE", "SID_NETWORK_SERVICE",
    "SID_ADMINISTRATORS", "SID_USERS", "SID_GUESTS", "SID_POWER_USERS",
    "SID_CREATOR_OWNER", "SID_CREATOR_GROUP", "SID_INTERACTIVE",
    "SID_NETWORK", "SID_ANONYMOUS", "SID_DIALUP",
]
