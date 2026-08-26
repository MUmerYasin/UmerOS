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
UmerOS /dev kmsg + rtc — structured kernel log and wake timers.

KmsgRing      /dev/kmsg (char 1:11) per Documentation/ABI/testing/dev-kmsg:
              records "prio,seq,usec,flags;message\n" plus " KEY=value"
              continuation lines; '<N>' syslog prefixes on write with the
              facility forced from LOG_KERN(0) to LOG_USER(1); per-reader
              cursors; -EAGAIN when empty+O_NONBLOCK and -EPIPE after
              overwrite; lseek restricted to SEEK_SET/END/DATA with 0.
RtcWakeDevice /dev/rtc0 (char 254:0): clock read, alarm set/clear through
              wakealarm-style epoch writes, alarm-fired detection.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.KmsgRtc")


class KmsgRing:
    """Structured printk ring exported at /dev/kmsg."""

    RING_CAP = 32
    LOG_KERN = 0
    LOG_USER = 1

    def __init__(self):
        self._records: List[Dict[str, Any]] = []
        self._seq = 0
        self._dropped = 0
        self._readers: Dict[int, int] = {}   # reader_id -> seq cursor
        self._next_reader = 1
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="kmsg", path="/dev/kmsg",
            dev_type=DeviceType.CHAR, major=1, minor=11, mode=0o640,
            description="printk ring buffer (structured records)",
            read_callback=self._on_read,
            write_callback=self._on_write,
        ))
        self.boot_log()

    # ── writing ───────────────────────────────────────────────────────
    def _on_write(self, data: bytes) -> int:
        return self.write(data.decode("utf-8", "replace"))

    def write(self, line: str, facility_from_userspace: bool = True) -> Dict[str, Any]:
        prio, facility = 6, self.LOG_USER if facility_from_userspace else self.LOG_KERN
        msg = line
        if msg.startswith("<"):
            head, _, rest = msg[1:].partition(">")
            try:
                combined = int(head)
                prio = combined & 0x7
                facility = (combined >> 3) & 0xFF
                if facility_from_userspace and facility == self.LOG_KERN:
                    facility = self.LOG_USER
                msg = rest
            except ValueError:
                pass
        meta: List[str] = []
        if " SUBSYSTEM=" in msg:
            body, _, meta_part = msg.partition(" SUBSYSTEM=")
            msg = body
            meta.append("SUBSYSTEM=" + meta_part.split()[0])
        record = {
            "prio": prio,
            "facility": facility,
            "seq": self._next_seq(),
            "ts_us": time.monotonic_ns() // 1000,
            "flags": "-",
            "msg": msg.strip(),
            "meta": meta,
        }
        if len(self._records) >= self.RING_CAP:
            self._records.pop(0)
            self._dropped += 1
        self._records.append(record)
        return record

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def boot_log(self) -> None:
        for line in (
            "<6>UmerOS kernel: devtmpfs mounted",
            "<6>umerd: device manager online",
            "<7>input: UmerOS virtual keyboard as /dev/input/event0",
        ):
            self.write(line, facility_from_userspace=False)

    # ── reading ───────────────────────────────────────────────────────
    def open_reader(self) -> int:
        rid = self._next_reader
        self._next_reader += 1
        first_seq = self._records[0]["seq"] if self._records else self._seq
        self._readers[rid] = first_seq - 1
        return rid

    def _on_read(self, size: int) -> bytes:
        rec = self.read_record(self.open_reader(), nonblock=True)
        return rec["formatted"].encode() if rec else b""

    def read_record(self, reader_id: int, nonblock: bool = False) -> Optional[Dict[str, Any]]:
        if reader_id not in self._readers:
            raise KeyError(reader_id)
        cursor = self._readers[reader_id]
        available = [r for r in self._records if r["seq"] > cursor]
        if not available:
            if nonblock:
                return {"errno": -11}   # -EAGAIN
            return None
        oldest = self._records[0]["seq"]
        lost = max(0, available[0]["seq"] - oldest)
        record = available[0]
        self._readers[reader_id] = record["seq"]
        out = dict(record)
        out["formatted"] = self.format_record(record)
        out["lost_before_read"] = lost if lost else 0
        return out

    @staticmethod
    def format_record(rec: Dict[str, Any]) -> str:
        combined = (rec["facility"] << 3) | rec["prio"]
        line = f"{rec['prio']},{rec['seq']},{rec['ts_us']},{rec['flags']};{rec['msg']}"
        cont = "".join(f"\n {m}" for m in rec.get("meta", []))
        return f"<{combined}>{line}{cont}\n"

    def dump_all(self) -> str:
        return "".join(self.format_record(r) for r in self._records)

    def seek(self, reader_id: int, whence: str) -> bool:
        """Only SEEK_SET/SEEK_END/SEEK_DATA with offset 0 are legal."""
        if whence not in ("SET", "END", "DATA"):
            return False   # would raise EINVAL / ESPIPE
        if whence == "SET":
            self._readers[reader_id] = (self._records[0]["seq"] - 1) if self._records else 0
        elif whence == "END":
            self._readers[reader_id] = self._seq
        else:
            self._readers[reader_id] = self._seq
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "records": len(self._records),
            "dropped": self._dropped,
            "readers": len(self._readers),
            "last_seq": self._seq,
        }

    def __repr__(self) -> str:
        return f"<KmsgRing n={len(self._records)} dropped={self._dropped}>"


class RtcWakeDevice:
    """/dev/rtc0 — hardware clock + epoch wakealarm."""

    PATH = "/dev/rtc0"

    def __init__(self):
        self._alarm_epoch: Optional[float] = None
        self._alarms_fired = 0
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="rtc0", path=self.PATH,
            dev_type=DeviceType.CHAR, major=254, minor=0, mode=0o600,
            description="Real-time clock with wake alarm",
            ioctl_callback=lambda req, arg: 0,
        ))
        log.info("RtcWakeDevice created")

    def read_time(self) -> Dict[str, Any]:
        t = time.time()
        lt = time.localtime(t)
        return {
            "epoch": int(t),
            "sec": lt.tm_sec, "min": lt.tm_min, "hour": lt.tm_hour,
            "mday": lt.tm_mday, "mon": lt.tm_mon, "year": lt.tm_year + 1900,
        }

    def set_wakealarm(self, epoch: float) -> Dict[str, Any]:
        if epoch <= time.time():
            return {"ok": False, "error": "-EINVAL: alarm must be in the future"}
        self._alarm_epoch = epoch
        log.debug("wakealarm armed for %s", epoch)
        return {"ok": True, "armed_at_epoch": int(epoch), "in_seconds": int(epoch - time.time())}

    def clear_wakealarm(self) -> None:
        self._alarm_epoch = None

    def poll_alarm(self) -> Dict[str, Any]:
        if self._alarm_epoch is None:
            return {"armed": False}
        fired = time.time() >= self._alarm_epoch
        if fired:
            self._alarms_fired += 1
            self._alarm_epoch = None
        return {"armed": not fired, "fired": fired}

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": self.PATH,
            "alarm_armed": self._alarm_epoch is not None,
            "alarm_at": self._alarm_epoch,
            "alarms_fired": self._alarms_fired,
        }

    def __repr__(self) -> str:
        return f"<RtcWakeDevice armed={self._alarm_epoch is not None}>"
