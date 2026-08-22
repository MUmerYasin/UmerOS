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

#!/usr/bin/env python3
"""
Umer OS Initrd /init entry point
================================
A thin wrapper that lets the initrd boot as a real ``/init`` binary
inside the unpacked tmpfs.

When the kernel finishes phase 1-3 of the TLDP boot it executes
``/init`` (PID 1) with the initrd as its root.  The cpio archive built
by :mod:`initrd.builder` installs the file ``/usr/lib/umeros/initrd/
linuxrc_main.py`` plus a symlink ``/linuxrc`` and a ``/init`` shell
stub that re-execs this Python file.

In standalone mode (running on the build host, not in the kernel)
the script accepts a path to a cpio archive and runs the same
runtime.

Usage inside the initrd::

    /init                                # uses /etc/umeros/initrd.conf
    /init /path/to/initramfs.img.gz      # explicit image

Usage on the host for smoke tests::

    python -m initrd.linuxrc_main /path/to/initramfs.img.gz
    python initrd/linuxrc_main.py /path/to/initramfs.img.gz

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Make sure the package import works whether we are inside the cpio
# archive (where /usr/lib/umeros is the real path) or on the build
# host (where the module is on PYTHONPATH).
_THIS_DIR = Path(__file__).resolve().parent
_PARENT = _THIS_DIR.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from initrd.archivers import detect_archiver  # noqa: E402
from initrd.builder import BuildRequest  # noqa: E402
from initrd.cpio import unpack_archive  # noqa: E402
from initrd.linuxrc import BootContext, run  # noqa: E402
from initrd.scenarios import ScenarioId  # noqa: E402

log = logging.getLogger("UmerOS.Initrd.LinuxrcMain")


CONFIG_PATHS = (
    "/etc/umeros/initrd.conf",
    "/etc/initrd.conf",
    "/initrd.conf",
)


def _load_config(host_root: str) -> BuildRequest:
    for rel in CONFIG_PATHS:
        path = Path(host_root) / rel.lstrip("/")
        if path.is_file():
            try:
                return BuildRequest.from_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, KeyError) as exc:
                log.warning("could not load %s: %s", path, exc)
    return BuildRequest(
        kernel_version=os.uname().release if hasattr(os, "uname") else "host",
        scenario=ScenarioId.NORMAL,
    )


def _load_image(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_bytes()
    archiver = detect_archiver(raw)
    if archiver.extension:
        log.info("decompressing via %s", archiver.__name__)
        raw = archiver.decompress(raw)
    return raw


def main(argv: Optional[list] = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    argv = list(sys.argv[1:] if argv is None else argv)
    image_path = Path(argv[0]).resolve() if argv else None
    host_root = os.environ.get("UMEROS_HOST_ROOT", os.getcwd())

    request = _load_config(host_root)
    if image_path is not None:
        blob = _load_image(image_path)
    else:
        # No image supplied - synthesise a tiny cpio so the runtime has
        # something to extract.  Useful for the "PID 1 booted with an
        # empty initrd" edge case.
        from initrd.cpio import pack_archive, newc_dir, newc_file
        blob = pack_archive([
            newc_dir("bin"),
            newc_file("init", b"#!/bin/sh\nexit 0\n", mode=0o755),
        ])

    ctx = BootContext.from_request(request, blob=blob, host_root=host_root)
    return run(ctx)


if __name__ == "__main__":
    sys.exit(main())
