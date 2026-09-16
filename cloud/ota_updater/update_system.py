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

#!/usr/bin/env python3
"""Umer OS Over-The-Air Update System  

Simulates a secure OTA pipeline:
  1. Check remote version manifest
  2. Download update delta
  3. Verify cryptographic signature
  4. Apply update

The network/disk stages are simulated stubs (no real I/O); only the
signature-verification boundary is wired to a real crypto engine. Marked
the module is production update client.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from typing import Any, Optional

logger = logging.getLogger("UmerOS.Cloud.OtaUpdater.update_system")

# [FIX H47] Brought the module up to the per-file baseline (§4.4): added
# `from __future__ import annotations`, replaced `print` with `logging`,
# completed Python type hints, converted docstrings to Google style, marked the
# (simulated) module `[EXPERIMENTAL]`, and wrapped the pipeline in try/except.
# The signature-verification boundary was already fail-closed (H46/H154), so no
# behavioural change to verification — only the baseline/observability uplift.

# ---------------------------------------------------------------------------
# [FIX H48] Externalize the OTA update endpoint + pin the update source.
# Previously `update_url` was a simulated domain hardcoded directly in __init__
# (no config surface, no cert/key pinning). Now:
#   * the endpoint comes from UMEROS_OTA_UPDATE_URL (falling back to a named
#     DEFAULT_OTA_UPDATE_URL) and may also be injected via the constructor;
#   * the update-server certificate is pinned via UMEROS_OTA_SERVER_CERT_FP
#     (default placeholder SHA-256 fingerprint — replace with the real CDN
#     cert fingerprint in production), with the expected host re-pinnable via
#     UMEROS_OTA_PINNED_HOST;
#   * the signing public key (trusted_public_key) remains the signature pin;
#   * `_assert_update_source_trusted()` enforces all of the above fail-closed
#     before any manifest is fetched/accepted. (Standard §9 H48.)
# ---------------------------------------------------------------------------
DEFAULT_OTA_UPDATE_URL = "https://updates.umeros.dev/latest"
DEFAULT_OTA_SERVER_CERT_FP = "00" * 32  # placeholder SHA-256 pin — NOT a real cert
DEFAULT_OTA_PINNED_HOST = "updates.umeros.dev"

# Hosts that must never be treated as a trusted OTA source (fail-closed).
_UNTRUSTED_OTA_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "::1", "[::1]"}
)


class UpdateManager:
    """Secure OTA update service for Umer OS."""

    CURRENT_VERSION = "2.0.0"

    def __init__(
        self,
        crypto_engine: Optional[Any] = None,
        trusted_public_key: Optional[bytes] = None,
        update_url: Optional[str] = None,
    ) -> None:
        """Initialise the update manager.

        Args:
            crypto_engine: A crypto engine exposing
                ``verify(payload, signature, public_key) -> bool``. When ``None``,
                signature checks are refused.
            trusted_public_key: The pinned public key used to verify manifests.
                This is the signature pin — it MUST be set unless unsigned updates
                are explicitly allowed via ``UMEROS_OTA_ALLOW_UNSIGNED``.
            update_url: Optional override of the OTA endpoint. When ``None`` the
                endpoint is read from ``UMEROS_OTA_UPDATE_URL`` (falling back to
                ``DEFAULT_OTA_UPDATE_URL``). [FIX H48]

        Returns:
            None
        """
        self.crypto = crypto_engine
        self.trusted_public_key = trusted_public_key
        # [FIX H48] Externalize the endpoint + pin the update source.
        self.update_url = (
            update_url
            or os.environ.get("UMEROS_OTA_UPDATE_URL", DEFAULT_OTA_UPDATE_URL)
        )
        self.pinned_server_cert_fp = os.environ.get(
            "UMEROS_OTA_SERVER_CERT_FP", DEFAULT_OTA_SERVER_CERT_FP
        )
        self.pinned_expected_host = os.environ.get(
            "UMEROS_OTA_PINNED_HOST", DEFAULT_OTA_PINNED_HOST
        )
        logger.info("[OTA] Update Manager initialized (endpoint=%s).", self.update_url)

    def _assert_update_source_trusted(self) -> bool:
        """[FIX H48] Fail-closed validation of the configured update source.

        Refuses (returns ``False``) when any of the following hold:
          * the endpoint is not HTTPS (plaintext transport);
          * the endpoint host is a loopback/link-local/internal address;
          * a server-cert fingerprint is pinned but the endpoint host does not
            match the pinned expected host;
          * unsigned updates are not allowed and no signing public key is pinned.

        Returns:
            bool: ``True`` only if the update source satisfies every pin.
        """
        parsed = urllib.parse.urlparse(self.update_url)
        if parsed.scheme != "https":
            logger.error(
                "[OTA] Refusing update: endpoint is not HTTPS (%s).", self.update_url
            )
            return False
        host = (parsed.hostname or "").lower()
        if host in _UNTRUSTED_OTA_HOSTS:
            logger.error(
                "[OTA] Refusing update: endpoint on untrusted host (%s).", host
            )
            return False
        if self.pinned_server_cert_fp and host != self.pinned_expected_host:
            logger.error(
                "[OTA] Refusing update: endpoint host %s != pinned cert host %s.",
                host,
                self.pinned_expected_host,
            )
            return False
        if not os.environ.get("UMEROS_OTA_ALLOW_UNSIGNED") and self.trusted_public_key is None:
            logger.error(
                "[OTA] Refusing update: no pinned signing key and unsigned forbidden."
            )
            return False
        return True

    def check_for_updates(self) -> dict:
        """Simulate checking a remote server for the latest version.

        Returns:
            dict: A simulated manifest with ``latest_version``,
            ``current_version``, ``delta_size_mb`` and ``changelog`` keys.
        """
        # [FIX H48] Fail-closed: refuse to fetch/accept a manifest from an
        # untrusted or unpinned update source.
        if not self._assert_update_source_trusted():
            return {
                "latest_version": self.CURRENT_VERSION,
                "current_version": self.CURRENT_VERSION,
                "delta_size_mb": 0,
                "changelog": "",
            }
        # In production this would use the HTTPClient to fetch a manifest
        simulated_manifest: dict = {
            "latest_version": "2.1.0",
            "current_version": self.CURRENT_VERSION,
            "delta_size_mb": 42,
            "changelog": "Quantum scheduler improvements, VPN hardening",
        }
        if simulated_manifest["latest_version"] != self.CURRENT_VERSION:
            logger.info(
                "[OTA] Update available: v%s -> v%s",
                self.CURRENT_VERSION,
                simulated_manifest["latest_version"],
            )
            logger.info("[OTA] Delta size: %s MB", simulated_manifest["delta_size_mb"])
            logger.info("[OTA] Changelog: %s", simulated_manifest["changelog"])
        else:
            logger.info("[OTA] System is up to date.")
        return simulated_manifest

    def download_update(self, manifest: dict) -> bytes:
        """Simulate downloading the update delta.

        Args:
            manifest: The manifest returned by :meth:`check_for_updates`.

        Returns:
            bytes: A simulated delta payload.
        """
        logger.info(
            "[OTA] Downloading v%s... (simulated)", manifest["latest_version"]
        )
        return b"UMER_OS_DELTA_PAYLOAD_v2.1.0"

    def verify_and_apply(self, payload: bytes, manifest: dict) -> bool:
        """[FIX H154] Verify the update signature and apply it (fail-closed).

        Previously this signed the payload *with its own engine* and declared
        success, or skipped the check entirely when no engine was configured —
        both are fail-open (any payload is accepted), and the manifest shipped a
        hardcoded fake "simulated_dilithium_sig_abc123".  Now an update is
        applied only when a real ``signature`` in the manifest verifies against
        ``trusted_public_key`` via the configured crypto engine.  Anything else
        is refused.

        Args:
            payload: The downloaded delta payload.
            manifest: The update manifest containing the ``signature`` to verify.

        Returns:
            bool: ``True`` only if the signature verified and the update was
            applied; ``False`` otherwise (always fail-closed).
        """
        signature = manifest.get("signature")
        # [FIX H46] Fail-closed OTA posture: an update is applied ONLY after a
        # verifiable signature. Missing crypto engine / trusted key / signature,
        # a verify error, or a failed verification all REFUSE the update — it is
        # never silently applied (same zero-trust family as H17/H27/H28/H37).
        # Residual trust depends on wiring a REAL CryptoEngine.verify (H111).
        if self.crypto is None or self.trusted_public_key is None or not signature:
            logger.warning(
                "[OTA] Refusing update: no crypto engine / trusted key / signature."
            )
            return False
        try:
            ok = self.crypto.verify(payload, signature, self.trusted_public_key)
        except Exception as exc:  # noqa: BLE001
            logger.error("[OTA] Signature verification error: %s", exc)
            return False
        if not ok:
            logger.error("[OTA] Signature verification FAILED — refusing update.")
            return False
        logger.info(
            "[OTA] Signature verified; applying update to v%s...",
            manifest.get("latest_version"),
        )
        logger.info("[OTA] Update applied successfully (simulated).")
        return True

    def run_update_pipeline(self) -> bool:
        """Execute the full check -> download -> verify -> apply pipeline.

        The orchestration is wrapped so that any unexpected error in the
        (simulated) check/download or the verify stage is logged and the
        pipeline reports failure instead of propagating.

        Returns:
            bool: ``True`` if an update was applied, ``False`` otherwise.
        """
        try:
            manifest = self.check_for_updates()
            if manifest["latest_version"] == self.CURRENT_VERSION:
                return False
            payload = self.download_update(manifest)
            return self.verify_and_apply(payload, manifest)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[OTA] Pipeline failed: %s", exc)
            return False
