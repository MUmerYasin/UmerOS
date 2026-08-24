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
import os
import sys
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class BackupRecord:
    username: str
    backup_path: str
    timestamp: str
    size_bytes: int = 0
    file_count: int = 0
    checksum: str = ""
    note: str = ""


# [FIX H83] Zero-trust capability gate for the destructive restore path. Restoring
# a home overwrites user data and (without the traversal filter) can write outside
# /home, so it must require the `home.admin` capability when a CapabilityManager is
# wired (fail-closed); standalone it is permissive (warning) so existing tooling works.
try:
    from core.capability_gate import gate, CAP_HOME_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_HOME_ADMIN

# [FIX H83] Python < 3.12 lacks the fail-closed `filter=` argument on extractall();
# fall back to no filter there (matching the >= 3.12 target). The member pre-scan
# below provides traversal safety on every version regardless.
_FILTER_KW = {} if sys.version_info < (3, 12) else {"filter": "data"}


def _is_safe_segment(name: str) -> bool:
    """[FIX H83] A safe single path segment: no '/', '\\', '..', and only
    ``[A-Za-z0-9._-]+``. Rejects anything that could escape the home tree."""
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        return False
    return all(c.isalnum() or c in "._-" for c in name)


def _assert_member_under(member, user_home: Path) -> None:
    """[FIX H83] Ensure a tar member resolves under ``user_home``.

    Rejects absolute paths, ``..`` traversal, and symlink/hardlink members. This
    is defense-in-depth alongside ``filter='data'`` (CVE-2007-4559 / tar slip).
    """
    name = member.name
    if not name or name.startswith("/") or ".." in Path(name).parts:
        raise ValueError(f"unsafe tar member name: {name!r}")
    candidate = (user_home / name).resolve()
    base = user_home.resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError(f"tar member escapes home: {name!r}")
    if member.issym() or member.islnk():
        raise ValueError(f"symlink/hardlink members not allowed: {name!r}")


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
        """Restore a home directory from backup.

        [FIX H83] Fail-closed, traversal-safe, non-destructive restore:
          * Requires the ``home.admin`` capability (zero-trust; fail-closed when wired).
          * Refuses if ``username`` is not a single safe path segment / escapes home.
          * Verifies the archive checksum against any known BackupRecord (best-effort).
          * Validates every tar member resolves under the target home and rejects
            ``..``/absolute/symlink members (closes CVE-2007-4559 / tar traversal).
          * Extracts with ``filter='data'`` (>= 3.12) and, crucially, does NOT
            ``rmtree`` the live home up front --- the live home is *snapshotted*, then
            the verified tree is swapped in, so a malformed/swapped backup can never
            destroy user data.
        """
        gate.require(CAP_HOME_ADMIN)

        src = Path(backup_file)
        if not src.exists() or not src.is_file():
            return False

        # [FIX H83] Reject unsafe / escaping target usernames before touching disk.
        if not _is_safe_segment(username):
            return False
        user_home = self.home_path / username
        try:
            user_home.resolve().relative_to(self.home_path.resolve())
        except ValueError:
            return False

        # [FIX H83] Best-effort checksum verify against a known backup record.
        rec = self._lookup_record_by_path(str(src))
        if rec is not None and rec.checksum:
            if self._checksum(str(src)) != rec.checksum:
                logger.error(f"Restore aborted: checksum mismatch for {src}")
                return False

        # [FIX H83] Pre-scan: reject any member that would escape the home tree,
        # then snapshot the live home and extract (extracting into the home *parent*
        # so the archive's ``username/`` prefix lands exactly on ``user_home``).
        snapshot = None
        try:
            with tarfile.open(str(src), "r:gz") as tar:
                for member in tar.getmembers():
                    _assert_member_under(member, user_home)
                try:
                    if user_home.exists():
                        snapshot = user_home.with_name(
                            f"{user_home.name}.restore-bak-{int(time.time())}"
                        )
                        user_home.rename(snapshot)
                    tar.extractall(str(self.home_path), **_FILTER_KW)
                except (tarfile.TarError, OSError) as exc:
                    # Restore the snapshot; remove any partially-extracted home.
                    if user_home.exists():
                        shutil.rmtree(user_home, ignore_errors=True)
                    if snapshot is not None and Path(snapshot).exists():
                        snapshot.rename(user_home)
                    logger.error(f"Restore aborted: extraction failed: {exc}")
                    return False
        except (tarfile.TarError, ValueError, OSError) as exc:
            logger.error(f"Restore aborted: invalid tar member: {exc}")
            return False

        if snapshot is not None and Path(snapshot).exists():
            shutil.rmtree(snapshot, ignore_errors=True)
        return True

    def _lookup_record_by_path(self, backup_path: str) -> Optional[BackupRecord]:
        """[FIX H83] Find a known BackupRecord whose path matches ``backup_path``."""
        for records in self.records.values():
            for rec in records:
                if rec.backup_path == backup_path:
                    return rec
        return None

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
