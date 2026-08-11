"""
UMEROS Cloud Session Pool
=========================
Connection pooling for quantum cloud sessions.

Reuses :class:`CloudSession` instances across multiple requests to reduce
connection overhead, API token usage, and latency.  Supports per-provider
pool sizing, idle eviction, and health checking.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .auth import AuthManager
from .session import CloudSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_MAX_SIZE = 5
_DEFAULT_IDLE_TIMEOUT = 300.0  # seconds
_DEFAULT_HEALTH_CHECK_INTERVAL = 60.0  # seconds


@dataclass
class PoolConfig:
    """Configuration for a session pool."""

    max_size: int = _DEFAULT_MAX_SIZE
    idle_timeout: float = _DEFAULT_IDLE_TIMEOUT
    health_check_interval: float = _DEFAULT_HEALTH_CHECK_INTERVAL
    auto_reconnect: bool = True


# ---------------------------------------------------------------------------
# Pool entry
# ---------------------------------------------------------------------------


@dataclass
class _PoolEntry:
    """Internal entry wrapping a session and its metadata."""

    session: CloudSession
    last_used: float = field(default_factory=time.monotonic)
    created_at: float = field(default_factory=time.monotonic)
    in_use: bool = False

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_used

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at


# ---------------------------------------------------------------------------
# Session Pool
# ---------------------------------------------------------------------------


class SessionPool:
    """Manages a pool of reusable :class:`CloudSession` instances.

    Usage::

        pool = SessionPool(auth_manager=my_auth)
        session = pool.acquire("ibm")
        try:
            job = session.submit(...)
        finally:
            pool.release("ibm", session)

    Parameters
    ----------
    auth_manager:
        Shared :class:`AuthManager` for credential resolution.
    config:
        Pool configuration.  Uses defaults when *None*.
    """

    def __init__(
        self,
        auth_manager: Optional[AuthManager] = None,
        config: Optional[PoolConfig] = None,
    ) -> None:
        self._auth_manager = auth_manager or AuthManager()
        self._config = config or PoolConfig()
        self._pools: Dict[str, List[_PoolEntry]] = {}
        self._lock = threading.Lock()
        self._stats: Dict[str, Dict[str, int]] = {}

    # -- Public API --------------------------------------------------------

    def acquire(
        self,
        provider: str,
        *,
        endpoint: Optional[str] = None,
        token: Optional[str] = None,
    ) -> CloudSession:
        """Acquire a session for *provider* from the pool.

        Returns an existing idle session if available, otherwise creates
        a new one.  The caller **must** call :meth:`release` when done.

        Parameters
        ----------
        provider:
            Provider name.
        endpoint:
            Override endpoint for new sessions.
        token:
            Override token for new sessions.
        """
        key = provider.lower()
        self._ensure_pool(key)

        with self._lock:
            # Try to reuse an existing idle session
            for entry in self._pools[key]:
                if not entry.in_use and entry.session.is_active:
                    if entry.idle_seconds < self._config.idle_timeout:
                        entry.in_use = True
                        entry.last_used = time.monotonic()
                        self._record_stat(key, "reuse")
                        logger.debug("Reused session for %s (idle %.1fs)", key, entry.idle_seconds)
                        return entry.session
                    else:
                        # Idle too long — stop and evict
                        logger.debug("Evicting stale session for %s", key)
                        try:
                            entry.session.stop()
                        except Exception:
                            pass

            # Clean up dead sessions
            self._pools[key] = [
                e for e in self._pools[key]
                if e.session.is_active or e.in_use
            ]

            # Create a new session if under capacity
            if len(self._pools[key]) < self._config.max_size:
                session = CloudSession(
                    provider=key,
                    token=token,
                    endpoint=endpoint,
                    auth_manager=self._auth_manager,
                )
                session.start()
                entry = _PoolEntry(session=session, in_use=True)
                self._pools[key].append(entry)
                self._record_stat(key, "create")
                logger.debug("Created new session for %s (pool size: %d)", key, len(self._pools[key]))
                return session

            # Pool is full — return the least-recently-used active session
            # This shouldn't happen in normal usage but handles edge cases
            self._record_stat(key, "overflow")
            logger.warning("Pool full for %s — creating overflow session", key)
            session = CloudSession(
                provider=key,
                token=token,
                endpoint=endpoint,
                auth_manager=self._auth_manager,
            )
            session.start()
            return session

    def release(self, provider: str, session: CloudSession) -> None:
        """Return a session to the pool for reuse.

        Parameters
        ----------
        provider:
            Provider name.
        session:
            The session to release.
        """
        key = provider.lower()
        with self._lock:
            entries = self._pools.get(key, [])
            for entry in entries:
                if entry.session is session:
                    entry.in_use = False
                    entry.last_used = time.monotonic()
                    self._record_stat(key, "release")
                    logger.debug("Released session for %s", key)
                    return

        # Session not found in pool — just stop it
        try:
            session.stop()
        except Exception:
            pass

    def acquire_context(
        self,
        provider: str,
        *,
        endpoint: Optional[str] = None,
        token: Optional[str] = None,
    ) -> _SessionContextManager:
        """Return a context manager that acquires and auto-releases a session.

        Usage::

            with pool.acquire_context("ibm") as session:
                job = session.submit(...)
        """
        return _SessionContextManager(
            pool=self,
            provider=provider,
            endpoint=endpoint,
            token=token,
        )

    def drain(self, provider: Optional[str] = None) -> int:
        """Stop and remove all sessions from the pool.

        Parameters
        ----------
        provider:
            If given, only drain sessions for this provider.

        Returns
        -------
        int
            Number of sessions stopped.
        """
        count = 0
        with self._lock:
            keys = [provider.lower()] if provider else list(self._pools.keys())
            for key in keys:
                entries = self._pools.pop(key, [])
                for entry in entries:
                    if entry.session.is_active:
                        try:
                            entry.session.stop()
                            count += 1
                        except Exception:
                            pass
        return count

    def health_check(self) -> Dict[str, Dict[str, Any]]:
        """Run a health check on all pooled sessions.

        Returns a dict mapping provider names to health status dicts.
        """
        report: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            for key, entries in self._pools.items():
                active = sum(1 for e in entries if e.session.is_active)
                idle = sum(
                    1 for e in entries
                    if e.session.is_active and not e.in_use
                )
                in_use = sum(1 for e in entries if e.in_use)
                stale = sum(
                    1 for e in entries
                    if not e.in_use and e.idle_seconds > self._config.idle_timeout
                )
                report[key] = {
                    "total": len(entries),
                    "active": active,
                    "idle": idle,
                    "in_use": in_use,
                    "stale": stale,
                }
        return report

    def stats(self) -> Dict[str, Dict[str, int]]:
        """Return usage statistics per provider."""
        return dict(self._stats)

    # -- Size management ---------------------------------------------------

    def set_max_size(self, provider: str, max_size: int) -> None:
        """Update the maximum pool size for a provider."""
        key = provider.lower()
        with self._lock:
            self._ensure_pool(key)
            self._pools[key] = self._pools[key][:max_size]

    def resize(self, provider: str, new_max: int) -> int:
        """Resize the pool, evicting excess sessions.

        Returns the number of sessions stopped.
        """
        key = provider.lower()
        count = 0
        with self._lock:
            self._ensure_pool(key)
            while len(self._pools[key]) > new_max:
                # Evict the least-recently-used idle session
                evict = None
                for entry in self._pools[key]:
                    if not entry.in_use and entry.session.is_active:
                        if evict is None or entry.last_used < evict.last_used:
                            evict = entry
                if evict is None:
                    break
                self._pools[key].remove(evict)
                try:
                    evict.session.stop()
                    count += 1
                except Exception:
                    pass
        return count

    # -- Internal ----------------------------------------------------------

    def _ensure_pool(self, key: str) -> None:
        """Ensure a pool list exists for *key* (caller must hold lock)."""
        if key not in self._pools:
            self._pools[key] = []

    def _record_stat(self, key: str, action: str) -> None:
        """Increment a stat counter (caller must hold lock)."""
        if key not in self._stats:
            self._stats[key] = {}
        self._stats[key][action] = self._stats[key].get(action, 0) + 1

    def __repr__(self) -> str:
        with self._lock:
            sizes = {k: len(v) for k, v in self._pools.items()}
        return f"SessionPool(config={self._config!r}, sizes={sizes!r})"


# ---------------------------------------------------------------------------
# Context manager helper
# ---------------------------------------------------------------------------


class _SessionContextManager:
    """Context manager that acquires a session from a pool and releases it on exit."""

    def __init__(
        self,
        pool: SessionPool,
        provider: str,
        endpoint: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        self._pool = pool
        self._provider = provider
        self._endpoint = endpoint
        self._token = token
        self._session: Optional[CloudSession] = None

    def __enter__(self) -> CloudSession:
        self._session = self._pool.acquire(
            self._provider,
            endpoint=self._endpoint,
            token=self._token,
        )
        return self._session

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._session is not None:
            self._pool.release(self._provider, self._session)
            self._session = None
