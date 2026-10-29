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
UmerOS /media/network - Network Share Management
================================================

Manages network-mounted filesystems (SMB/CIFS, NFS, SSHFS, etc.)
under the /media/network hierarchy, following Linux FHS conventions.

Modules
-------
- **network_share** - Share type definitions, URIs, and credentials.
- **network_mount** - Mount/unmount operations for network shares.
- **network_discovery** - Browse and discover available network shares.
- **network_credentials** - Secure credential storage and management.

Quick start::

    from media.network import NetworkShareManager, ShareProtocol

    mgr = NetworkShareManager()
    share = mgr.add_share(
        name="office_docs",
        protocol=ShareProtocol.SMB,
        host="192.168.1.10",
        path="/shared/documents",
        username="user",
        password="pass",
    )
    mount_point = mgr.mount(share)
    print(f"Mounted at {mount_point}")
"""

from __future__ import annotations

from .network_share import (
    ShareProtocol,
    NetworkShare,
    ShareCredentials,
    ShareStatus,
    NetworkShareManager,
)
from .network_mount import (
    NetworkMountResult,
    mount_share,
    unmount_share,
    is_share_mounted,
    list_mounted_shares,
)
from .network_discovery import (
    NetworkBrowser,
    DiscoveredShare,
    discover_smb_shares,
    discover_nfs_exports,
)
from .network_credentials import (
    CredentialStore,
    NetworkCredential,
    save_credential,
    load_credential,
    delete_credential,
)

__all__ = [
    # network_share
    "ShareProtocol",
    "NetworkShare",
    "ShareCredentials",
    "ShareStatus",
    "NetworkShareManager",
    # network_mount
    "NetworkMountResult",
    "mount_share",
    "unmount_share",
    "is_share_mounted",
    "list_mounted_shares",
    # network_discovery
    "NetworkBrowser",
    "DiscoveredShare",
    "discover_smb_shares",
    "discover_nfs_exports",
    # network_credentials
    "CredentialStore",
    "NetworkCredential",
    "save_credential",
    "load_credential",
    "delete_credential",
]


def _selftest() -> bool:
    import importlib as _il
    import sys as _sys
    pkg = _il.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"{__name__} selftest FAIL: missing {missing}", file=_sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)