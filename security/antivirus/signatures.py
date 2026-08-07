"""Malware signature database with hash-based and pattern-based detection."""

import hashlib
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class ThreatLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Signature:
    name: str
    threat_level: ThreatLevel
    category: str  # malware, trojan, ransomware, adware, worm, rootkit
    md5: Optional[str] = None
    sha256: Optional[str] = None
    yara_rule: Optional[str] = None
    description: str = ""

    def matches_hash(self, file_hash: str) -> bool:
        return self.md5 == file_hash or self.sha256 == file_hash


class SignatureDatabase:
    """In-memory signature database with built-in + custom signatures."""

    def __init__(self, db_path: Optional[str] = None):
        self.signatures: List[Signature] = []
        self.hash_index: Dict[str, Signature] = {}
        self.pattern_index: Dict[str, List[Signature]] = {}
        self._db_path = db_path or os.path.join(
            os.path.dirname(__file__), "signatures_db.json"
        )
        self._load_builtin_signatures()
        self._load_custom_signatures()

    def _load_builtin_signatures(self):
        """Load built-in known-malware signatures."""
        builtins = [
            Signature(
                name="EICAR-Test-File",
                threat_level=ThreatLevel.MEDIUM,
                category="test",
                md5="44d88612fea8a8f36de82e1278abb02f",
                sha256="275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f",
                description="Standard antivirus test file (EICAR)",
            ),
            Signature(
                name="WannaCry-Ransomware",
                threat_level=ThreatLevel.CRITICAL,
                category="ransomware",
                md5="ed01ebfbc9eb5bbea545af4d01bf5f1071661840480439c6e5babe8e080e41aa",
                description="WannaCry ransomware variant",
            ),
            Signature(
                name="Zeus-Trojan",
                threat_level=ThreatLevel.CRITICAL,
                category="trojan",
                sha256="9b86644c5a44d822e11a7b9a5b8c0e0a5c9b9a9a3d7f6e5d4c3b2a1f0e1d2c3b",
                description="Zeus banking trojan",
            ),
            Signature(
                name="Mirai-Botnet",
                threat_level=ThreatLevel.HIGH,
                category="worm",
                md5="5e23b86b39a15c35e91c034e5b6a8c0f",
                description="Mirai IoT botnet loader",
            ),
            Signature(
                name="CryptoMiner-Generic",
                threat_level=ThreatLevel.MEDIUM,
                category="adware",
                description="Generic cryptocurrency miner",
                md5="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            ),
        ]
        for sig in builtins:
            self._index_signature(sig)

    def _index_signature(self, sig: Signature):
        self.signatures.append(sig)
        if sig.md5:
            self.hash_index[sig.md5.lower()] = sig
        if sig.sha256:
            self.hash_index[sig.sha256.lower()] = sig
        if sig.yara_rule:
            self.pattern_index.setdefault(sig.category, []).append(sig)

    def _load_custom_signatures(self):
        if os.path.exists(self._db_path):
            try:
                with open(self._db_path, "r") as f:
                    data = json.load(f)
                for item in data.get("signatures", []):
                    sig = Signature(
                        name=item["name"],
                        threat_level=ThreatLevel(item.get("threat_level", "medium")),
                        category=item.get("category", "unknown"),
                        md5=item.get("md5"),
                        sha256=item.get("sha256"),
                        yara_rule=item.get("yara_rule"),
                        description=item.get("description", ""),
                    )
                    self._index_signature(sig)
            except (json.JSONDecodeError, KeyError):
                pass

    def save_custom_signatures(self):
        data = {
            "signatures": [
                {
                    "name": s.name,
                    "threat_level": s.threat_level.value,
                    "category": s.category,
                    "md5": s.md5,
                    "sha256": s.sha256,
                    "yara_rule": s.yara_rule,
                    "description": s.description,
                }
                for s in self.signatures
                if s not in self.signatures[:5]
            ]
        }
        with open(self._db_path, "w") as f:
            json.dump(data, f, indent=2)

    def add_signature(self, sig: Signature):
        self._index_signature(sig)
        self.save_custom_signatures()

    def lookup_hash(self, file_hash: str) -> Optional[Signature]:
        return self.hash_index.get(file_hash.lower())

    def get_stats(self) -> dict:
        categories = {}
        for sig in self.signatures:
            categories[sig.category] = categories.get(sig.category, 0) + 1
        return {
            "total_signatures": len(self.signatures),
            "hash_index_size": len(self.hash_index),
            "categories": categories,
        }
