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

"""/proc/sysvipc/* — System V IPC resource listing.

Mirrors the Linux ``ipcs -a`` data exposed via /proc:
    message queues, semaphore arrays, and shared memory segments.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from proc.nodes import ProcDir, ProcFile

if TYPE_CHECKING:
    from proc.procfs import ProcFileSystem


def register_sysvipc_entries(fs: "ProcFileSystem") -> None:
    adapter = fs.adapter
    ipc_info = adapter.ipc_info()

    sysvipc = ProcDir("sysvipc")
    fs.root.add(sysvipc)

    # ── msg — message queues ────────────────────────────────────
    def _msg() -> str:
        return (
            "       key      msqid perms      cbytes      qnum lspid lrpid   uid   gid  cuid  cgid  stime      rtime      ctime\n"
            "0x00000000 65536     0666  0          0       0     0   0     0     0     0     0    0          0          0\n"
        )

    sysvipc.add(ProcFile("msg", _msg))

    # ── sem — semaphore arrays ──────────────────────────────────
    def _sem() -> str:
        return (
            "       key      semid perms      nsems   cuid   cgid   uid   gid  otime      ctime\n"
            "0x00000000 0        0666      16      0      0      0     0    0          0\n"
        )

    sysvipc.add(ProcFile("sem", _sem))

    # ── shm — shared memory segments ───────────────────────────
    def _shm() -> str:
        return (
            "       key      shmid perms              size  cpid  lpid  nattch     uid   gid  cuid  cgid  atime      dtime      ctime                   rss\n"
            "0x00000000 0        0666             524288    1000 0     1          0     0     0     0    0          0          0                   0\n"
        )

    sysvipc.add(ProcFile("shm", _shm))
