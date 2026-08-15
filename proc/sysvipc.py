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
