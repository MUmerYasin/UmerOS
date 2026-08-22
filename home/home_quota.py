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
UmerOS Home Quota Manager
Tracks disk usage and quotas per user home directory.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import json


@dataclass
class UserQuota:
    username: str
    hard_limit_bytes: int = 0
    soft_limit_bytes: int = 0
    used_bytes: int = 0
    inodes_hard: int = 0
    inodes_soft: int = 0
    inodes_used: int = 0

    @property
    def usage_percent(self) -> float:
        if self.hard_limit_bytes == 0:
            return 0.0
        return (self.used_bytes / self.hard_limit_bytes) * 100

    @property
    def inode_usage_percent(self) -> float:
        if self.inodes_hard == 0:
            return 0.0
        return (self.inodes_used / self.inodes_hard) * 100

    @property
    def is_over_soft(self) -> bool:
        return self.soft_limit_bytes > 0 and self.used_bytes > self.soft_limit_bytes

    @property
    def is_over_hard(self) -> bool:
        return self.hard_limit_bytes > 0 and self.used_bytes >= self.hard_limit_bytes


class HomeQuotaManager:
    """Manages disk quotas for user home directories."""

    def __init__(self, home_path: str = "/home"):
        self.home_path = Path(home_path)
        self.quotas: Dict[str, UserQuota] = {}

    def set_quota(self, username: str, hard_bytes: int = 0,
                  soft_bytes: int = 0, hard_inodes: int = 0,
                  soft_inodes: int = 0) -> UserQuota:
        """Set quota limits for a user."""
        quota = UserQuota(
            username=username,
            hard_limit_bytes=hard_bytes,
            soft_limit_bytes=soft_bytes,
            inodes_hard=hard_inodes,
            inodes_soft=soft_inodes,
        )
        self.quotas[username] = quota
        return quota

    def get_quota(self, username: str) -> Optional[UserQuota]:
        """Get quota for a user."""
        return self.quotas.get(username)

    def scan_usage(self, username: str) -> UserQuota:
        """Scan actual disk usage for a user."""
        user_home = self.home_path / username
        quota = self.quotas.get(username, UserQuota(username=username))

        total_bytes = 0
        total_inodes = 0
        if user_home.exists():
            for f in user_home.rglob('*'):
                if f.is_file():
                    total_bytes += f.stat().st_size
                    total_inodes += 1

        quota.used_bytes = total_bytes
        quota.inodes_used = total_inodes
        self.quotas[username] = quota
        return quota

    def check_quota(self, username: str) -> Dict:
        """Check if a user is within quota."""
        quota = self.scan_usage(username)
        return {
            "username": username,
            "used_bytes": quota.used_bytes,
            "hard_limit": quota.hard_limit_bytes,
            "soft_limit": quota.soft_limit_bytes,
            "usage_percent": round(quota.usage_percent, 2),
            "is_over_soft": quota.is_over_soft,
            "is_over_hard": quota.is_over_hard,
            "inodes_used": quota.inodes_used,
            "inodes_hard": quota.inodes_hard,
            "inode_usage_percent": round(quota.inode_usage_percent, 2),
        }

    def list_quotas(self) -> List[Dict]:
        """List all user quotas."""
        results = []
        for username in self.quotas:
            results.append(self.check_quota(username))
        return results

    def remove_quota(self, username: str) -> bool:
        """Remove quota for a user."""
        if username in self.quotas:
            del self.quotas[username]
            return True
        return False

    def export_quotas(self) -> Dict:
        """Export all quotas as dict."""
        result = {}
        for username, q in self.quotas.items():
            result[username] = {
                "hard_limit_bytes": q.hard_limit_bytes,
                "soft_limit_bytes": q.soft_limit_bytes,
                "used_bytes": q.used_bytes,
                "inodes_hard": q.inodes_hard,
                "inodes_soft": q.inodes_soft,
                "inodes_used": q.inodes_used,
            }
        return result

    def format_size(self, size_bytes: int) -> str:
        """Human-readable size."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"
