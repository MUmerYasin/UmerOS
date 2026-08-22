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
UmerOS Home Backup Manager
Backup and restore user home directories.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import shutil
import json
import tarfile
import hashlib
from datetime import datetime


@dataclass
class BackupRecord:
    username: str
    backup_path: str
    timestamp: str
    size_bytes: int = 0
    file_count: int = 0
    checksum: str = ""
    note: str = ""


class HomeBackupManager:
    """Manages home directory backups and restores."""

    def __init__(self, home_path: str = "/home",
                 backup_path: str = "/var/backups/homes"):
        self.home_path = Path(home_path)
        self.backup_path = Path(backup_path)
        self.backup_path.mkdir(parents=True, exist_ok=True)
        self.records: Dict[str, List[BackupRecord]] = {}

    def create_backup(self, username: str, note: str = "") -> Optional[BackupRecord]:
        """Create a tar.gz backup of a user's home."""
        user_home = self.home_path / username
        if not user_home.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_path / f"{username}_{timestamp}.tar.gz"

        with tarfile.open(str(backup_file), "w:gz") as tar:
            tar.add(str(user_home), arcname=username)

        size = backup_file.stat().st_size
        checksum = self._checksum(str(backup_file))
        file_count = sum(1 for _ in user_home.rglob('*') if _.is_file())

        record = BackupRecord(
            username=username,
            backup_path=str(backup_file),
            timestamp=timestamp,
            size_bytes=size,
            file_count=file_count,
            checksum=checksum,
            note=note,
        )

        self.records.setdefault(username, []).append(record)
        return record

    def restore_backup(self, username: str, backup_file: str) -> bool:
        """Restore a home directory from backup."""
        src = Path(backup_file)
        if not src.exists():
            return False

        user_home = self.home_path / username
        if user_home.exists():
            shutil.rmtree(str(user_home))

        with tarfile.open(str(src), "r:gz") as tar:
            tar.extractall(str(self.home_path))

        return True

    def list_backups(self, username: str = "") -> List[BackupRecord]:
        """List backups, optionally filtered by username."""
        if username:
            return self.records.get(username, [])
        all_records = []
        for records in self.records.values():
            all_records.extend(records)
        return sorted(all_records, key=lambda r: r.timestamp, reverse=True)

    def delete_backup(self, username: str, timestamp: str) -> bool:
        """Delete a specific backup."""
        records = self.records.get(username, [])
        for i, rec in enumerate(records):
            if rec.timestamp == timestamp:
                backup_file = Path(rec.backup_path)
                if backup_file.exists():
                    backup_file.unlink()
                records.pop(i)
                return True
        return False

    def get_latest_backup(self, username: str) -> Optional[BackupRecord]:
        """Get the most recent backup for a user."""
        records = self.records.get(username, [])
        if not records:
            return None
        return max(records, key=lambda r: r.timestamp)

    def _checksum(self, filepath: str) -> str:
        """Calculate SHA-256 checksum."""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def get_backup_stats(self) -> Dict:
        """Get overall backup statistics."""
        total_backups = sum(len(r) for r in self.records.values())
        total_size = sum(r.size_bytes for records in self.records.values() for r in records)
        return {
            "total_backups": total_backups,
            "total_size_bytes": total_size,
            "unique_users": len(self.records),
            "backup_dir": str(self.backup_path),
        }
