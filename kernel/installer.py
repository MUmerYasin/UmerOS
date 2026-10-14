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
UmerOS /kernel — installer script (prototype)  [EXPERIMENTAL]
=============================================================
Copies the OS modules into a target directory to create a simulated install.

.. note:: This is a legacy prototype.  The canonical installer lives in the
   ``installer/`` package (``installer/installer.py``), which performs real
   integrity verification and records a proper install log.
"""

from __future__ import annotations

import logging
import os
import shutil

log = logging.getLogger("UmerOS.Kernel.Installer")

_MODULES = (
    "bootloader.py",
    "umer_kernel.py",
    "quantum_sim.py",
    "umer_ai.py",
    "gui.py",
    "container_engine.py",
    "security.py",
    "qfs.py",
    "installer.py",
)


def install_files(target_dir: str = "umer_os") -> int:
    """Copy the OS modules into *target_dir*; return the number of files copied."""
    log.info("Installing Umer OS to '%s'...", target_dir)
    os.makedirs(target_dir, exist_ok=True)
    copied = 0
    for mod in _MODULES:
        if os.path.exists(mod):
            shutil.copy(mod, os.path.join(target_dir, mod))
            log.info("  Copied %s", mod)
            copied += 1
        else:
            log.warning("  %s not found, skipping.", mod)
    # Create a config file.
    with open(os.path.join(target_dir, "umer_os.conf"), "w") as f:
        f.write("version=1.0.0\n")
        f.write("quantum_simulation=True\n")
    log.info("Installation complete (%d files copied).", copied)
    return copied
