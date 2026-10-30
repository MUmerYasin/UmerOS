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

"""Strict TLS policy for every provider REST call in the quantum stack.

Every outbound HTTP request in ``quantum/`` carries a provider credential in a
header -- IBM ``Bearer {access_token}``, IonQ ``apiKey {api_key}``, AWS
``AWS4-HMAC-SHA256 Credential={access_key}``, Rigetti ``Bearer {api_key}``.  A
``urllib.request.urlopen(req)`` with no ``context=`` argument silently uses
whatever the platform default happens to be, which is exactly the wrong
default for a bearer-token call: a rogue CA or an on-path attacker gets the
token.

This module is the single source of truth for that policy so the copies in
``cloud/auth.py``, ``cloud/job.py``, ``providers/*`` and ``quantum_sim.py``
cannot drift apart.  ``tls_context()`` returns a cached ``SSLContext`` that:

* verifies the peer certificate chain (``CERT_REQUIRED``),
* verifies the hostname matches the certificate (``check_hostname``),
* refuses anything below TLS 1.2,
* trusts **only** the file named by ``UMEROS_TLS_CAFILE`` when that variable is
  set (explicit CA pinning), and fails closed when the file cannot be loaded
  rather than silently falling back to the system trust store.

There is no opt-out.  No code path in this module can produce an unverified
context, and callers are expected to pass ``context=tls_context()`` to every
``urlopen``.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import ssl
from typing import Optional

log = logging.getLogger("UmerOS.Quantum.TLS")

#: Environment variable holding the path to a CA bundle used for pinning.
CAFILE_ENV = "UMEROS_TLS_CAFILE"

#: Lowest protocol version this policy permits.
MINIMUM_TLS_VERSION = ssl.TLSVersion.TLSv1_2

_cached_context: Optional[ssl.SSLContext] = None


def tls_context() -> ssl.SSLContext:
    """Return the cached, strict ``SSLContext`` used for provider REST calls.

    The context is built once and reused -- ``ssl.SSLContext`` is thread-safe
    for concurrent handshakes and rebuilding it per request would re-read the
    CA bundle on every call.

    Returns:
        A verifying ``SSLContext`` with ``CERT_REQUIRED``, hostname checking
        and a TLS 1.2 floor.

    Raises:
        RuntimeError: If ``UMEROS_TLS_CAFILE`` is set but the file cannot be
            loaded.  This is deliberately fatal: falling back to the system
            trust store would silently discard the operator's pinning intent,
            which is the failure mode pinning exists to prevent.
    """
    global _cached_context
    if _cached_context is not None:
        return _cached_context

    cafile = os.environ.get(CAFILE_ENV)
    if cafile:
        try:
            context = ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH, cafile=cafile
            )
        except (OSError, ssl.SSLError) as exc:
            raise RuntimeError(
                f"{CAFILE_ENV}={cafile!r} could not be loaded ({exc}); "
                "refusing to fall back to the system trust store"
            ) from exc
        log.info("TLS CA pinning enabled (%s=%s)", CAFILE_ENV, cafile)
    else:
        context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)

    # Enforce strict verification.  These assignments are redundant on a
    # create_default_context() result, but they are the actual policy: if the
    # platform default ever loosens, this module does not.
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.minimum_version = MINIMUM_TLS_VERSION

    _cached_context = context
    return context


def reset_tls_context() -> None:
    """Drop the cached context so the next call re-reads the environment.

    Intended for tests and for long-lived processes that change
    ``UMEROS_TLS_CAFILE`` at runtime; production code never needs it.
    """
    global _cached_context
    _cached_context = None
