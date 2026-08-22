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
UmerOS - /etc/cups + /etc/printcap manager
FHS 3.0: /etc/cups/ contains CUPS configuration.
/etc/printcap is the printer capability database.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List

CUPS_DIR = Path(os.environ.get("UMEROS_CUPS", "/etc/cups"))
PRINTCAP = Path(os.environ.get("UMEROS_PRINTCAP", "/etc/printcap"))

DEFAULT_PRINTCAP = """# /etc/printcap - UmerOS printer database
# Format: name|description:\\
#   :sd=spool-dir:\\
#   :lp=device:\\
#   :lf=log-file:
"""

DEFAULT_CUPSD_CONF = """# cupsd.conf - CUPS scheduler configuration
Listen localhost:631
ServerName umerOS
ServerAlias localhost
ErrorLog /var/log/cups/error_log
AccessLog /var/log/cups/access_log
"""


class CUPSConfigManager:
    """Manages CUPS printing configuration."""

    def __init__(self):
        CUPS_DIR.mkdir(parents=True, exist_ok=True)

    def _ensure_printcap(self) -> None:
        if not PRINTCAP.exists():
            PRINTCAP.write_text(DEFAULT_PRINTCAP, encoding="utf-8")

    def read_printcap(self) -> Dict[str, str]:
        self._ensure_printcap()
        printers = {}
        content = PRINTCAP.read_text(encoding="utf-8")
        for block in content.split("\n\n"):
            lines = [l.strip() for l in block.splitlines() if l.strip() and not l.strip().startswith("#")]
            if lines and ":" in lines[0]:
                name = lines[0].split("|")[0].split(":")[0].strip()
                printers[name] = "\n".join(lines)
        return printers

    def add_printer(self, name: str, description: str, device: str) -> None:
        entry = f"{name}|{description}:\\\n\t:lp={device}:\\\n\t:sd=/var/spool/cups/{name}:"
        with PRINTCAP.open("a", encoding="utf-8") as f:
            f.write(f"\n{entry}\n")

    def cups_conf_path(self) -> Path:
        return CUPS_DIR / "cupsd.conf"

    def read_cupsd_conf(self) -> str:
        p = self.cups_conf_path()
        if p.exists():
            return p.read_text(encoding="utf-8")
        return DEFAULT_CUPSD_CONF
