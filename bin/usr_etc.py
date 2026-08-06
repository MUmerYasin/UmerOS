"""
UmerOS /usr/etc - System Configuration Hierarchy
=================================================
TLDP /usr: Another directory for configuration files. Virtually unused now.
"""

from __future__ import annotations

from core.command import Command


class UsrEtcCommand(Command):
    """System-wide configuration (usr/etc)."""

    name = "usr-etc"
    description = "/usr/etc - system-wide configuration (rarely used)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/etc/ - System-wide configuration\n"
            "  Theoretically for configuration files shared across hosts.\n"
            "  Virtually unused on modern Linux systems.\n"
            "  Preferred location: /etc/ for host-specific config,\n"
            "  /usr/share/etc/ for shareable config.\n"
        )


class UsrEtcDefaultCommand(Command):
    """Default values for programs."""

    name = "usr-etc-default"
    description = "/usr/etc/default - default program values"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/etc/default/ - Default configuration values\n"
            "  Used to store default settings for programs.\n"
            "  Similar to /etc/default/ but for read-only /usr.\n"
        )


class UsrEtcProfileCommand(Command):
    """System-wide profile scripts."""

    name = "usr-etc-profile"
    description = "/usr/etc/profile - system-wide shell profile"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/etc/profile.d/ - System-wide shell initialization\n"
            "  Scripts executed by login shells.\n"
            "  Similar to /etc/profile.d/ but for /usr.\n"
        )
