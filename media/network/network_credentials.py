# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS /media/network - Network Credential Management
====================================================

Secure storage and management of credentials for network shares.
Uses simple file-based storage with basic obfuscation.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Media.Network.Credentials")

_CRED_DIR = Path.home() / ".config" / "umeros" / "network_credentials"


@dataclass
class NetworkCredential:
    """Stored credentials for a network share."""
    name: str
    username: str
    password: str = ""
    domain: Optional[str] = None
    key_file: Optional[str] = None
    protocol: str = "smb"
    host: str = ""

    def redacted(self) -> dict:
        return {
            "name": self.name,
            "username": self.username,
            "password": "***" if self.password else "",
            "domain": self.domain,
            "key_file": self.key_file,
            "protocol": self.protocol,
            "host": self.host,
        }


class CredentialStore:
    """File-based credential store with basic obfuscation."""

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self.store_dir = store_dir or _CRED_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, NetworkCredential] = {}
        self._load_all()

    def _cred_path(self, name: str) -> Path:
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return self.store_dir / f"{safe_name}.cred"

    def _obfuscate(self, data: str) -> str:
        """Basic base64 obfuscation (not encryption)."""
        return base64.b64encode(data.encode()).decode()

    def _deobfuscate(self, data: str) -> str:
        try:
            return base64.b64decode(data.encode()).decode()
        except Exception:
            return data

    def _load_all(self) -> None:
        for path in self.store_dir.glob("*.cred"):
            try:
                with open(path, "r") as f:
                    raw = json.load(f)
                cred = NetworkCredential(
                    name=raw["name"],
                    username=self._deobfuscate(raw.get("username", "")),
                    password=self._deobfuscate(raw.get("password", "")),
                    domain=raw.get("domain"),
                    key_file=raw.get("key_file"),
                    protocol=raw.get("protocol", "smb"),
                    host=raw.get("host", ""),
                )
                self._cache[cred.name] = cred
            except Exception as e:
                log.warning("Failed to load credential %s: %s", path, e)

    def save(self, cred: NetworkCredential) -> bool:
        """Save a credential to disk."""
        path = self._cred_path(cred.name)
        try:
            data = {
                "name": cred.name,
                "username": self._obfuscate(cred.username),
                "password": self._obfuscate(cred.password),
                "domain": cred.domain,
                "key_file": cred.key_file,
                "protocol": cred.protocol,
                "host": cred.host,
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            self._cache[cred.name] = cred
            log.info("Saved credential: %s", cred.name)
            return True
        except Exception as e:
            log.error("Failed to save credential %s: %s", cred.name, e)
            return False

    def load(self, name: str) -> Optional[NetworkCredential]:
        """Load a credential by name."""
        return self._cache.get(name)

    def delete(self, name: str) -> bool:
        """Delete a credential."""
        path = self._cred_path(name)
        try:
            if path.exists():
                path.unlink()
            self._cache.pop(name, None)
            log.info("Deleted credential: %s", name)
            return True
        except Exception as e:
            log.error("Failed to delete credential %s: %s", name, e)
            return False

    def list_credentials(self) -> List[NetworkCredential]:
        """List all stored credentials."""
        return list(self._cache.values())

    def find_by_host(self, host: str) -> List[NetworkCredential]:
        return [c for c in self._cache.values() if c.host == host]


# Convenience functions
def save_credential(cred: NetworkCredential, store_dir: Optional[Path] = None) -> bool:
    store = CredentialStore(store_dir)
    return store.save(cred)


def load_credential(name: str, store_dir: Optional[Path] = None) -> Optional[NetworkCredential]:
    store = CredentialStore(store_dir)
    return store.load(name)


def delete_credential(name: str, store_dir: Optional[Path] = None) -> bool:
    store = CredentialStore(store_dir)
    return store.delete(name)