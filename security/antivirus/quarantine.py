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

"""Quarantine system for isolating detected threats."""

import json
import os
import shutil
import time
import base64
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class QuarantineEntry:
    id: str
    original_path: str
    quarantine_path: str
    threat_name: str
    threat_level: str
    detection_method: str
    quarantined_at: float
    file_size: int
    md5: str
    sha256: str
    restored: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "original_path": self.original_path,
            "quarantine_path": self.quarantine_path,
            "threat_name": self.threat_name,
            "threat_level": self.threat_level,
            "detection_method": self.detection_method,
            "quarantined_at": self.quarantined_at,
            "file_size": self.file_size,
            "md5": self.md5,
            "sha256": self.sha256,
            "restored": self.restored,
        }


class QuarantineManager:
    def __init__(self, quarantine_dir: Optional[str] = None):
        self._quarantine_dir = quarantine_dir or os.path.join(
            os.path.dirname(__file__), "quarantine"
        )
        self._meta_path = os.path.join(self._quarantine_dir, "quarantine.json")
        self._entries: Dict[str, QuarantineEntry] = {}
        os.makedirs(self._quarantine_dir, exist_ok=True)
        self._load_metadata()

    def _load_metadata(self):
        if os.path.exists(self._meta_path):
            try:
                with open(self._meta_path, "r") as f:
                    data = json.load(f)
                for key, val in data.items():
                    self._entries[key] = QuarantineEntry(**val)
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_metadata(self):
        data = {k: v.to_dict() for k, v in self._entries.items()}
        with open(self._meta_path, "w") as f:
            json.dump(data, f, indent=2)

    def quarantine_file(
        self,
        file_path: str,
        threat_name: str,
        threat_level: str,
        detection_method: str,
        md5: str = "",
        sha256: str = "",
    ) -> Optional[QuarantineEntry]:
        if not os.path.exists(file_path):
            return None

        entry_id = f"Q-{int(time.time()*1000)}"
        safe_name = os.path.basename(file_path).replace("/", "_").replace("\\", "_")
        quarantine_path = os.path.join(self._quarantine_dir, f"{entry_id}_{safe_name}")

        try:
            # Read and XOR-encrypt the file content to prevent accidental execution
            with open(file_path, "rb") as f:
                original = f.read()

            # Simple XOR obfuscation (not strong crypto, but prevents casual execution)
            obfuscated = bytes(b ^ 0xAA for b in original)
            with open(quarantine_path, "wb") as f:
                f.write(obfuscated)

            # Remove original
            file_size = os.path.getsize(file_path)
            os.remove(file_path)

            entry = QuarantineEntry(
                id=entry_id,
                original_path=os.path.abspath(file_path),
                quarantine_path=quarantine_path,
                threat_name=threat_name,
                threat_level=threat_level,
                detection_method=detection_method,
                quarantined_at=time.time(),
                file_size=file_size,
                md5=md5,
                sha256=sha256,
            )
            self._entries[entry_id] = entry
            self._save_metadata()
            return entry
        except Exception:
            return None

    def restore_file(self, entry_id: str) -> bool:
        entry = self._entries.get(entry_id)
        if not entry or not os.path.exists(entry.quarantine_path):
            return False

        try:
            with open(entry.quarantine_path, "rb") as f:
                obfuscated = f.read()
            original = bytes(b ^ 0xAA for b in obfuscated)

            os.makedirs(os.path.dirname(entry.original_path), exist_ok=True)
            with open(entry.original_path, "wb") as f:
                f.write(original)

            os.remove(entry.quarantine_path)
            entry.restored = True
            self._save_metadata()
            return True
        except Exception:
            return False

    def delete_quarantined(self, entry_id: str) -> bool:
        entry = self._entries.get(entry_id)
        if not entry:
            return False
        try:
            if os.path.exists(entry.quarantine_path):
                os.remove(entry.quarantine_path)
            del self._entries[entry_id]
            self._save_metadata()
            return True
        except Exception:
            return False

    def list_entries(self) -> List[QuarantineEntry]:
        return list(self._entries.values())

    def get_entry(self, entry_id: str) -> Optional[QuarantineEntry]:
        return self._entries.get(entry_id)

    def get_stats(self) -> dict:
        entries = self.list_entries()
        return {
            "total": len(entries),
            "active": sum(1 for e in entries if not e.restored),
            "restored": sum(1 for e in entries if e.restored),
            "total_size_bytes": sum(e.file_size for e in entries if not e.restored),
        }
