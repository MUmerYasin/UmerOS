# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

"""
UmerOS /tools — System Tools & Utilities
=========================================

System installation, diagnostics, and utility tools for UmerOS.

Modules
-------
- **installer** - UmerOS installation and setup
- **system_info** - Hardware and OS information
- **disk_tools** - Disk/partition management
- **network_tools** - Network diagnostics
- **process_tools** - Process management

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
import os
import sys

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Tools")

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)


def _try_import(module_name: str, names: tuple) -> None:
    global __all__
    try:
        mod = __import__(f"tools.{module_name}", fromlist=names)
    except ImportError as exc:
        log.warning("tools.%s could not be imported (%s); skipping.", module_name, exc)
        return
    for n in names:
        if hasattr(mod, n):
            globals()[n] = getattr(mod, n)
            __all__ = list(__all__) + [n]


for _mod, _names in (
    ("installer", ("show_license", "install_umer_os", "verify_installation", "uninstall_umer_os", "get_install_info")),
    ("system_info", ("SystemInfo", "get_system_info", "get_cpu_info", "get_memory_info")),
    ("disk_tools", ("DiskManager", "get_disk_usage", "list_partitions")),
    ("network_tools", ("NetworkDiagnostics", "ping_host", "dns_lookup")),
    ("process_tools", ("ProcessManager", "list_processes", "kill_process", "get_process_info")),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    import importlib
    import sys
    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"tools selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)