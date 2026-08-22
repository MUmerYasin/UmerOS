# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
UmerOS /lib/security — Pluggable Authentication Modules (PAM)
==============================================================
Implements the FHS subdirectory ``/lib/security`` which holds the PAM
shared library files loaded by ``libpam.so`` at runtime.

Real ``/lib/security`` typically contains:

  pam_unix.so       — classic /etc/passwd + /etc/shadow auth
  pam_nologin.so    — refuse non-root logins when /etc/nologin exists
  pam_env.so        — set/unset environment variables
  pam_limits.so     — process resource limits
  pam_deny.so       — always deny
  pam_permit.so     — always permit
  pam_warn.so       — log a warning, then defer to next module
  pam_cracklib.so   — password strength check (legacy)
  pam_pwquality.so  — password quality check (replacement)
  pam_tally2.so     — failed-login counter
  pam_faillock.so   — failed-login locking
  pam_ldap.so       — LDAP-based auth
  pam_krb5.so       — Kerberos auth
  pam_sss.so        — System Security Services daemon
  pam_gnome_keyring — GNOME keyring unlock
  pam_systemd.so    — register session with systemd-logind
  pam_loginuid.so   — set audit uid
  pam_umask.so      — set file-creation mask
  pam_userpass.so   — change expired passwords
  pam_access.so     — /etc/security/access.conf
  pam_time.so       — /etc/security/time.conf
  pam_sepermit.so   — SELinux-aware allow/deny
  pam_namespace.so  — polyinstantiated directories
  pam_motd.so       — show message of the day
  pam_mail.so       — check mailbox
  pam_exec.so       — run an external command
  pam_echo.so       — echo text to the user
  pam_keyinit.so    — revoke session keyring
  pam_selinux.so    — SELinux context management
  pam_apparmor.so   — AppArmor profile change
  pam_cap.so        — drop capabilities
  pam_pkcs11.so     — smart card / PKCS#11 auth
  pam_ssh.so        — ssh-agent pass-through
  pam_yubico.so     — YubiKey OTP
  pam_u2f.so        — FIDO2 / U2F
  pam_fprintd.so    — fingerprint
  pam_google_authenticator.so — TOTP

UmerOS ships the same set as stub metadata so the security subsystem
(``security/`` + ``kernel/cred.py``) can ask "is PAM module X available?"
without needing the C code.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

log = logging.getLogger("UmerOS.Lib.Security")


class PamModuleType(str, Enum):
    """PAM module interface type (one per row of pam.conf)."""
    AUTH       = "auth"        # authenticate the user
    ACCOUNT    = "account"     # check account validity (expiry, time, etc.)
    SESSION    = "session"     # setup/teardown for a session
    PASSWORD   = "password"    # change password


class PamControlFlag(str, Enum):
    REQUIRED  = "required"
    REQUISITE = "requisite"
    SUFFICIENT = "sufficient"
    OPTIONAL  = "optional"
    INCLUDE   = "include"
    SUBSTACK  = "substack"


@dataclass
class PamModule:
    """A single PAM shared library under /lib/security."""
    name: str
    path: str
    description: str
    version: str = "1.6.0"
    size: int = 16_384
    supports: Set[PamModuleType] = field(default_factory=set)
    provides: List[str] = field(default_factory=list)   # keywords this implements
    is_legacy: bool = False
    is_uncommon: bool = False                           # e.g. needs extra deps
    md5: str = ""


_STOCK_PAM_MODULES: List[PamModule] = [
    PamModule("pam_unix.so", "/lib/security/pam_unix.so",
        "Standard Unix authentication (passwd/shadow)",
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT, PamModuleType.SESSION, PamModuleType.PASSWORD},
        provides=["password", "shadow", "nis", "unix"]),
    PamModule("pam_nologin.so", "/lib/security/pam_nologin.so",
        "Refuse non-root logins when /etc/nologin exists",
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT}),
    PamModule("pam_env.so", "/lib/security/pam_env.so",
        "Set/unset environment variables from /etc/environment",
        supports={PamModuleType.AUTH, PamModuleType.SESSION}),
    PamModule("pam_limits.so", "/lib/security/pam_limits.so",
        "Apply /etc/security/limits.conf",
        supports={PamModuleType.SESSION}),
    PamModule("pam_deny.so", "/lib/security/pam_deny.so",
        "Always deny",
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT, PamModuleType.SESSION, PamModuleType.PASSWORD}),
    PamModule("pam_permit.so", "/lib/security/pam_permit.so",
        "Always permit",
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT, PamModuleType.SESSION, PamModuleType.PASSWORD}),
    PamModule("pam_warn.so", "/lib/security/pam_warn.so",
        "Log a warning and continue",
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT, PamModuleType.SESSION, PamModuleType.PASSWORD}),
    PamModule("pam_cracklib.so", "/lib/security/pam_cracklib.so",
        "Password strength check (legacy)",
        is_legacy=True,
        supports={PamModuleType.PASSWORD}),
    PamModule("pam_pwquality.so", "/lib/security/pam_pwquality.so",
        "Password quality check (replacement for cracklib)",
        supports={PamModuleType.PASSWORD}),
    PamModule("pam_tally2.so", "/lib/security/pam_tally2.so",
        "Failed-login counter",
        is_legacy=True,
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT}),
    PamModule("pam_faillock.so", "/lib/security/pam_faillock.so",
        "Failed-login locking",
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT}),
    PamModule("pam_ldap.so", "/lib/security/pam_ldap.so",
        "LDAP authentication",
        is_uncommon=True,
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT, PamModuleType.SESSION, PamModuleType.PASSWORD}),
    PamModule("pam_krb5.so", "/lib/security/pam_krb5.so",
        "Kerberos 5 authentication",
        is_uncommon=True,
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT, PamModuleType.SESSION, PamModuleType.PASSWORD}),
    PamModule("pam_sss.so", "/lib/security/pam_sss.so",
        "System Security Services daemon",
        is_uncommon=True,
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT, PamModuleType.SESSION, PamModuleType.PASSWORD}),
    PamModule("pam_gnome_keyring.so", "/lib/security/pam_gnome_keyring.so",
        "Unlock the GNOME keyring at login",
        is_uncommon=True,
        supports={PamModuleType.AUTH, PamModuleType.SESSION, PamModuleType.PASSWORD}),
    PamModule("pam_systemd.so", "/lib/security/pam_systemd.so",
        "Register session with systemd-logind",
        is_uncommon=True,
        supports={PamModuleType.SESSION, PamModuleType.AUTH, PamModuleType.ACCOUNT}),
    PamModule("pam_loginuid.so", "/lib/security/pam_loginuid.so",
        "Set audit uid from the kernel",
        supports={PamModuleType.SESSION}),
    PamModule("pam_umask.so", "/lib/security/pam_umask.so",
        "Set the file-creation mask",
        supports={PamModuleType.SESSION}),
    PamModule("pam_userpass.so", "/lib/security/pam_userpass.so",
        "Change expired passwords",
        supports={PamModuleType.AUTH, PamModuleType.PASSWORD}),
    PamModule("pam_access.so", "/lib/security/pam_access.so",
        "Apply /etc/security/access.conf",
        supports={PamModuleType.ACCOUNT}),
    PamModule("pam_time.so", "/lib/security/pam_time.so",
        "Apply /etc/security/time.conf",
        supports={PamModuleType.ACCOUNT}),
    PamModule("pam_sepermit.so", "/lib/security/pam_sepermit.so",
        "Allow/deny based on SELinux user",
        is_uncommon=True,
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT, PamModuleType.SESSION}),
    PamModule("pam_namespace.so", "/lib/security/pam_namespace.so",
        "Polyinstantiated directories",
        supports={PamModuleType.SESSION}),
    PamModule("pam_motd.so", "/lib/security/pam_motd.so",
        "Show message of the day",
        supports={PamModuleType.SESSION}),
    PamModule("pam_mail.so", "/lib/security/pam_mail.so",
        "Inform user of incoming mail",
        supports={PamModuleType.SESSION}),
    PamModule("pam_exec.so", "/lib/security/pam_exec.so",
        "Run an external command",
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT, PamModuleType.SESSION, PamModuleType.PASSWORD}),
    PamModule("pam_echo.so", "/lib/security/pam_echo.so",
        "Echo a message to the user",
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT, PamModuleType.SESSION, PamModuleType.PASSWORD}),
    PamModule("pam_keyinit.so", "/lib/security/pam_keyinit.so",
        "Revoke the session keyring on logout",
        supports={PamModuleType.SESSION}),
    PamModule("pam_selinux.so", "/lib/security/pam_selinux.so",
        "SELinux context management",
        is_uncommon=True,
        supports={PamModuleType.SESSION, PamModuleType.AUTH}),
    PamModule("pam_apparmor.so", "/lib/security/pam_apparmor.so",
        "AppArmor profile change",
        is_uncommon=True,
        supports={PamModuleType.SESSION, PamModuleType.AUTH}),
    PamModule("pam_cap.so", "/lib/security/pam_cap.so",
        "Drop capabilities on session start",
        supports={PamModuleType.SESSION}),
    PamModule("pam_pkcs11.so", "/lib/security/pam_pkcs11.so",
        "Smart card / PKCS#11 authentication",
        is_uncommon=True,
        supports={PamModuleType.AUTH, PamModuleType.ACCOUNT}),
    PamModule("pam_ssh.so", "/lib/security/pam_ssh.so",
        "ssh-agent pass-through",
        is_uncommon=True,
        supports={PamModuleType.AUTH, PamModuleType.SESSION}),
    PamModule("pam_yubico.so", "/lib/security/pam_yubico.so",
        "YubiKey OTP authentication",
        is_uncommon=True,
        supports={PamModuleType.AUTH}),
    PamModule("pam_u2f.so", "/lib/security/pam_u2f.so",
        "FIDO2 / U2F authentication",
        is_uncommon=True,
        supports={PamModuleType.AUTH}),
    PamModule("pam_fprintd.so", "/lib/security/pam_fprintd.so",
        "Fingerprint authentication",
        is_uncommon=True,
        supports={PamModuleType.AUTH}),
    PamModule("pam_google_authenticator.so", "/lib/security/pam_google_authenticator.so",
        "TOTP via Google Authenticator",
        is_uncommon=True,
        supports={PamModuleType.AUTH}),
]


@dataclass
class PamService:
    """One service config in /etc/pam.d/<service>."""
    service: str
    rules: List[Dict] = field(default_factory=list)

    def add_rule(
        self,
        type_,
        control,
        module: str,
        args: Optional[List[str]] = None,
    ) -> None:
        # Accept both enum members and raw strings.
        if hasattr(type_, "value"):
            type_ = type_.value
        if hasattr(control, "value"):
            control = control.value
        self.rules.append({
            "type": type_,
            "control": control,
            "module": module,
            "args": list(args or []),
        })


class PamLibraryManager:
    """
    Manages ``/lib/security`` — the PAM module directory.
    """

    def __init__(
        self,
        lib_path: str = "/lib",
        security_path: str = "/lib/security",
    ) -> None:
        self.lib_path = Path(lib_path)
        self.security_path = Path(security_path)
        self._modules: Dict[str, PamModule] = {
            m.name: m for m in _STOCK_PAM_MODULES
        }
        self._services: Dict[str, PamService] = {}

    # ── module listing / lookup ───────────────────────────────────

    def list_modules(self) -> List[PamModule]:
        return list(self._modules.values())

    def find_module(self, name: str) -> Optional[PamModule]:
        if name in self._modules:
            return self._modules[name]
        if not name.startswith("pam_"):
            name = "pam_" + name
        if not name.endswith(".so"):
            name = name + ".so"
        return self._modules.get(name)

    def modules_supporting(self, type_: PamModuleType) -> List[PamModule]:
        return [m for m in self._modules.values() if type_ in m.supports]

    def modules_for_auth(self) -> List[PamModule]:
        return self.modules_supporting(PamModuleType.AUTH)

    def register_module(self, module: PamModule) -> None:
        self._modules[module.name] = module

    # ── service management (/etc/pam.d) ──────────────────────────

    def create_service(self, service: str) -> PamService:
        svc = self._services.get(service) or PamService(service=service)
        self._services[service] = svc
        return svc

    def get_service(self, service: str) -> Optional[PamService]:
        return self._services.get(service)

    def list_services(self) -> List[str]:
        return sorted(self._services.keys())

    # ── on-disk materialisation ───────────────────────────────────

    def materialise_stubs(self, root: str = "/") -> int:
        target = Path(root) / "lib" / "security"
        target.mkdir(parents=True, exist_ok=True)
        written = 0
        for m in self._modules.values():
            p = target / m.name
            if not p.exists():
                p.write_bytes(
                    b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
                    + f"UmerOS stub for {m.name} ({m.description})\n".encode()
                )
                written += 1
        return written

    # ── summary ───────────────────────────────────────────────────

    def get_summary(self) -> Dict:
        return {
            "total_modules": len(self._modules),
            "legacy_modules": sum(1 for m in self._modules.values() if m.is_legacy),
            "uncommon_modules": sum(1 for m in self._modules.values() if m.is_uncommon),
            "modules_per_type": {
                t.value: len(self.modules_supporting(t))
                for t in PamModuleType
            },
            "total_size_bytes": sum(m.size for m in self._modules.values()),
            "services_defined": len(self._services),
            "directory": str(self.security_path),
        }


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = PamLibraryManager(lib_path=tmpdir, security_path=tmpdir)
        summary = mgr.get_summary()
        assert "total_modules" in summary, "summary should have total_modules"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
