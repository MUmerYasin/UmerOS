"""
UmerOS /opt - Third-Party Package Hierarchy
=============================================

FHS/TLDP-compliant management of the /opt directory tree for
third-party and add-on software packages.

The ``/opt`` directory is reserved for the installation of "add-on"
software packages.  Each package installs in ``/opt/<provider>/<pkg>``
or ``/opt/<pkg>/`` with a standard subdirectory layout::

    /opt/<pkg>/bin      — program binaries
    /opt/<pkg>/etc      — package configuration
    /opt/<pkg>/include  — C/C++ headers
    /opt/<pkg>/info     — info documents
    /opt/<pkg>/lib      — libraries
    /opt/<pkg>/man      — man pages
    /opt/<pkg>/share    — architecture-independent data
    /opt/<pkg>/state    — variable/state data

Related system directories:

- ``/etc/opt/<pkg>/`` — host-specific configuration for /opt packages
- ``/var/opt/<pkg>/`` — variable/state data for /opt packages

Reserved for local sysadmin use (packages must NOT install here):

- ``/opt/bin``, ``/opt/doc``, ``/opt/include``, ``/opt/info``
- ``/opt/lib``, ``/opt/man``

Modules
-------
- **hierarchy** – ``/opt`` directory tree creation and reserved-dir protection.
- **package** – package install, uninstall, list, and metadata.
- **config** – ``/etc/opt`` host-specific configuration management.
- **var** – ``/var/opt`` variable data management.
- **fhs** – FHS compliance audit for the ``/opt`` hierarchy.
- **env** – ``$PATH`` and man-path integration for ``/opt/*/bin``.

Quick start::

    from opt import OptHierarchy, OptPackageManager

    # Create the /opt hierarchy with reserved dirs
    hierarchy = OptHierarchy()
    hierarchy.bootstrap()

    # Install a third-party package
    pkg_mgr = OptPackageManager()
    pkg_mgr.install("firefox", provider="mozilla",
                     source="/tmp/firefox.tar.gz")

    # List installed packages
    for info in pkg_mgr.list_packages():
        print(info["name"], info["provider"])
"""

from __future__ import annotations

from .config import EtcOptManager, PackageConfig
from .env import OptEnvManager
from .fhs import FHSFinding, OptFHSValidator, Severity
from .hierarchy import (
    OPT_ROOT,
    RESERVED_DIRS,
    OptHierarchy,
    PackageEntry,
)
from .package import (
    InstalledPackage,
    OptPackageManager,
    PackageManifest,
)
from .var import VarOptManager

__all__ = [
    # hierarchy
    "OPT_ROOT",
    "RESERVED_DIRS",
    "OptHierarchy",
    "PackageEntry",
    # package
    "PackageManifest",
    "InstalledPackage",
    "OptPackageManager",
    # config
    "PackageConfig",
    "EtcOptManager",
    # var
    "VarOptManager",
    # fhs
    "Severity",
    "FHSFinding",
    "OptFHSValidator",
    # env
    "OptEnvManager",
]
