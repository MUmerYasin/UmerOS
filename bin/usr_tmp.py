"""
UmerOS /usr/tmp - User Space Temporary Files
=============================================
TLDP /usr: User space temporary files. Not found on modern distributions.
Was created as a consequence of UNIX heritage.
"""

from __future__ import annotations

from core.command import Command


class UsrTmpCommand(Command):
    """User space temporary directory."""

    name = "usr-tmp"
    description = "/usr/tmp - user space temporary files (legacy)"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/tmp/ - User space temporary files\n"
            "  Legacy location, rarely used on modern systems.\n"
            "  Modern equivalent: /var/tmp/ or /tmp/\n"
            "  Original from UNIX heritage.\n"
        )


class UsrTmpLinkCommand(Command):
    """usr/tmp symlink management."""

    name = "usr-tmp-link"
    description = "Manage /usr/tmp symlinks"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/tmp -> /var/tmp (symlink)\n"
            "  On modern systems, /usr/tmp is typically a symlink\n"
            "  to /var/tmp for backward compatibility.\n"
        )
