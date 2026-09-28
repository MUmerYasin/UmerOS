"""
Umer OS /compatibility/tokens — Win32 token / privilege surface
===============================================================

Pure-Python implementation of the Win32 *token* and *privilege*
surface used by every Windows installer and application that asks
"am I admin?":

* :func:`OpenProcessToken` -- get a token handle for the current
  process (or any process we have access to).
* :func:`GetTokenInformation` -- query ``TokenElevationType``,
  ``TokenElevation``, ``TokenGroups``, ``TokenUser``,
  ``TokenIntegrityLevel``, ``TokenPrivileges`` etc.
* :func:`LookupPrivilegeValue` -- resolve a friendly privilege name
  like ``"SeShutdownPrivilege"`` to its 64-bit LUID.
* :func:`AdjustTokenPrivileges` -- no-op stub that returns success
  when the caller asks for a privilege the user already holds.
* :func:`CheckTokenMembership` -- check whether the SID of the
  requested group is enabled in the token.

The actual authentication boundary is the host OS; we model the
UmerOS process as if it were a Win32 user-mode process that
*started* with a token granted by ``UmerOS\Self``.  The single
hard-coded SID -- ``S-1-5-32-544`` (``BUILTIN\\Administrators``) --
is treated as both a member and a privilege carrier.  This is
exactly the level of fidelity that the average installer or
in-process application needs to perform preflight checks; full
elevation would require inter-process coordination that we do not
implement.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/
* https://learn.microsoft.com/en-us/windows/win32/secauthz/privilege-constants

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

from .win_sid import Sid, SID_ADMINISTRATORS, SID_USERS, SID_LOCAL_SYSTEM

log = logging.getLogger("UmerOS.Compat.Tokens")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ERROR_SUCCESS              = 0
ERROR_NOT_ENOUGH_MEMORY    = 8
ERROR_INVALID_PARAMETER    = 87
ERROR_ACCESS_DENIED        = 5
ERROR_NO_TOKEN             = 1008
ERROR_NOT_ALL_ASSIGNED     = 1300

# Token access rights.
TOKEN_ASSIGN_PRIMARY    = 0x0001
TOKEN_DUPLICATE        = 0x0002
TOKEN_IMPERSONATE      = 0x0004
TOKEN_QUERY            = 0x0008
TOKEN_QUERY_SOURCE     = 0x0010
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_ADJUST_GROUPS    = 0x0040
TOKEN_ADJUST_SESSIONID = 0x0100
TOKEN_ALL_ACCESS       = 0x000F01FF

# TokenInformationClass.
class TokenInformationClass(IntEnum):
    TokenUser                   = 1
    TokenGroups                 = 2
    TokenPrivileges             = 3
    TokenOwner                  = 4
    TokenPrimaryGroup           = 5
    TokenDefaultDacl            = 6
    TokenSource                 = 7
    TokenType                   = 8
    TokenImpersonationLevel     = 9
    TokenStatistics             = 10
    TokenRestrictedSids         = 11
    TokenSessionId              = 12
    TokenGroupsAndPrivileges    = 13
    TokenSessionReference       = 14
    TokenSandBoxInert           = 15
    TokenAuditPolicy            = 16
    TokenOrigin                 = 17
    TokenElevationType          = 18
    TokenLinkedToken            = 19
    TokenElevation              = 20
    TokenHasRestrictions        = 21
    TokenAccessInformation      = 22
    TokenVirtualizationAllowed  = 23
    TokenVirtualizationEnabled  = 24
    TokenIntegrityLevel         = 25
    TokenUIAccess               = 26
    TokenMandatoryPolicy        = 27
    TokenLogonSid               = 28
    MaxTokenInfoClass           = 29


class TokenElevationType(IntEnum):
    TokenElevationTypeDefault = 1
    TokenElevationTypeFull     = 2
    TokenElevationTypeLimited  = 3


# Pre-defined LUIDs (Windows documented values; we use the same).
LUID_SE_SHUTDOWN_PRIVILEGE = (12, 0x00000004)
LUID_SE_DEBUG_PRIVILEGE    = (20, 0x00000003)
LUID_SE_BACKUP_PRIVILEGE   = (17, 0x00000001)
LUID_SE_RESTORE_PRIVILEGE  = (18, 0x00000002)
LUID_SE_CHANGE_NOTIFY      = (23, 0x00000005)
LUID_SE_TCB_PRIVILEGE      = (7,  0x00000007)
LUID_SE_ASSIGNPRIMARYTOKEN = (3,  0x00000003)
LUID_SE_LOAD_DRIVER        = (10, 0x00000001)
LUID_SE_INCREASE_QUOTA     = (5,  0x00000005)
LUID_SE_SECURITY           = (8,  0x00000004)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Luid:
    """Win32 ``LUID`` (64-bit split as LowPart + HighPart)."""
    low: int
    high: int

    @classmethod
    def from_dwords(cls, low: int, high: int) -> "Luid":
        return cls(low=low, high=high)

    def as_packed(self) -> int:
        return (self.high << 32) | (self.low & 0xFFFFFFFF)


@dataclass(frozen=True)
class LuidAndAttributes:
    """``LUID_AND_ATTRIBUTES`` pair."""
    luid: Luid
    attributes: int = 0


@dataclass
class TokenPrivileges:
    """A simplified view of ``TOKEN_PRIVILEGES``."""
    privileges: List[LuidAndAttributes] = field(default_factory=list)

    def has(self, luid: Luid) -> bool:
        return any(p.luid.as_packed() == luid.as_packed() for p in
                   self.privileges)


@dataclass
class TokenGroups:
    groups: List[Tuple[Sid, int]] = field(default_factory=list)


@dataclass
class TokenUser:
    user: Sid
    attributes: int = 0


@dataclass
class TokenIntegrityLevel:
    rid: int
    """The integrity RID (e.g. 0x2000 for Medium, 0x3000 for High)."""


@dataclass
class TokenElevation:
    is_elevated: bool


@dataclass
class Token:
    """The in-memory representation of an opened token."""

    user: TokenUser = field(default_factory=lambda:
        TokenUser(user=SID_LOCAL_SYSTEM))
    groups: TokenGroups = field(default_factory=TokenGroups)
    privileges: TokenPrivileges = field(default_factory=TokenPrivileges)
    integrity_level: TokenIntegrityLevel = field(
        default_factory=lambda: TokenIntegrityLevel(rid=0x2000))
    elevation_type: TokenElevationType = \
        TokenElevationType.TokenElevationTypeDefault
    is_elevated: bool = False
    impersonation_level: int = 0
    is_primary: bool = True


# ---------------------------------------------------------------------------
# Process / token handle table
# ---------------------------------------------------------------------------

_TOKEN_HANDLES: Dict[int, Token] = {}
_TOKEN_COUNTER = 0xC0000000
_TOKEN_LOCK = threading.Lock()


def _new_handle(token: Token) -> int:
    global _TOKEN_COUNTER
    with _TOKEN_LOCK:
        _TOKEN_COUNTER += 1
        _TOKEN_HANDLES[_TOKEN_COUNTER] = token
        return _TOKEN_COUNTER


def _resolve_token(handle: int) -> Optional[Token]:
    return _TOKEN_HANDLES.get(handle)


def _close_token(handle: int) -> bool:
    with _TOKEN_LOCK:
        return _TOKEN_HANDLES.pop(handle, None) is not None


# ---------------------------------------------------------------------------
# Privileges table
# ---------------------------------------------------------------------------

PRIVILEGES: Dict[str, Luid] = {
    "SeShutdownPrivilege":       Luid(*LUID_SE_SHUTDOWN_PRIVILEGE),
    "SeDebugPrivilege":          Luid(*LUID_SE_DEBUG_PRIVILEGE),
    "SeBackupPrivilege":         Luid(*LUID_SE_BACKUP_PRIVILEGE),
    "SeRestorePrivilege":        Luid(*LUID_SE_RESTORE_PRIVILEGE),
    "SeChangeNotifyPrivilege":   Luid(*LUID_SE_CHANGE_NOTIFY),
    "SeTcbPrivilege":            Luid(*LUID_SE_TCB_PRIVILEGE),
    "SeAssignPrimaryTokenPrivilege": Luid(*LUID_SE_ASSIGNPRIMARYTOKEN),
    "SeLoadDriverPrivilege":     Luid(*LUID_SE_LOAD_DRIVER),
    "SeIncreaseQuotaPrivilege":  Luid(*LUID_SE_INCREASE_QUOTA),
    "SeSecurityPrivilege":       Luid(*LUID_SE_SECURITY),
}


def LookupPrivilegeValue(system_name: Optional[str], privilege_name: str
                          ) -> Tuple[int, int]:
    """Resolve a friendly privilege name to a (low, high) LUID pair.

    Returns ``(0, 0)`` if the privilege is unknown -- Win32
    semantics map that to ``ERROR_NO_SUCH_PRIVILEGE``.
    """
    luid = PRIVILEGES.get(privilege_name)
    if luid is None:
        return (0, 0)
    return (luid.low, luid.high)


# ---------------------------------------------------------------------------
# Process / token API
# ---------------------------------------------------------------------------

def OpenProcessToken(process_handle: int, desired_access: int) -> Tuple[int, int]:
    """``OpenProcessToken`` equivalent.

    ``process_handle`` is a fake handle; the only one we accept is
    ``0xFFFFFFFF`` ("self").  Returns ``(token_handle, error)``.
    """
    if process_handle != 0xFFFFFFFF:
        return (0, ERROR_ACCESS_DENIED)
    token = _build_self_token()
    h = _new_handle(token)
    return (h, ERROR_SUCCESS)


def _build_self_token() -> Token:
    """Construct the token we pretend the UmerOS process holds."""
    admin = SID_ADMINISTRATORS
    users = SID_USERS
    system = SID_LOCAL_SYSTEM
    t = Token(
        user=TokenUser(user=system, attributes=0),
        groups=TokenGroups(groups=[
            (admin, 0x00000007),    # SE_GROUP_ENABLED | LOGON | MANDATORY
            (users, 0x00000007),
        ]),
        privileges=TokenPrivileges(privileges=[
            LuidAndAttributes(luid=PRIVILEGES["SeShutdownPrivilege"],
                              attributes=0x00000002),
            LuidAndAttributes(luid=PRIVILEGES["SeDebugPrivilege"],
                              attributes=0x00000002),
            LuidAndAttributes(luid=PRIVILEGES["SeBackupPrivilege"],
                              attributes=0x00000002),
            LuidAndAttributes(luid=PRIVILEGES["SeRestorePrivilege"],
                              attributes=0x00000002),
            LuidAndAttributes(luid=PRIVILEGES["SeChangeNotifyPrivilege"],
                              attributes=0x00000003),
            LuidAndAttributes(luid=PRIVILEGES["SeTcbPrivilege"],
                              attributes=0x00000002),
        ]),
        integrity_level=TokenIntegrityLevel(rid=0x3000),    # High
        elevation_type=TokenElevationType.TokenElevationTypeFull,
        is_elevated=True,
    )
    return t


def GetTokenInformation(token_handle: int,
                        info_class: TokenInformationClass
                        ) -> Optional[object]:
    """Look up ``TokenXxx`` on a token opened via :func:`OpenProcessToken`."""
    token = _resolve_token(token_handle)
    if token is None:
        return None
    if info_class == TokenInformationClass.TokenUser:
        return token.user
    if info_class == TokenInformationClass.TokenGroups:
        return token.groups
    if info_class == TokenInformationClass.TokenPrivileges:
        return token.privileges
    if info_class == TokenInformationClass.TokenElevation:
        return TokenElevation(is_elevated=token.is_elevated)
    if info_class == TokenInformationClass.TokenElevationType:
        return token.elevation_type
    if info_class == TokenInformationClass.TokenIntegrityLevel:
        return token.integrity_level
    if info_class == TokenInformationClass.TokenGroupsAndPrivileges:
        return token.groups, token.privileges
    log.debug("GetTokenInformation: unsupported class %d", info_class)
    return None


def AdjustTokenPrivileges(token_handle: int, disable_all: bool,
                          privileges: List[LuidAndAttributes],
                          length: int) -> int:
    """``AdjustTokenPrivileges`` -- mutates the privilege attributes.

    Real Win32 returns ``ERROR_NOT_ALL_ASSIGNED`` when a privilege
    cannot be granted; we always succeed because our fake token
    already holds every entry of :data:`PRIVILEGES`.
    """
    token = _resolve_token(token_handle)
    if token is None:
        return ERROR_NO_TOKEN
    if disable_all:
        token.privileges = TokenPrivileges()
        return ERROR_SUCCESS
    if not privileges:
        return ERROR_INVALID_PARAMETER
    # Replace any privilege in the table; add unknown ones.
    for lp in privileges:
        for existing in token.privileges.privileges:
            if existing.luid.as_packed() == lp.luid.as_packed():
                existing.__dict__.update(attributes=lp.attributes)
                break
        else:
            token.privileges.privileges.append(lp)
    return ERROR_SUCCESS


def CheckTokenMembership(token_handle: int, sid_to_check: Sid) -> bool:
    """Return ``True`` if ``sid_to_check`` is enabled in the token."""
    token = _resolve_token(token_handle)
    if token is None:
        return False
    return any(s == sid_to_check for s, _ in token.groups.groups)


def IsUserAdmin(token_handle: int = 0) -> bool:
    """Convenience: ``True`` if the SID_BUILTIN\\Administrators group
    is enabled in the token (or any token the caller supplied)."""
    if token_handle == 0:
        token_handle = _new_handle(_build_self_token())
    info = GetTokenInformation(token_handle,
                                TokenInformationClass.TokenGroups)
    if info is None:
        return False
    if isinstance(info, TokenGroups):
        return any(s == SID_ADMINISTRATORS for s, _ in info.groups)
    return False


def CloseToken(handle: int) -> bool:
    return _close_token(handle)


# ---------------------------------------------------------------------------
# EXPORTS
# ---------------------------------------------------------------------------

EXPORTS = {
    "OpenProcessToken": OpenProcessToken,
    "GetTokenInformation": GetTokenInformation,
    "LookupPrivilegeValue": LookupPrivilegeValue,
    "AdjustTokenPrivileges": AdjustTokenPrivileges,
    "CheckTokenMembership": CheckTokenMembership,
    "CloseToken": CloseToken,
}


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    h, err = OpenProcessToken(0xFFFFFFFF, TOKEN_QUERY)
    if err != ERROR_SUCCESS or h == 0:
        return False
    user = GetTokenInformation(h, TokenInformationClass.TokenUser)
    if not isinstance(user, TokenUser):
        return False
    privs = GetTokenInformation(h, TokenInformationClass.TokenPrivileges)
    if not isinstance(privs, TokenPrivileges):
        return False
    if not privs.has(PRIVILEGES["SeShutdownPrivilege"]):
        return False
    elevation = GetTokenInformation(h, TokenInformationClass.TokenElevation)
    if not isinstance(elevation, TokenElevation) or not elevation.is_elevated:
        return False
    if not CheckTokenMembership(h, SID_ADMINISTRATORS):
        return False
    low, high = LookupPrivilegeValue(None, "SeShutdownPrivilege")
    if (low, high) != LUID_SE_SHUTDOWN_PRIVILEGE:
        return False
    # Unknown privilege returns (0, 0).
    if LookupPrivilegeValue(None, "SeDoesNotExist") != (0, 0):
        return False
    # AdjustTokenPrivileges works.
    if AdjustTokenPrivileges(h, False, [
        LuidAndAttributes(Luid(*LUID_SE_SHUTDOWN_PRIVILEGE),
                          attributes=0x80000000)        # SE_PRIVILEGE_REMOVED
    ], 0) != ERROR_SUCCESS:
        return False
    CloseToken(h)
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
