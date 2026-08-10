"""
UMEROS Cloud Service
=====================
High-level façade for managing sessions and jobs across providers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .auth import AuthManager, AuthCredentials
from .job import CloudJob, CloudJobStatus
from .session import CloudSession


class CloudService:
    """Unified entry-point for quantum cloud operations.

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
    ) -> CloudSession:
        """Create and start a session for *provider*.

        If a session already exists for the provider it is stopped first.

        Returns
        -------
        CloudSession
        """
        provider_key = provider.lower()
        if provider_key in self._sessions:
            old = self._sessions[provider_key]
            if old.is_active:
                old.stop()
        session = CloudSession(
            provider=provider_key,
            token=token,
            endpoint=endpoint,
            auth_manager=self._auth_manager,
        )
        session.start()
        self._sessions[provider_key] = session
        return session

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
        **options:
            Additional provider-specific options.

        Raises
        ------
        RuntimeError
            If no active session exists for *provider*.
        """
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

        Raises
        ------
        RuntimeError
            If no active session exists for *provider*.
        """
        session = self._get_active_session(provider)
        creds = self._auth_manager.get_credentials(provider)
        return {
            "provider": provider,
            "session_id": session.session_id,
            "endpoint": session.endpoint,
            "has_credentials": creds is not None and creds.is_valid,
        }

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

    # -- Dunder ------------------------------------------------------------

    def __repr__(self) -> str:
        providers = self.list_providers()
        return f"CloudService(providers={providers!r})"
