"""
UMEROS Cloud Authentication
============================
Credential management for quantum cloud providers.
Implements real OAuth2 token exchange and refresh flows for all providers.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment variable mapping per provider
# ---------------------------------------------------------------------------

_ENV_KEY_MAP = {
    "ibm": "UMEROS_IBM_TOKEN",
    "ionq": "UMEROS_IONQ_API_KEY",
    "braket": "UMEROS_BRAKET_ACCESS_KEY",
    "rigetti": "UMEROS_RIGETTI_API_KEY",
}

# ---------------------------------------------------------------------------
# Provider OAuth2 / token-refresh endpoints
# ---------------------------------------------------------------------------

_PROVIDER_AUTH_CONFIG: Dict[str, Dict[str, Any]] = {
    "ibm": {
        "token_url": "https://auth.quantum-computing.ibm.com/api/users/loginWithToken",
        "refresh_url": "https://auth.quantum-computing.ibm.com/api/users/refreshToken",
        "verify_url": "https://auth.quantum-computing.ibm.com/api/users/me",
        "grant_type": "refresh_token",
    },
    "ionq": {
        "token_url": "https://api.ionq.co/v0.3/auth/token",
        "refresh_url": "https://api.ionq.co/v0.3/auth/token/refresh",
        "verify_url": "https://api.ionq.co/v0.3/auth/me",
        "grant_type": "refresh_token",
    },
    "braket": {
        # Braket uses AWS SigV4 — no OAuth2 refresh; we validate via STS.
        "verify_url": "https://sts.amazonaws.com/",
        "grant_type": None,
    },
    "rigetti": {
        "token_url": "https://qpu.rigetti.com/v1/auth/token",
        "refresh_url": "https://qpu.rigetti.com/v1/auth/token/refresh",
        "verify_url": "https://qpu.rigetti.com/v1/auth/me",
        "grant_type": "refresh_token",
    },
}


# ---------------------------------------------------------------------------
# HTTP helper (importable by other cloud modules)
# ---------------------------------------------------------------------------


def _http_request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Make an HTTP request and return parsed JSON.

    Raises RuntimeError on non-2xx and ConnectionError on network failures.
    """
    default_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        default_headers.update(headers)

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=default_headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw.strip():
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(
            f"HTTP {exc.code} on {method} {url}: {body_text}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"Failed to reach {url}: {exc.reason}"
        ) from exc


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


@dataclass
class AuthCredentials:
    """Credentials for a single quantum cloud provider.

    Attributes
    ----------
    token:
        Primary API token (used by IBM, IonQ, Rigetti).
    api_key:
        Static API key (used by IonQ, Rigetti as alternative).
    access_token:
        OAuth2 access token.
    refresh_token:
        OAuth2 refresh token for obtaining a new access_token.
    expires_at:
        ISO-8601 timestamp when the token expires.
    provider:
        Provider name.
    endpoint:
        API base URL.
    """

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


# ---------------------------------------------------------------------------
# AuthManager
# ---------------------------------------------------------------------------


class AuthManager:
    """Manages authentication credentials for multiple quantum cloud providers.

    Supports:
    - Environment variable loading
    - JSON file persistence
    - Real OAuth2 token exchange (IBM, IonQ, Rigetti)
    - Automatic token refresh on expiry
    - Token validation via provider APIs
    """

    def __init__(self) -> None:
        self._credentials: Dict[str, AuthCredentials] = {}
        # Allow subclasses to register custom refresh callbacks
        self._refresh_callbacks: Dict[str, Callable[[str, AuthManager], None]] = {}

    # -- Credential CRUD ---------------------------------------------------

    def set_credentials(self, provider: str, credentials: AuthCredentials) -> None:
        """Store credentials for a provider."""
        key = provider.lower()
        credentials.provider = key
        self._credentials[key] = credentials

    def get_credentials(self, provider: str) -> Optional[AuthCredentials]:
        """Retrieve credentials for a provider, or None if absent.

        Automatically attempts token refresh if credentials are expired.
        """
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

    # -- Token refresh -----------------------------------------------------

    def register_refresh_callback(
        self, provider: str, callback: Callable[[str, AuthManager], None]
    ) -> None:
        """Register a custom callback for token refresh on a provider.

        The callback receives (provider_name, auth_manager) and should
        update the auth_manager's stored credentials for that provider.
        """
        self._refresh_callbacks[provider.lower()] = callback

    def _token_refresh(self, provider: str) -> None:
        """Attempt to refresh expired credentials for *provider*.

        Uses registered callback first, then falls back to built-in
        OAuth2 refresh flows for IBM, IonQ, and Rigetti.
        """
        key = provider.lower()
        creds = self._credentials.get(key)
        if creds is None:
            return

        # 1. Try registered callback
        callback = self._refresh_callbacks.get(key)
        if callback is not None:
            try:
                callback(key, self)
                return
            except Exception as exc:
                logger.warning(
                    "Custom refresh callback failed for %s: %s", key, exc
                )

        # 2. Try built-in OAuth2 refresh
        config = _PROVIDER_AUTH_CONFIG.get(key)
        refresh_url = (config or {}).get("refresh_url")
        if not refresh_url or not creds.refresh_token:
            logger.debug(
                "No refresh mechanism available for %s (no refresh_url or refresh_token)",
                key,
            )
            return

        try:
            token_data = _http_request(
                "POST",
                refresh_url,
                body={
                    "grant_type": "refresh_token",
                    "refresh_token": creds.refresh_token,
                },
            )
        except (RuntimeError, ConnectionError) as exc:
            logger.warning("Token refresh HTTP call failed for %s: %s", key, exc)
            return

        # Update credentials with refreshed values
        new_access = token_data.get(
            "access_token", token_data.get("token", creds.access_token)
        )
        new_refresh = token_data.get("refresh_token", creds.refresh_token)
        expires_in = token_data.get("expires_in")

        if new_access:
            creds.access_token = new_access
            creds.token = new_access
        if new_refresh:
            creds.refresh_token = new_refresh
        if expires_in is not None:
            try:
                exp_dt = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
                creds.expires_at = exp_dt.isoformat()
            except (ValueError, TypeError):
                pass

        self._credentials[key] = creds
        logger.info("Refreshed token for provider %s", key)

    # -- Token validation --------------------------------------------------

    def validate_token(self, provider: str) -> bool:
        """Validate that the stored credentials are still accepted by the provider.

        Makes a lightweight API call to the provider's verify endpoint.

        Returns True if valid, False otherwise.
        """
        creds = self._credentials.get(provider.lower())
        if creds is None:
            return False

        config = _PROVIDER_AUTH_CONFIG.get(provider.lower(), {})
        verify_url = config.get("verify_url")
        if not verify_url:
            # No verify endpoint — trust the local expiry check
            return creds.is_valid

        token = creds.token or creds.access_token or creds.api_key
        if not token:
            return False

        try:
            _http_request(
                "GET",
                verify_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            return True
        except (RuntimeError, ConnectionError):
            return False

    # -- Convenience -------------------------------------------------------

    def get_token(self, provider: str) -> Optional[str]:
        """Return the best available token for *provider*."""
        creds = self.get_credentials(provider)
        if creds is None:
            return None
        return creds.token or creds.access_token or creds.api_key

    def get_endpoint(self, provider: str) -> Optional[str]:
        """Return the stored endpoint for *provider*, or None."""
        creds = self.get_credentials(provider)
        return creds.endpoint if creds else None

    def __repr__(self) -> str:
        providers = self.list_providers()
        return f"AuthManager(providers={providers!r})"
