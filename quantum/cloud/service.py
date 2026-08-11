"""
UMEROS Cloud Service
====================
High-level facade for managing sessions and jobs across providers.
Integrates real provider REST API clients, token validation, and
auto-connection workflows.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .auth import AuthManager, AuthCredentials, _http_request
from .job import CloudJob, CloudJobResult, CloudJobStatus
from .session import CloudSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default API endpoints per provider
# ---------------------------------------------------------------------------

_DEFAULT_ENDPOINTS: Dict[str, str] = {
    "ibm": "https://auth.quantum-computing.ibm.com/api",
    "ionq": "https://api.ionq.co/v0.3",
    "braket": "https://braket.us-east-1.amazonaws.com",
    "rigetti": "https://qpu.rigetti.com/v1",
}

# ---------------------------------------------------------------------------
# Provider account-info endpoints
# ---------------------------------------------------------------------------

_ACCOUNT_INFO_ENDPOINTS: Dict[str, str] = {
    "ibm": "https://auth.quantum-computing.ibm.com/api/users/me",
    "ionq": "https://api.ionq.co/v0.3/auth/me",
    "braket": "https://braket.us-east-1.amazonaws.com/account",
    "rigetti": "https://qpu.rigetti.com/v1/auth/me",
}


class CloudService:
    """Unified entry-point for quantum cloud operations.

    Integrates real provider REST API clients from :mod:`cloud.session` and
    :mod:`cloud.job`, with automatic token validation and connection
    management via :class:`AuthManager`.

    Parameters
    ----------
    auth_manager:
        Pre-configured :class:`AuthManager`.  A new instance is created
        when *None* is provided.
    """

    def __init__(self, auth_manager: Optional[AuthManager] = None) -> None:
        self._auth_manager = auth_manager or AuthManager()
        self._sessions: Dict[str, CloudSession] = {}

    # -- Connection management ---------------------------------------------

    def connect(
        self,
        provider: str,
        token: Optional[str] = None,
        endpoint: Optional[str] = None,
        validate: bool = True,
    ) -> CloudSession:
        """Create and start a session for *provider*.

        If a session already exists for the provider it is stopped first.

        Parameters
        ----------
        provider:
            Provider name (``"ibm"``, ``"ionq"``, ``"braket"``, ``"rigetti"``).
        token:
            API token or key.  Falls back to :class:`AuthManager` credentials.
        endpoint:
            API base URL.  Uses provider default when *None*.
        validate:
            If *True*, validate the token against the provider before
            establishing the session.

        Returns
        -------
        CloudSession
        """
        provider_key = provider.lower()
        if provider_key in self._sessions:
            old = self._sessions[provider_key]
            if old.is_active:
                old.stop()

        # Resolve token from argument or auth manager
        resolved_token = token
        if not resolved_token:
            resolved_token = self._auth_manager.get_token(provider_key)

        resolved_endpoint = endpoint or _DEFAULT_ENDPOINTS.get(provider_key, "")

        # Optional token validation
        if validate and resolved_token:
            if not self._validate_token_remote(provider_key, resolved_token):
                logger.warning(
                    "Token validation failed for %s — proceeding anyway",
                    provider_key,
                )

        session = CloudSession(
            provider=provider_key,
            token=resolved_token,
            endpoint=resolved_endpoint,
            auth_manager=self._auth_manager,
        )
        session.start()
        self._sessions[provider_key] = session
        return session

    def connect_if_needed(self, provider: str) -> CloudSession:
        """Return the existing session for *provider*, or create one.

        Convenience method that avoids duplicate ``connect()`` calls.
        """
        session = self._sessions.get(provider.lower())
        if session is not None and session.is_active:
            return session
        return self.connect(provider)

    def disconnect(self, provider: Optional[str] = None) -> None:
        """Stop one or all sessions.

        Parameters
        ----------
        provider:
            If given, only the session for this provider is stopped.
            Otherwise all active sessions are stopped.
        """
        if provider is not None:
            key = provider.lower()
            session = self._sessions.get(key)
            if session is not None and session.is_active:
                session.stop()
        else:
            for session in self._sessions.values():
                if session.is_active:
                    session.stop()

    def list_providers(self) -> List[str]:
        """Return provider names that currently have an active session."""
        return sorted(self._sessions.keys())

    def is_connected(self, provider: str) -> bool:
        """Return True if an active session exists for *provider*."""
        session = self._sessions.get(provider.lower())
        return session is not None and session.is_active

    def get_session(self, provider: str) -> Optional[CloudSession]:
        """Return the session for *provider*, or None."""
        return self._sessions.get(provider.lower())

    # -- Job operations (convenience wrappers) ----------------------------

    def submit(
        self,
        provider: str,
        backend_name: str,
        circuits: Any,
        shots: int = 1024,
        auto_connect: bool = True,
        **options: Any,
    ) -> CloudJob:
        """Submit a circuit to *provider* / *backend_name*.

        Parameters
        ----------
        provider:
            Target cloud provider.
        backend_name:
            Target backend identifier.
        circuits:
            Circuit description (dict or list of dicts).
        shots:
            Number of measurement repetitions.
        auto_connect:
            If *True*, automatically connect when no active session exists.
        **options:
            Additional provider-specific options.

        Raises
        ------
        RuntimeError
            If no active session exists for *provider* and *auto_connect* is False.
        """
        if auto_connect:
            self.connect_if_needed(provider)
        session = self._get_active_session(provider)
        circuit_dict = circuits if isinstance(circuits, dict) else {"circuits": circuits}
        return session.submit(
            circuit_dict=circuit_dict,
            backend_name=backend_name,
            shots=shots,
            **options,
        )

    def list_jobs(
        self,
        provider: str,
        status: Optional[CloudJobStatus] = None,
        limit: int = 20,
    ) -> List[CloudJob]:
        """List jobs for *provider*."""
        session = self._get_active_session(provider)
        return session.list_jobs(status=status, limit=limit)

    def get_job(self, provider: str, job_id: str) -> CloudJob:
        """Retrieve a job by id from *provider*."""
        session = self._get_active_session(provider)
        return session.get_job(job_id)

    def cancel_job(self, provider: str, job_id: str) -> None:
        """Cancel a job on *provider*."""
        session = self._get_active_session(provider)
        session.cancel_job(job_id)

    def wait_for_job(
        self,
        provider: str,
        job_id: str,
        poll_interval: float = 5.0,
        timeout: Optional[float] = None,
    ) -> CloudJob:
        """Block until *job_id* completes or times out.

        Parameters
        ----------
        provider:
            Target cloud provider.
        job_id:
            Job identifier.
        poll_interval:
            Seconds between status polls.
        timeout:
            Maximum seconds to wait.  *None* means no limit.
        """
        session = self._get_active_session(provider)
        return session.wait_for_job(
            job_id, poll_interval=poll_interval, timeout=timeout
        )

    def list_backends(
        self, provider: str, status_filter: Optional[str] = None
    ) -> List[dict]:
        """List available backends for *provider*."""
        session = self._get_active_session(provider)
        return session.list_backends(status_filter=status_filter)

    def backend_properties(self, provider: str, backend_name: str) -> dict:
        """Return calibration properties for a specific backend."""
        session = self._get_active_session(provider)
        return session.get_backend_properties(backend_name)

    # -- Account info ------------------------------------------------------

    def account_info(self, provider: str) -> dict:
        """Return basic account / connection info for *provider*.

        Attempts a real API call to the provider's account endpoint.
        Falls back to local credential metadata on failure.
        """
        provider_key = provider.lower()
        creds = self._auth_manager.get_credentials(provider_key)
        session = self._sessions.get(provider_key)

        info: Dict[str, Any] = {
            "provider": provider_key,
            "session_id": session.session_id if session else None,
            "endpoint": session.endpoint if session else _DEFAULT_ENDPOINTS.get(provider_key),
            "has_credentials": creds is not None and creds.is_valid,
            "token_valid": False,
        }

        # Try real API call
        account_url = _ACCOUNT_INFO_ENDPOINTS.get(provider_key)
        token = self._auth_manager.get_token(provider_key)
        if account_url and token:
            try:
                account_data = _http_request(
                    "GET",
                    account_url,
                    headers={"Authorization": f"Bearer {token}"},
                )
                info["account"] = account_data
                info["token_valid"] = True
            except (RuntimeError, ConnectionError) as exc:
                logger.debug("Account info fetch failed for %s: %s", provider_key, exc)

        return info

    # -- Token management --------------------------------------------------

    def validate_token(self, provider: str) -> bool:
        """Validate the stored token for *provider* against the remote API."""
        return self._auth_manager.validate_token(provider)

    def refresh_token(self, provider: str) -> bool:
        """Attempt to refresh the token for *provider*.

        Returns True if new credentials were obtained.
        """
        key = provider.lower()
        creds_before = self._auth_manager.get_credentials(key)
        self._auth_manager._token_refresh(key)
        creds_after = self._auth_manager.get_credentials(key)
        if creds_after is None:
            return False
        if creds_before and creds_before.token == creds_after.token:
            return False
        return True

    # -- Internal helpers --------------------------------------------------

    def _get_active_session(self, provider: str) -> CloudSession:
        """Return the active session for *provider* or raise."""
        key = provider.lower()
        session = self._sessions.get(key)
        if session is None or not session.is_active:
            raise RuntimeError(
                f"No active session for provider {provider!r}. "
                "Call connect() first."
            )
        return session

    def _validate_token_remote(self, provider: str, token: str) -> bool:
        """Validate a token against the provider's verify endpoint."""
        verify_url = _ACCOUNT_INFO_ENDPOINTS.get(provider)
        if not verify_url or not token:
            return True  # Can't validate — assume valid
        try:
            _http_request(
                "GET",
                verify_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            return True
        except (RuntimeError, ConnectionError):
            return False

    # -- Dunder ------------------------------------------------------------

    def __repr__(self) -> str:
        providers = self.list_providers()
        return f"CloudService(providers={providers!r})"
