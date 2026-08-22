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
UmerOS ~/.ssh/ Key Manager
Manages SSH keys: id_rsa, id_rsa.pub, authorized_keys, known_hosts, config.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import hashlib
import secrets


@dataclass
class SSHKey:
    name: str
    private_key: str = ""
    public_key: str = ""
    key_type: str = "rsa"
    bits: int = 4096
    comment: str = ""

    def is_valid(self) -> bool:
        return bool(self.private_key and self.public_key)


@dataclass
class KnownHost:
    hostname: str
    key_type: str = "rsa"
    fingerprint: str = ""
    key: str = ""


class HomeSSHManager:
    KEY_TYPES = ["rsa", "ed25519", "ecdsa"]
    DEFAULT_BITS = {"rsa": 4096, "ecdsa": 521, "ed25519": 256}

    def __init__(self, home_path: str = "/home"):
        self.home_path = Path(home_path)
        self.keys: Dict[str, Dict[str, SSHKey]] = {}
        self.known_hosts: Dict[str, List[KnownHost]] = {}

    def setup_ssh(self, username: str) -> bool:
        ssh_dir = self.home_path / username / ".ssh"
        ssh_dir.mkdir(parents=True, exist_ok=True)
        try:
            ssh_dir.chmod(0o700)
        except (OSError, PermissionError):
            pass
        self.keys[username] = {}
        self.known_hosts[username] = []
        return True

    def generate_key(self, username: str, key_type: str = "rsa",
                     bits: int = 4096, comment: str = "") -> Optional[SSHKey]:
        ssh_dir = self.home_path / username / ".ssh"
        ssh_dir.mkdir(parents=True, exist_ok=True)
        pseudo_random = secrets.token_hex(bits // 8)
        fingerprint = hashlib.sha256(pseudo_random.encode()).hexdigest()
        priv = (
            f"-----BEGIN {key_type.upper()} PRIVATE KEY-----\n"
            f"Proc-Type: 4,ENCRYPTED\n"
            f"DEK-Info: AES-256-CBC,{fingerprint[:32]}\n\n"
            f"{pseudo_random}\n"
            f"-----END {key_type.upper()} PRIVATE KEY-----"
        )
        pub_comment = comment or f"{username}@UmerOS"
        pub = f"ssh-{key_type} {fingerprint[:96]} {pub_comment}"
        key = SSHKey(name=key_type, private_key=priv, public_key=pub,
                     key_type=key_type, bits=bits, comment=pub_comment)
        priv_file = ssh_dir / f"id_{key_type}"
        priv_file.write_text(priv, encoding='utf-8')
        try:
            priv_file.chmod(0o600)
        except (OSError, PermissionError):
            pass
        pub_file = ssh_dir / f"id_{key_type}.pub"
        pub_file.write_text(pub, encoding='utf-8')
        try:
            pub_file.chmod(0o644)
        except (OSError, PermissionError):
            pass
        if username not in self.keys:
            self.keys[username] = {}
        self.keys[username][key_type] = key
        return key

    def get_key(self, username: str, key_type: str = "rsa") -> Optional[SSHKey]:
        return self.keys.get(username, {}).get(key_type)

    def list_keys(self, username: str) -> List[str]:
        return list(self.keys.get(username, {}).keys())

    def add_authorized_key(self, username: str, public_key: str) -> bool:
        ssh_dir = self.home_path / username / ".ssh"
        auth_file = ssh_dir / "authorized_keys"
        existing = ""
        if auth_file.exists():
            existing = auth_file.read_text(encoding='utf-8')
        if public_key.strip() in existing:
            return False
        with open(str(auth_file), 'a', encoding='utf-8') as f:
            f.write(public_key.rstrip() + "\n")
        try:
            auth_file.chmod(0o644)
        except (OSError, PermissionError):
            pass
        return True

    def remove_authorized_key(self, username: str, public_key: str) -> bool:
        ssh_dir = self.home_path / username / ".ssh"
        auth_file = ssh_dir / "authorized_keys"
        if not auth_file.exists():
            return False
        lines = auth_file.read_text(encoding='utf-8').splitlines()
        new_lines = [l for l in lines if l.strip() != public_key.strip()]
        auth_file.write_text("\n".join(new_lines) + "\n", encoding='utf-8')
        return True

    def list_authorized_keys(self, username: str) -> List[str]:
        ssh_dir = self.home_path / username / ".ssh"
        auth_file = ssh_dir / "authorized_keys"
        if not auth_file.exists():
            return []
        return [l.strip() for l in auth_file.read_text(encoding='utf-8').splitlines()
                if l.strip() and not l.startswith('#')]

    def add_known_host(self, username: str, hostname: str,
                       key_type: str = "rsa", key: str = "") -> bool:
        ssh_dir = self.home_path / username / ".ssh"
        known_file = ssh_dir / "known_hosts"
        entry = f"{hostname} ssh-{key_type} {key}\n"
        with open(str(known_file), 'a', encoding='utf-8') as f:
            f.write(entry)
        self.known_hosts.setdefault(username, []).append(
            KnownHost(hostname=hostname, key_type=key_type, key=key))
        return True

    def remove_known_host(self, username: str, hostname: str) -> bool:
        ssh_dir = self.home_path / username / ".ssh"
        known_file = ssh_dir / "known_hosts"
        if not known_file.exists():
            return False
        lines = known_file.read_text(encoding='utf-8').splitlines()
        new_lines = [l for l in lines if not l.startswith(hostname)]
        known_file.write_text("\n".join(new_lines) + "\n", encoding='utf-8')
        return True

    def list_known_hosts(self, username: str) -> List[str]:
        ssh_dir = self.home_path / username / ".ssh"
        known_file = ssh_dir / "known_hosts"
        if not known_file.exists():
            return []
        return [l.split()[0] for l in known_file.read_text(encoding='utf-8').splitlines()
                if l.strip()]

    def write_config(self, username: str, config: str) -> bool:
        ssh_dir = self.home_path / username / ".ssh"
        ssh_dir.mkdir(parents=True, exist_ok=True)
        config_file = ssh_dir / "config"
        config_file.write_text(config, encoding='utf-8')
        try:
            config_file.chmod(0o600)
        except (OSError, PermissionError):
            pass
        return True

    def get_config(self, username: str) -> str:
        ssh_dir = self.home_path / username / ".ssh"
        config_file = ssh_dir / "config"
        if config_file.exists():
            return config_file.read_text(encoding='utf-8')
        return ""

    def get_ssh_stats(self, username: str) -> Dict:
        return {
            "keys": self.list_keys(username),
            "authorized_keys": len(self.list_authorized_keys(username)),
            "known_hosts": len(self.list_known_hosts(username)),
            "has_config": bool(self.get_config(username)),
        }
