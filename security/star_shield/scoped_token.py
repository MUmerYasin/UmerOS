"""Scoped Ephemeral Capability Tokens for UmerOS Star Shield.

Time-limited HMAC-signed tokens granting access to exactly one
file or socket, replacing broad permissions.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import secrets
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ScopedToken:
    """An ephemeral capability token."""
    token_id: str
    resource: str  # file path or socket address
    resource_type: str  # "file" or "socket"
    issued_at: float
    expires_at: float
    issuer_node: str
    signature: str = ""

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ScopedToken":
        return cls(**d)


class ScopedTokenGate:
    """Issues and validates scoped ephemeral tokens."""

    def __init__(self, secret_key: Optional[str] = None, default_ttl: float = 60.0) -> None:
        self.secret_key = secret_key or secrets.token_hex(32)
        self.default_ttl = default_ttl
        self._issued_tokens: dict[str, ScopedToken] = {}

    def issue(self, resource: str, resource_type: str = "file", node_id: str = "local", ttl: Optional[float] = None) -> ScopedToken:
        """Issue a new scoped token."""
        ttl = ttl or self.default_ttl
        token = ScopedToken(
            token_id=secrets.token_urlsafe(16),
            resource=resource,
            resource_type=resource_type,
            issued_at=time.time(),
            expires_at=time.time() + ttl,
            issuer_node=node_id,
        )
        # Sign the token
        payload = f"{token.token_id}:{token.resource}:{token.resource_type}:{token.expires_at}:{token.issuer_node}"
        token.signature = hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        self._issued_tokens[token.token_id] = token
        return token

    def validate(self, token: ScopedToken) -> bool:
        """Validate a token's signature and expiration."""
        if token.is_expired:
            return False
        if token.token_id not in self._issued_tokens:
            return False
        stored = self._issued_tokens[token.token_id]
        if stored.signature != token.signature:
            return False
        # Verify signature
        payload = f"{token.token_id}:{token.resource}:{token.resource_type}:{token.expires_at}:{token.issuer_node}"
        expected = hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, token.signature)

    def revoke(self, token_id: str) -> bool:
        """Revoke a token."""
        if token_id in self._issued_tokens:
            del self._issued_tokens[token_id]
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove expired tokens. Returns count removed."""
        expired = [tid for tid, t in self._issued_tokens.items() if t.is_expired]
        for tid in expired:
            del self._issued_tokens[tid]
        return len(expired)

    @property
    def active_count(self) -> int:
        return len(self._issued_tokens)