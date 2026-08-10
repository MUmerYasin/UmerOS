"""
UMEROS Cloud Authentication
===========================
Credential management for quantum cloud providers.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


_ENV_KEY_MAP = {
    "ibm": "UMEROS_IBM_TOKEN",
    "ionq": "UMEROS_IONQ_API_KEY",
    "braket": "UMEROS_BRAKET_ACCESS_KEY",
    "rigetti": "UMEROS_RIGETTI_API_KEY",
}


@dataclass
class AuthCredentials:
    """Credentials for a single quantum cloud provider."""

    token: Optional[str] = None
    api_key: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
    provider: str = "unknown"
    endpoint: str = ""

    @property
    def is_valid(self) -> bool:
        """Return True if at least one auth secret is present and not expired."""
        has_secret = any(
            getattr(self, attr) for attr in ("token", "api_key", "access_token")
        )
        return has_secret and not self.is_expired

    @property
    def is_expired(self) -> bool:
        """Return True if the credentials have an expiry in the past."""
        if self.expires_at is None:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) > exp
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> dict:
        """Serialize credentials to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> AuthCredentials:
        """Deserialize credentials from a dictionary."""
        return cls(
            token=d.get("token"),
            api_key=d.get("api_key"),
            access_token=d.get("access_token"),
            refresh_token=d.get("refresh_token"),
            expires_at=d.get("expires_at"),
            provider=d.get("provider", "unknown"),
            endpoint=d.get("endpoint", ""),
        )

    def __repr__(self) -> str:
        provider = self.provider
        has_token = bool(self.token)
        has_key = bool(self.api_key)
        expired = self.is_expired
        return (
            f"AuthCredentials(provider={provider!r}, has_token={has_token}, "
            f"has_api_key={has_key}, expired={expired})"
        )


class AuthManager:
    """Manages authentication credentials for multiple quantum cloud providers."""

    def __init__(self) -> None:
        self._credentials: Dict[str, AuthCredentials] = {}

    def set_credentials(self, provider: str, credentials: AuthCredentials) -> None:
        """Store credentials for a provider."""
        key = provider.lower()
        credentials.provider = key
        self._credentials[key] = credentials

    def get_credentials(self, provider: str) -> Optional[AuthCredentials]:
        """Retrieve credentials for a provider, or None if absent."""
        creds = self._credentials.get(provider.lower())
        if creds is not None and creds.is_expired:
            self._token_refresh(provider)
            creds = self._credentials.get(provider.lower())
        return creds

    def load_from_env(self, provider: str) -> Optional[AuthCredentials]:
        """Load credentials from environment variables for *provider*.

        Recognised variables per provider:
          - ibm:      ``UMEROS_IBM_TOKEN``
          - ionq:      ``UMEROS_IONQ_API_KEY``
          - braket:    ``UMEROS_BRAKET_ACCESS_KEY``
          - rigetti:   ``UMEROS_RIGETTI_API_KEY``
        """
        key = provider.lower()
        env_var = _ENV_KEY_MAP.get(key)
        if env_var is None:
            raise ValueError(
                f"Unknown provider {provider!r}. "
                f"Known providers: {list(_ENV_KEY_MAP.keys())}"
            )
        value = os.environ.get(env_var)
        if not value:
            return None
        creds = AuthCredentials(api_key=value, provider=key)
        self.set_credentials(key, creds)
        return creds

    def load_from_file(self, provider: str, filepath: str) -> AuthCredentials:
        """Load credentials from a JSON file.

        Raises FileNotFoundError if the file does not exist and
        ValueError if the JSON is malformed.
        """
        path = Path(filepath)
        if not path.is_file():
            raise FileNotFoundError(f"Credentials file not found: {filepath}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {filepath}: {exc}") from exc
        creds = AuthCredentials.from_dict(data)
        key = provider.lower()
        creds.provider = key
        self.set_credentials(key, creds)
        return creds

    def save_to_file(self, provider: str, filepath: str) -> None:
        """Save credentials for *provider* to a JSON file."""
        creds = self.get_credentials(provider)
        if creds is None:
            raise KeyError(f"No credentials stored for provider {provider!r}")
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(creds.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def clear(self, provider: Optional[str] = None) -> None:
        """Clear stored credentials.

        If *provider* is given, only that provider's credentials are removed.
        Otherwise all credentials are cleared.
        """
        if provider is None:
            self._credentials.clear()
        else:
            self._credentials.pop(provider.lower(), None)

    def list_providers(self) -> list[str]:
        """Return a list of provider names that have stored credentials."""
        return sorted(self._credentials.keys())

    def _token_refresh(self, provider: str) -> None:
        """Hook for automatic token refresh. Override in subclasses or
        register a callback to implement provider-specific refresh logic.
        """
        pass

    def __repr__(self) -> str:
        providers = self.list_providers()
        return f"AuthManager(providers={providers!r})"
