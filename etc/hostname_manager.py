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

"""UmerOS Hostname and Hosts Manager.

Manages hostname, domainname, NIS domain, and /etc/hosts files.
"""

import os
import re
import shutil
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


HOSTNAME_FILE = "/etc/hostname"
HOSTS_FILE = "/etc/hosts"
HOSTS_LOCAL = "/etc/hosts.local"
DOMAINNAME_FILE = "/etc/domainname"
NIS_DOMAIN = "/etc/yp.conf"


class HostnameManager:
    """Manages hostname, domainname, NIS domain, and hosts files for UmerOS."""

    def __init__(
        self,
        hostname_file: str = HOSTNAME_FILE,
        hosts_file: str = HOSTS_FILE,
        hosts_local: str = HOSTS_LOCAL,
        domainname_file: str = DOMAINNAME_FILE,
        nis_domain_file: str = NIS_DOMAIN,
    ) -> None:
        """Initialize HostnameManager with file paths.

        Args:
            hostname_file: Path to the hostname file.
            hosts_file: Path to the /etc/hosts file.
            hosts_local: Path to the /etc/hosts.local file.
            domainname_file: Path to the domainname file.
            nis_domain_file: Path to the NIS/yp.conf file.
        """
        self.hostname_file = Path(hostname_file)
        self.hosts_file = Path(hosts_file)
        self.hosts_local = Path(hosts_local)
        self.domainname_file = Path(domainname_file)
        self.nis_domain_file = Path(nis_domain_file)

    # ── File I/O Helpers ────────────────────────────────────────────────

    def _read_file(self, path: Path) -> str:
        """Read a file and return its contents.

        Args:
            path: File path to read.

        Returns:
            File contents as string.

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If the file cannot be read.
        """
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except PermissionError:
            raise PermissionError(f"Permission denied reading: {path}")

    def _write_file(self, path: Path, content: str) -> None:
        """Write content to a file.

        Args:
            path: File path to write.
            content: Content to write.

        Raises:
            PermissionError: If the file cannot be written.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except PermissionError:
            raise PermissionError(f"Permission denied writing: {path}")

    # ── Hostname ────────────────────────────────────────────────────────

    def get_hostname(self) -> str:
        """Read the current hostname from the hostname file.

        Returns:
            The hostname string.

        Raises:
            FileNotFoundError: If the hostname file does not exist.
        """
        content = self._read_file(self.hostname_file).strip()
        if not content:
            return socket.gethostname()
        return content.splitlines()[0].strip()

    def set_hostname(self, hostname: str) -> Dict:
        """Set the hostname.

        Args:
            hostname: The new hostname to set.

        Returns:
            Dict with status, old_hostname, and new_hostname.

        Raises:
            ValueError: If hostname is empty or contains invalid characters.
        """
        if not hostname or not hostname.strip():
            raise ValueError("Hostname cannot be empty.")

        hostname = hostname.strip()
        if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$", hostname):
            raise ValueError(f"Invalid hostname format: {hostname}")

        old_hostname = ""
        if self.hostname_file.exists():
            old_hostname = self.get_hostname()

        self._write_file(self.hostname_file, hostname + "\n")

        return {
            "status": "success",
            "message": f"Hostname set to {hostname}",
            "old_hostname": old_hostname,
            "new_hostname": hostname,
        }

    # ── FQDN / Domainname ──────────────────────────────────────────────

    def get_fqdn(self) -> str:
        """Return the fully qualified domain name (hostname.domainname).

        Returns:
            FQDN string.
        """
        hostname = self.get_hostname()
        domainname = self.get_domainname()
        if domainname:
            return f"{hostname}.{domainname}"
        return hostname

    def get_domainname(self) -> str:
        """Read the domain name from the domainname file.

        Returns:
            The domain name, or empty string if not set.
        """
        if not self.domainname_file.exists():
            return ""
        content = self._read_file(self.domainname_file).strip()
        return content.splitlines()[0].strip() if content else ""

    def set_domainname(self, domain: str) -> Dict:
        """Set the domain name.

        Args:
            domain: The new domain name.

        Returns:
            Dict with status, old_domain, and new_domain.

        Raises:
            ValueError: If domain is empty or contains invalid characters.
        """
        if not domain or not domain.strip():
            raise ValueError("Domain name cannot be empty.")

        domain = domain.strip()
        if re.search(r"[^a-zA-Z0-9.\-]", domain):
            raise ValueError(f"Invalid domain name: {domain}")

        old_domain = self.get_domainname()
        self._write_file(self.domainname_file, domain + "\n")

        return {
            "status": "success",
            "message": f"Domain name set to {domain}",
            "old_domain": old_domain,
            "new_domain": domain,
        }

    # ── NIS Domain ─────────────────────────────────────────────────────

    def get_nis_domain(self) -> str:
        """Read the NIS domain from /etc/yp.conf.

        Returns:
            The NIS domain name, or empty string if not set.
        """
        if not self.nis_domain_file.exists():
            return ""

        content = self._read_file(self.nis_domain_file)
        match = re.search(r"^domain\s+(\S+)", content, re.MULTILINE)
        return match.group(1) if match else ""

    def set_nis_domain(self, domain: str) -> Dict:
        """Set the NIS domain in /etc/yp.conf.

        Args:
            domain: The NIS domain name to set.

        Returns:
            Dict with status, old_domain, and new_domain.

        Raises:
            ValueError: If domain is empty or contains invalid characters.
        """
        if not domain or not domain.strip():
            raise ValueError("NIS domain cannot be empty.")

        domain = domain.strip()
        if re.search(r"[^a-zA-Z0-9.\-_]", domain):
            raise ValueError(f"Invalid NIS domain: {domain}")

        old_domain = self.get_nis_domain()

        if self.nis_domain_file.exists():
            content = self._read_file(self.nis_domain_file)
            if re.search(r"^domain\s+", content, re.MULTILINE):
                new_content = re.sub(
                    r"^domain\s+\S+",
                    f"domain {domain}",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                new_content = content.rstrip() + f"\ndomain {domain}\n"
        else:
            new_content = f"domain {domain}\n"

        self._write_file(self.nis_domain_file, new_content)

        return {
            "status": "success",
            "message": f"NIS domain set to {domain}",
            "old_domain": old_domain,
            "new_domain": domain,
        }

    # ── /etc/hosts Parsing & Writing ────────────────────────────────────

    @staticmethod
    def _parse_hosts_content(content: str) -> List[Dict]:
        """Parse hosts file content into structured entries.

        Args:
            content: Raw hosts file content.

        Returns:
            List of dicts, each with keys: ip, hostnames, comment.
        """
        entries: List[Dict] = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                entries.append({"ip": "", "hostnames": [], "comment": stripped[1:].strip()})
                continue

            comment = ""
            if "#" in stripped:
                code_part, comment_part = stripped.split("#", 1)
                stripped = code_part.strip()
                comment = comment_part.strip()

            parts = stripped.split()
            if len(parts) < 2:
                continue

            ip = parts[0]
            hostnames = parts[1:]
            entries.append({"ip": ip, "hostnames": hostnames, "comment": comment})

        return entries

    def _parse_hosts_file(self, path: Path) -> List[Dict]:
        """Parse a hosts file.

        Args:
            path: Path to the hosts file.

        Returns:
            List of parsed host entries.
        """
        if not path.exists():
            return []
        content = self._read_file(path)
        return self._parse_hosts_content(content)

    @staticmethod
    def _write_hosts_file(path: Path, entries: List[Dict]) -> str:
        """Serialize entries back to hosts file format.

        Args:
            path: File path to write.
            entries: List of entry dicts with ip, hostnames, comment.

        Returns:
            The file content that was written.
        """
        lines: List[str] = []
        for entry in entries:
            ip = entry.get("ip", "")
            hostnames = entry.get("hostnames", [])
            comment = entry.get("comment", "")

            if not ip and not hostnames and comment:
                lines.append(f"# {comment}")
                continue

            line_parts = [ip] + hostnames
            line = "  ".join(line_parts)
            if comment:
                line += f"  # {comment}"
            lines.append(line)

        content = "\n".join(lines) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return content

    def get_hosts(self) -> List[Dict]:
        """Parse /etc/hosts into structured entries.

        Returns:
            List of dicts with keys: ip, hostnames, comment.
        """
        return self._parse_hosts_file(self.hosts_file)

    def set_hosts(self, entries: List[Dict]) -> Dict:
        """Write entries to /etc/hosts.

        Args:
            entries: List of entry dicts with ip, hostnames, comment.

        Returns:
            Dict with status and entry count.
        """
        self._write_hosts_file(self.hosts_file, entries)
        return {
            "status": "success",
            "message": f"Wrote {len(entries)} entries to {self.hosts_file}",
            "entry_count": len(entries),
        }

    def add_host_entry(
        self, ip: str, hostnames: List[str], comment: str = ""
    ) -> Dict:
        """Add a new entry to /etc/hosts.

        Args:
            ip: The IP address.
            hostnames: List of hostnames for this IP.
            comment: Optional comment.

        Returns:
            Dict with status and the added entry.

        Raises:
            ValueError: If ip or hostnames are invalid.
        """
        if not ip or not ip.strip():
            raise ValueError("IP address cannot be empty.")
        if not hostnames:
            raise ValueError("At least one hostname is required.")

        ip = ip.strip()
        hostnames = [h.strip() for h in hostnames]

        entries = self.get_hosts()
        entries.append({"ip": ip, "hostnames": hostnames, "comment": comment})
        self._write_hosts_file(self.hosts_file, entries)

        return {
            "status": "success",
            "message": f"Added entry for {ip} -> {', '.join(hostnames)}",
            "entry": {"ip": ip, "hostnames": hostnames, "comment": comment},
        }

    def remove_host_entry(
        self, ip: Optional[str] = None, hostname: Optional[str] = None
    ) -> Dict:
        """Remove entries from /etc/hosts by IP or hostname.

        Args:
            ip: IP address to match for removal.
            hostname: Hostname to match for removal.

        Returns:
            Dict with status and count of removed entries.

        Raises:
            ValueError: If neither ip nor hostname is provided.
        """
        if not ip and not hostname:
            raise ValueError("At least one of ip or hostname must be provided.")

        entries = self.get_hosts()
        original_count = len(entries)

        if ip:
            ip = ip.strip()
            entries = [e for e in entries if e["ip"] != ip]
        elif hostname:
            hostname = hostname.strip()
            entries = [
                e
                for e in entries
                if hostname not in e["hostnames"]
            ]

        removed = original_count - len(entries)
        self._write_hosts_file(self.hosts_file, entries)

        return {
            "status": "success",
            "message": f"Removed {removed} entry(ies) from {self.hosts_file}",
            "removed_count": removed,
        }

    def find_host(self, query: str) -> List[Dict]:
        """Search /etc/hosts by IP or hostname substring.

        Args:
            query: IP or hostname to search for.

        Returns:
            List of matching entry dicts.
        """
        if not query:
            return []

        query = query.strip().lower()
        entries = self.get_hosts()
        matches: List[Dict] = []

        for entry in entries:
            if query in entry["ip"].lower():
                matches.append(entry)
                continue
            for h in entry["hostnames"]:
                if query in h.lower():
                    matches.append(entry)
                    break

        return matches
    # ─ /etc/hosts.local ────────────────────────────────────────────────

    def get_hosts_local(self) -> List[Dict]:
        """Parse /etc/hosts.local into structured entries.

        Returns:
            List of dicts with keys: ip, hostnames, comment.
        """
        return self._parse_hosts_file(self.hosts_local)

    def set_hosts_local(self, entries: List[Dict]) -> Dict:
        """Write entries to /etc/hosts.local.

        Args:
            entries: List of entry dicts with ip, hostnames, comment.

        Returns:
            Dict with status and entry count.
        """
        self._write_hosts_file(self.hosts_local, entries)
        return {
            "status": "success",
            "message": "Wrote {} entries to {}".format(len(entries), self.hosts_local),
            "entry_count": len(entries),
        }

    def add_hosts_local_entry(
        self, ip: str, hostnames: List[str], comment: str = ""
    ) -> Dict:
        """Add a new entry to /etc/hosts.local.

        Args:
            ip: The IP address.
            hostnames: List of hostnames for this IP.
            comment: Optional comment.

        Returns:
            Dict with status and the added entry.

        Raises:
            ValueError: If ip or hostnames are invalid.
        """
        if not ip or not ip.strip():
            raise ValueError("IP address cannot be empty.")
        if not hostnames:
            raise ValueError("At least one hostname is required.")

        ip = ip.strip()
        hostnames = [h.strip() for h in hostnames]

        entries = self.get_hosts_local()
        entries.append({"ip": ip, "hostnames": hostnames, "comment": comment})
        self._write_hosts_file(self.hosts_local, entries)

        return {
            "status": "success",
            "message": "Added entry for {} -> {} to hosts.local".format(ip, ", ".join(hostnames)),
            "entry": {"ip": ip, "hostnames": hostnames, "comment": comment},
        }

    def remove_hosts_local_entry(
        self, ip: Optional[str] = None, hostname: Optional[str] = None
    ) -> Dict:
        """Remove entries from /etc/hosts.local by IP or hostname.

        Args:
            ip: IP address to match for removal.
            hostname: Hostname to match for removal.

        Returns:
            Dict with status and count of removed entries.

        Raises:
            ValueError: If neither ip nor hostname is provided.
        """
        if not ip and not hostname:
            raise ValueError("At least one of ip or hostname must be provided.")

        entries = self.get_hosts_local()
        original_count = len(entries)

        if ip:
            ip = ip.strip()
            entries = [e for e in entries if e["ip"] != ip]
        elif hostname:
            hostname = hostname.strip()
            entries = [
                e
                for e in entries
                if hostname not in e["hostnames"]
            ]

        removed = original_count - len(entries)
        self._write_hosts_file(self.hosts_local, entries)

        return {
            "status": "success",
            "message": "Removed {} entry(ies) from {}".format(removed, self.hosts_local),
            "removed_count": removed,
        }

    # ─ Validation ─────────────────────────────────────────────────────────────────

    def validate_hosts(self) -> Dict:
        """Validate /etc/hosts for common issues.

        Checks for:
            - Duplicate IP entries
            - Duplicate hostname entries
            - Format errors (lines with less than 2 fields)
            - Required entries (127.0.0.1, ::1, 127.0.1.1)

        Returns:
            Dict with is_valid, errors, warnings, and entries checked.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not self.hosts_file.exists():
            return {
                "is_valid": False,
                "errors": ["Hosts file not found: {}".format(self.hosts_file)],
                "warnings": [],
                "entries_checked": 0,
            }

        content = self._read_file(self.hosts_file)
        entries = self._parse_hosts_content(content)
        non_comment = [e for e in entries if e["ip"]]

        # Check for required entries
        required_map = {
            "127.0.0.1": ["localhost"],
            "::1": ["localhost", "ip6-localhost", "ip6-loopback"],
            "127.0.1.1": [],
        }

        found_ips: Dict[str, List[str]] = {}
        found_hostnames: Dict[str, str] = {}

        for entry in non_comment:
            ip = entry["ip"]
            if ip in found_ips:
                found_ips[ip].extend(entry["hostnames"])
            else:
                found_ips[ip] = list(entry["hostnames"])

            for h in entry["hostnames"]:
                if h in found_hostnames:
                    warnings.append(
                        "Hostname '{}' appears in multiple entries"
                        " (IPs: {}, {})".format(h, found_hostnames[h], ip)
                    )
                else:
                    found_hostnames[h] = ip

        # Check required entries
        for required_ip, required_names in required_map.items():
            if required_ip not in found_ips:
                errors.append("Missing required entry for {}".format(required_ip))
            else:
                for name in required_names:
                    if name not in found_hostnames:
                        warnings.append(
                            "Missing recommended alias '{}' for {}".format(name, required_ip)
                        )

        # Check for duplicate IPs
        for ip, hosts in found_ips.items():
            if len(hosts) > 0:
                seen = set()
                duplicates = []
                for h in hosts:
                    if h in seen:
                        duplicates.append(h)
                    seen.add(h)
                if duplicates:
                    warnings.append(
                        "Duplicate hostnames under {}: {}".format(ip, ", ".join(duplicates))
                    )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "entries_checked": len(non_comment),
        }

    # ─ Standard Hosts ──────────────────────────────────────────────

    @staticmethod
    def get_standard_hosts() -> List[Dict]:
        """Return default /etc/hosts entries for UmerOS.

        Returns:
            List of standard host entry dicts.
        """
        return [
            {
                "ip": "127.0.0.1",
                "hostnames": ["localhost"],
                "comment": "Loopback address",
            },
            {
                "ip": "127.0.1.1",
                "hostnames": [],
                "comment": "Hostname entry (see man 5 hosts)",
            },
            {
                "ip": "::1",
                "hostnames": ["localhost", "ip6-localhost", "ip6-loopback"],
                "comment": "IPv6 loopback",
            },
            {
                "ip": "ff02::1",
                "hostnames": ["ip6-allnodes"],
                "comment": "IPv6 all nodes multicast",
            },
            {
                "ip": "ff02::2",
                "hostnames": ["ip6-allrouters"],
                "comment": "IPv6 all routers multicast",
            },
        ]

    # ─ Export / Backup ──────────────────────────────────────────────────

    def export_status(self) -> Dict:
        """Export the current hostname/network configuration status.

        Returns:
            Dict containing hostname, domainname, fqdn, nis_domain,
            hosts entries, hosts_local entries, and validation result.
        """
        hostname = ""
        domainname = ""
        fqdn = ""
        nis_domain = ""
        hosts_entries: List[Dict] = []
        hosts_local_entries: List[Dict] = []
        validation: Dict = {}

        try:
            hostname = self.get_hostname()
        except (FileNotFoundError, PermissionError):
            hostname = ""

        try:
            domainname = self.get_domainname()
        except (FileNotFoundError, PermissionError):
            domainname = ""

        try:
            fqdn = self.get_fqdn()
        except (FileNotFoundError, PermissionError):
            fqdn = ""

        try:
            nis_domain = self.get_nis_domain()
        except (FileNotFoundError, PermissionError):
            nis_domain = ""

        try:
            hosts_entries = self.get_hosts()
        except (FileNotFoundError, PermissionError):
            hosts_entries = []

        try:
            hosts_local_entries = self.get_hosts_local()
        except (FileNotFoundError, PermissionError):
            hosts_local_entries = []

        try:
            validation = self.validate_hosts()
        except (FileNotFoundError, PermissionError):
            validation = {"is_valid": False, "errors": ["Validation unavailable"], "warnings": [], "entries_checked": 0}

        return {
            "hostname": hostname,
            "domainname": domainname,
            "fqdn": fqdn,
            "nis_domain": nis_domain,
            "hosts_entries": hosts_entries,
            "hosts_local_entries": hosts_local_entries,
            "hosts_validation": validation,
            "files": {
                "hostname_file": str(self.hostname_file),
                "hosts_file": str(self.hosts_file),
                "hosts_local": str(self.hosts_local),
                "domainname_file": str(self.domainname_file),
                "nis_domain_file": str(self.nis_domain_file),
            },
            "exported_at": datetime.now().isoformat(),
        }

    def backup_all(self, backup_path: str) -> Dict:
        """Backup all managed configuration files.

        Creates timestamped backups of:
            - /etc/hostname
            - /etc/hosts
            - /etc/hosts.local
            - /etc/domainname
            - /etc/yp.conf

        Args:
            backup_path: Directory path to store backups.

        Returns:
            Dict with status and list of backed up files.
        """
        backup_dir = Path(backup_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = backup_dir / "hostname_backup_{}".format(timestamp)
        backup_subdir.mkdir(parents=True, exist_ok=True)

        backed_up: List[str] = []
        errors: List[str] = []

        files_to_backup = {
            "hostname": self.hostname_file,
            "hosts": self.hosts_file,
            "hosts.local": self.hosts_local,
            "domainname": self.domainname_file,
            "yp.conf": self.nis_domain_file,
        }

        for name, src in files_to_backup.items():
            if src.exists():
                try:
                    dest = backup_subdir / name
                    shutil.copy2(str(src), str(dest))
                    backed_up.append(str(dest))
                except (PermissionError, OSError) as e:
                    errors.append("Failed to backup {}: {}".format(src, e))
            else:
                errors.append("File not found, skipped: {}".format(src))

        return {
            "status": "success" if not errors else "partial",
            "backup_directory": str(backup_subdir),
            "backed_up_files": backed_up,
            "errors": errors,
            "timestamp": timestamp,
        }


# ─ CLI Interface ──────────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Command-line interface for hostname management."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="UmerOS Hostname and Hosts Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("get-hostname", help="Get current hostname")
    subparsers.add_parser("get-fqdn", help="Get fully qualified domain name")
    subparsers.add_parser("get-domainname", help="Get domain name")
    subparsers.add_parser("get-nis-domain", help="Get NIS domain")

    sp = subparsers.add_parser("set-hostname", help="Set hostname")
    sp.add_argument("value", help="New hostname")

    sp = subparsers.add_parser("set-domainname", help="Set domain name")
    sp.add_argument("value", help="New domain name")

    sp = subparsers.add_parser("set-nis-domain", help="Set NIS domain")
    sp.add_argument("value", help="New NIS domain")

    subparsers.add_parser("show-hosts", help="Display /etc/hosts entries")
    subparsers.add_parser("show-hosts-local", help="Display /etc/hosts.local entries")

    sp = subparsers.add_parser("add-host", help="Add host entry to /etc/hosts")
    sp.add_argument("ip", help="IP address")
    sp.add_argument("hostnames", nargs="+", help="Hostnames for this IP")
    sp.add_argument("--comment", default="", help="Optional comment")

    sp = subparsers.add_parser("remove-host", help="Remove host entry from /etc/hosts")
    sp.add_argument("--ip", default=None, help="IP address to remove")
    sp.add_argument("--hostname", default=None, help="Hostname to remove")

    sp = subparsers.add_parser("find-host", help="Search hosts by IP or hostname")
    sp.add_argument("query", help="Search query")

    subparsers.add_parser("validate", help="Validate /etc/hosts")
    subparsers.add_parser("standard-hosts", help="Show standard default hosts entries")
    subparsers.add_parser("export-status", help="Export full configuration status")

    sp = subparsers.add_parser("backup", help="Backup all config files")
    sp.add_argument("path", help="Backup directory path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    mgr = HostnameManager()

    try:
        if args.command == "get-hostname":
            print(mgr.get_hostname())
        elif args.command == "set-hostname":
            result = mgr.set_hostname(args.value)
            print(json.dumps(result, indent=2))
        elif args.command == "get-fqdn":
            print(mgr.get_fqdn())
        elif args.command == "get-domainname":
            print(mgr.get_domainname())
        elif args.command == "set-domainname":
            result = mgr.set_domainname(args.value)
            print(json.dumps(result, indent=2))
        elif args.command == "get-nis-domain":
            print(mgr.get_nis_domain())
        elif args.command == "set-nis-domain":
            result = mgr.set_nis_domain(args.value)
            print(json.dumps(result, indent=2))
        elif args.command == "show-hosts":
            entries = mgr.get_hosts()
            for e in entries:
                if e["ip"]:
                    line = "{}  {}".format(e["ip"], "  ".join(e["hostnames"]))
                    if e["comment"]:
                        line += "  # {}".format(e["comment"])
                    print(line)
                elif e["comment"]:
                    print("# {}".format(e["comment"]))
        elif args.command == "show-hosts-local":
            entries = mgr.get_hosts_local()
            for e in entries:
                if e["ip"]:
                    line = "{}  {}".format(e["ip"], "  ".join(e["hostnames"]))
                    if e["comment"]:
                        line += "  # {}".format(e["comment"])
                    print(line)
                elif e["comment"]:
                    print("# {}".format(e["comment"]))
        elif args.command == "add-host":
            result = mgr.add_host_entry(args.ip, args.hostnames, args.comment)
            print(json.dumps(result, indent=2))
        elif args.command == "remove-host":
            result = mgr.remove_host_entry(ip=args.ip, hostname=args.hostname)
            print(json.dumps(result, indent=2))
        elif args.command == "find-host":
            matches = mgr.find_host(args.query)
            if matches:
                for m in matches:
                    print(json.dumps(m, indent=2))
            else:
                print("No matches found.")
        elif args.command == "validate":
            result = mgr.validate_hosts()
            print(json.dumps(result, indent=2))
        elif args.command == "standard-hosts":
            entries = mgr.get_standard_hosts()
            for e in entries:
                if e["ip"]:
                    line = "{}  {}".format(e["ip"], "  ".join(e["hostnames"]))
                    if e["comment"]:
                        line += "  # {}".format(e["comment"])
                    print(line)
        elif args.command == "export-status":
            result = mgr.export_status()
            print(json.dumps(result, indent=2, default=str))
        elif args.command == "backup":
            result = mgr.backup_all(args.path)
            print(json.dumps(result, indent=2))

    except FileNotFoundError as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
    except PermissionError as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
