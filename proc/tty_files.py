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

"""/proc/tty/* — terminal device information.

    drivers/  — driver usage counters (serial, vt, console)
    ldiscs/   — line discipline registration table
    driver/   — per-driver subdirectory (serial port stats)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from proc.nodes import ProcDir, ProcFile

if TYPE_CHECKING:
    from proc.procfs import ProcFileSystem


def register_tty_entries(fs: "ProcFileSystem") -> None:
    adapter = fs.adapter

    tty = ProcDir("tty")
    fs.root.add(tty)

    # ── drivers ─────────────────────────────────────────────────
    def _drivers() -> str:
        return (
            "serconsole\t1\n"
            "uart\t4096\n"
            "vt\t2\n"
            "console\t1\n"
        )

    tty.add(ProcFile("drivers", _drivers))

    # ── ldiscs — line disciplines ───────────────────────────────
    def _ldiscs() -> str:
        return (
            "tty ldisc 0: (n_tty)\n"
            "tty ldisc 1: (n_hdlc)\n"
            "tty ldisc 2: (n_raw)\n"
            "tty ldisc 3: (n_slip)\n"
            "tty ldisc 4: (n_ppp)\n"
            "tty ldisc 5: (n_vt)\n"
        )

    tty.add(ProcFile("ldiscs", _ldiscs))

    # ── driver/serial — serial port stats ────────────────────────
    driver = ProcDir("driver")
    tty.add(driver)
    serial = ProcDir("serial")
    driver.add(serial)
    serial.add(ProcFile("serial0", lambda: (
        "0: uart:16550A port:0x03F8 irq:4 tx:0 rx:0 CTS|DSR\n"
        "1: uart:16550A port:0x02F8 irq:3 tx:0 rx:0 DSR\n"
    )))
    serial.add(ProcFile("serial1", lambda: (
        "0: uart:16550A port:0x03F8 irq:4 tx:0 rx:0 CTS|DSR\n"
    )))

    # ── per-tty device dirs (tty0, tty1, console, etc.) ────────
    for tty_name in ("tty0", "tty1", "ttyS0", "console"):
        n = ProcDir(tty_name)
        n.add(ProcFile("device",
                       lambda: f"4:{tty_name if tty_name.startswith('ttyS') else '0'}\n",
                       mode="r--r--r--"))
        tty.add(n)
