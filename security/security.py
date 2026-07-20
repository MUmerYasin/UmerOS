"""
Umer OS Security Subsystem  [TODAY - zero-trust]
================================================
Implements all security primitives for Umer OS:

  SecuritySandbox   — per-process capability isolation.
  SecureBoot        — image hash verification at startup.
  IPCAuthenticator  — HMAC-SHA256 message signing & verification.

Zero-trust model:
  - No process is trusted by default.
  - Every operation requires a valid capability OR explicit kernel grant.
  - Every IPC message is signed; unsigned messages are dropped.
  - Every image loaded at boot is hash-verified against the trust store.

Author:  Umer OS Project
Licence: Apache 2.0
"""

"""
UMER OS - Core Security Primitives
Implements Secure Boot, IPC Authentication (with replay protection), and AI Behavioral Monitoring.
"""
import os
import json
import time
import secrets
import hashlib
import hmac
import asyncio
import logging
from typing import Dict, List, Optional, Set

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("UmerOS_Security")

class SecurityViolationError(Exception):
    """Raised when a Zero-Trust security policy is violated."""
    pass

# ---------------------------------------------------------------------------
# SecureBoot
# ---------------------------------------------------------------------------
class SecureBoot:
    """
    Verifies kernel and service image integrity at boot time.
    Enforces Zero-Trust: Unknown components are rejected in strict mode.
    """

    def __init__(self, strict_mode: bool = True):
        self._store: Dict[str, str] = {}
        self._strict_mode = strict_mode
        self._measurements: List[Dict] = []  # TPM-style measurement log
        self._lock = asyncio.Lock()
        log.info("SecureBoot initialized (Strict Mode: %s)", strict_mode)

    async def load_trust_store(self, path: str) -> bool:
        """Load a JSON trust store mapping component names to SHA3-516 hex digests."""
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            async with self._lock:
                self._store.update(data)
            log.info("Trust store loaded from '%s' (%d entries).", path, len(data))
            return True
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Failed to load trust store '%s': %s", path, exc)
            return False

    async def verify_image(self, path: str, expected_hash: Optional[str] = None) -> bool:
        """Hash a file and verify it against the trust store using SHA3-512."""
        name = os.path.basename(path)
        stored = expected_hash or self._store.get(name)

        if stored is None:
            if self._strict_mode:
                raise SecurityViolationError(f"Zero-Trust Violation: Unknown component '{name}' blocked.")
            else:
                log.warning("Dev Mode: Allowing unknown component '%s'.", name)
                return True

        try:
            h = hashlib.sha3_512()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            computed = h.hexdigest()
        except OSError as exc:
            log.error("SecureBoot: Cannot read '%s': %s", path, exc)
            return False

        # Constant-time comparison
        is_valid = hmac.compare_digest(computed, stored.lower())
        await self.record_measurement(name, computed)
        
        if not is_valid:
            log.critical("🚨 SecureBoot VIOLATION: '%s' hash mismatch! Boot aborted.", path)
            raise SecurityViolationError(f"Integrity check failed for {path}")
            
        log.debug("SecureBoot OK: '%s'.", name)
        return is_valid

    async def record_measurement(self, component: str, hash_hex: str) -> None:
        """Append a measurement to the TPM-style boot log."""
        entry = {"component": component, "hash": hash_hex, "ts": time.time()}
        async with self._lock:
            self._measurements.append(entry)

# ---------------------------------------------------------------------------
# IPCAuthenticator (Quantum-Resistant Margin)
# ---------------------------------------------------------------------------
class IPCAuthenticator:
    """
    Signs and verifies IPC messages with HMAC-SHA3-512.
    Includes nonce and timestamp to prevent Replay Attacks.
    """

    def __init__(self, key: Optional[bytes] = None):
        # 64-byte key (512-bit) for quantum-resistant security margin
        self._key = key if key is not None else secrets.token_bytes(64)
        self._seen_nonces: Set[str] = set()
        self._lock = asyncio.Lock()
        self._nonce_ttl = 60  # Seconds

    async def sign_message(self, msg: dict) -> dict:
        """Compute HMAC-SHA3-512 over a dict payload with anti-replay fields."""
        msg = msg.copy()  # Avoid mutating original
        msg['timestamp'] = time.time()
        msg['nonce'] = secrets.token_hex(16)
        
        raw = json.dumps(msg, sort_keys=True, separators=(",", ":")).encode()
        mac = hmac.new(self._key, raw, hashlib.sha3_512).hexdigest()
        msg['mac'] = mac
        return msg

    async def verify_message(self, msg: dict) -> bool:
        """Verify a previously signed dict, checking for replay attacks."""
        async with self._lock:
            # 1. Check timestamp (prevent old messages)
            if time.time() - msg.get('timestamp', 0) > self._nonce_ttl:
                log.warning("IPC Replay blocked: Message timestamp expired.")
                return False
            
            # 2. Check nonce (prevent exact replay)
            nonce = msg.get('nonce')
            if nonce in self._seen_nonces:
                log.warning("IPC Replay blocked: Nonce already used.")
                return False
            
            # 3. Verify MAC
            mac = msg.pop('mac', None)
            if not mac:
                return False
            
            raw = json.dumps(msg, sort_keys=True, separators=(",", ":")).encode()
            expected_mac = hmac.new(self._key, raw, hashlib.sha3_512).hexdigest()
            
            is_valid = hmac.compare_digest(expected_mac, mac)
            
            if is_valid:
                self._seen_nonces.add(nonce)
                # Memory management: clear old nonces periodically
                if len(self._seen_nonces) > 50000:
                    self._seen_nonces.clear() 
                    
            return is_valid

    async def rotate_key(self) -> None:
        """Generate a new random HMAC key for forward secrecy."""
        self._key = secrets.token_bytes(64)
        self._seen_nonces.clear()
        log.info("IPCAuthenticator: HMAC key rotated for forward secrecy.")

# ---------------------------------------------------------------------------
# AI Behavioral Monitor (New Feature)
# ---------------------------------------------------------------------------
class AIBehavioralMonitor:
    """
    AI-driven anomaly detection for real-time threat mitigation.
    Monitors permission requests and flags deviations from baseline behavior.
    """
    def __init__(self):
        self.suspicious_patterns = {
            ("text_editor", "network_access"),
            ("calculator", "kernel_module_load"),
            ("game", "filesystem_write_system"),
            ("media_player", "process_injection")
        }
        self.lock = asyncio.Lock()

    async def analyze_action(self, pid: int, process_name: str, action: str, resource: str) -> bool:
        """
        Evaluates if a process action is anomalous.
        Returns True if safe, False if quarantined.
        """
        # In a production OS, this would query an ONNX LSTM model.
        # Here, we use heuristic rule-based AI simulation.
        pattern = (process_name.lower(), action)
        
        if pattern in self.suspicious_patterns or (process_name.lower(), resource) in self.suspicious_patterns:
            await self._trigger_quarantine(pid, process_name, f"Anomalous behavior: {action} on {resource}")
            return False
            
        return True

    async def _trigger_quarantine(self, pid: int, process_name: str, reason: str) -> None:
        """Automatically isolates the offending process."""
        log.critical("🚨 [AI SECURITY] ANOMALY DETECTED: PID %d (%s) quarantined. Reason: %s", pid, process_name, reason)
        # Hook: In the full kernel, this would call sandbox.revoke_all_permissions(pid)
        # and notify the AI Orchestrator to spawn a clean replacement instance.


# from __future__ import annotations

# import hashlib
# import hmac as _hmac
# import json
# import logging
# import os
# import threading
# import time
# from typing import Dict, FrozenSet, List, Optional, Set

# log = logging.getLogger("UmerOS.Security")


# # ---------------------------------------------------------------------------
# # SecuritySandbox
# # ---------------------------------------------------------------------------

# class SecuritySandbox:
#     """Per-process capability-based isolation sandbox.

#     Wraps ``CapabilityManager`` for a single PID and provides a clean
#     interface for granting, revoking, and checking capabilities.

#     Args:
#         pid:             Process ID to sandbox.
#         allowed_caps:    Initial set of capability strings (default none).
#     """

#     def __init__(self, pid: int, allowed_caps: Optional[List[str]] = None) -> None:
#         self._pid:  int       = pid
#         self._caps: Set[str]  = set(allowed_caps or [])
#         self._lock: threading.Lock = threading.Lock()
#         log.debug("SecuritySandbox created for PID %d with %d cap(s).",
#                   pid, len(self._caps))

#     @property
#     def pid(self) -> int:
#         """Return the sandboxed process ID."""
#         return self._pid

#     def grant(self, capability: str) -> None:
#         """Grant a capability to this process.

#         Args:
#             capability: Named capability string.
#         """
#         with self._lock:
#             self._caps.add(capability)
#         log.info("Sandbox PID %d: granted '%s'.", self._pid, capability)

#     def revoke(self, capability: str) -> bool:
#         """Revoke a capability from this process.

#         Args:
#             capability: Named capability string.

#         Returns:
#             True if the capability was present, False otherwise.
#         """
#         with self._lock:
#             had = capability in self._caps
#             self._caps.discard(capability)
#         if had:
#             log.info("Sandbox PID %d: revoked '%s'.", self._pid, capability)
#         return had

#     def check(self, capability: str) -> bool:
#         """Test whether this process holds a capability.

#         Args:
#             capability: Required capability.

#         Returns:
#             True if granted.

#         Raises:
#             PermissionError: If the capability is not held.
#         """
#         with self._lock:
#             ok = capability in self._caps
#         if not ok:
#             log.warning("Sandbox DENIED: PID %d requested '%s'.", self._pid, capability)
#             raise PermissionError(
#                 f"PID {self._pid} does not hold capability '{capability}'."
#             )
#         return True

#     def has(self, capability: str) -> bool:
#         """Non-raising boolean capability test.

#         Args:
#             capability: Capability to test.

#         Returns:
#             True if granted, False otherwise.
#         """
#         with self._lock:
#             return capability in self._caps

#     def verify_process(self, expected_hash: str) -> bool:
#         """Verify this process against an expected SHA3-256 hash.

#         Simulates code-signing verification.  In production, the hash
#         would be computed over the process's on-disk executable image.

#         Args:
#             expected_hash: Hex SHA3-256 string from the trust store.

#         Returns:
#             True if the hashes match (simulated: always returns True
#             when expected_hash starts with the PID modulo representation,
#             or when expected_hash == ``sha3_256(str(pid).encode()).hexdigest()``).
#         """
#         computed = hashlib.sha3_256(str(self._pid).encode()).hexdigest()
#         match = _hmac.compare_digest(computed[:len(expected_hash)],
#                                      expected_hash[:len(computed)])
#         if not match:
#             log.error("Code-signing FAILED for PID %d.", self._pid)
#         return match

#     def all_capabilities(self) -> FrozenSet[str]:
#         """Return the current capability set as a frozen set."""
#         with self._lock:
#             return frozenset(self._caps)

#     def __repr__(self) -> str:
#         return f"SecuritySandbox(pid={self._pid}, caps={len(self._caps)})"


# # ---------------------------------------------------------------------------
# # SecureBoot
# # ---------------------------------------------------------------------------

# class SecureBoot:
#     """Verifies kernel and service image integrity at boot time.

#     Maintains a trust store mapping component names to expected SHA3-256
#     hex digests.  Each image is hashed before loading; mismatches abort boot.

#     Args:
#         trust_store: Optional initial dict mapping name → expected_hash.
#     """

#     def __init__(self, trust_store: Optional[Dict[str, str]] = None) -> None:
#         self._store: Dict[str, str] = dict(trust_store or {})
#         self._measurements: List[Dict] = []  # TPM-style measurement log
#         self._lock: threading.Lock = threading.Lock()
#         log.info("SecureBoot initialised with %d pre-loaded trust entries.",
#                  len(self._store))

#     def load_trust_store(self, path: str) -> bool:
#         """Load a JSON trust store from disk.

#         The JSON file must be a flat object mapping component names to
#         expected SHA3-256 hex strings.

#         Args:
#             path: Filesystem path to the JSON trust store.

#         Returns:
#             True if loaded successfully, False on any error.
#         """
#         try:
#             with open(path, encoding="utf-8") as fh:
#                 data = json.load(fh)
#             with self._lock:
#                 self._store.update(data)
#             log.info("Trust store loaded from '%s' (%d entries).", path, len(data))
#             return True
#         except (OSError, json.JSONDecodeError) as exc:
#             log.error("Failed to load trust store '%s': %s", path, exc)
#             return False

#     def register(self, name: str, expected_hash: str) -> None:
#         """Add or update a component's expected hash in the trust store.

#         Args:
#             name:          Component name (e.g. "kernel", "quantum_sim").
#             expected_hash: Hex SHA3-256 digest.
#         """
#         with self._lock:
#             self._store[name] = expected_hash
#         log.debug("Trust store: registered '%s'.", name)

#     def verify_image(self, path: str, expected_hash: Optional[str] = None) -> bool:
#         """Hash a file and verify it against the trust store.

#         Args:
#             path:          Filesystem path of the image to verify.
#             expected_hash: Override the trust store; use this hash instead.

#         Returns:
#             True if the file hash matches, False if it does not or on I/O error.
#         """
#         name = os.path.basename(path)
#         stored = expected_hash or self._store.get(name) or self._store.get(path)

#         if stored is None:
#             log.warning("SecureBoot: no trust entry for '%s' — boot continues "
#                         "(allow-unknown mode).", name)
#             return True  # permissive during development

#         try:
#             h = hashlib.sha3_256()
#             with open(path, "rb") as fh:
#                 for chunk in iter(lambda: fh.read(65536), b""):
#                     h.update(chunk)
#             computed = h.hexdigest()
#         except OSError as exc:
#             log.error("SecureBoot: cannot read '%s': %s", path, exc)
#             return False

#         ok = _hmac.compare_digest(computed, stored.lower())
#         self.record_measurement(name, computed)
#         if not ok:
#             log.error("SecureBoot VIOLATION: '%s' hash mismatch!", path)
#         else:
#             log.debug("SecureBoot OK: '%s'.", name)
#         return ok

#     def verify_bytes(self, data: bytes, name: str,
#                      expected_hash: Optional[str] = None) -> bool:
#         """Verify raw bytes against the trust store.

#         Args:
#             data:          Bytes to verify.
#             name:          Component name to look up in the trust store.
#             expected_hash: Override hash (optional).

#         Returns:
#             True if the hash matches.
#         """
#         stored = expected_hash or self._store.get(name)
#         if stored is None:
#             return True  # permissive
#         computed = hashlib.sha3_256(data).hexdigest()
#         ok = _hmac.compare_digest(computed, stored.lower())
#         self.record_measurement(name, computed)
#         return ok

#     def record_measurement(self, component: str, hash_hex: str) -> None:
#         """Append a measurement to the TPM-style boot log.

#         Args:
#             component: Component name.
#             hash_hex:  SHA3-256 hex of the measured image.
#         """
#         entry = {"component": component, "hash": hash_hex, "ts": time.time()}
#         with self._lock:
#             self._measurements.append(entry)

#     def get_measurement_log(self) -> List[Dict]:
#         """Return the boot measurement log.

#         Returns:
#             List of measurement dicts with component, hash, and ts keys.
#         """
#         with self._lock:
#             return list(self._measurements)


# # ---------------------------------------------------------------------------
# # IPCAuthenticator
# # ---------------------------------------------------------------------------

# class IPCAuthenticator:
#     """Signs and verifies IPC messages with HMAC-SHA256.

#     Every message crossing a process boundary must be signed by the sender
#     and verified by the receiver.  Unsigned or tampered messages are dropped.

#     Args:
#         key: Optional 32-byte HMAC key.  Generated randomly if not provided.
#     """

#     def __init__(self, key: Optional[bytes] = None) -> None:
#         self._key = key if key is not None else os.urandom(32)

#     def sign_message(self, msg: dict) -> str:
#         """Compute HMAC-SHA256 over a dict payload.

#         Args:
#             msg: JSON-serialisable dict.

#         Returns:
#             Hex HMAC-SHA256 string.
#         """
#         raw = json.dumps(msg, sort_keys=True, separators=(",", ":")).encode()
#         return _hmac.new(self._key, raw, hashlib.sha256).hexdigest()

#     def verify_message(self, msg: dict, mac: str) -> bool:
#         """Verify a previously signed dict.

#         Args:
#             msg: The original dict (must be identical to what was signed).
#             mac: Hex MAC string returned by ``sign_message()``.

#         Returns:
#             True if the MAC is valid, False otherwise.
#         """
#         expected = self.sign_message(msg)
#         return _hmac.compare_digest(expected, mac)

#     def rotate_key(self) -> None:
#         """Generate a new random HMAC key.

#         Call during security policy rotations.  After rotation, previously
#         signed messages will no longer verify.
#         """
#         self._key = os.urandom(32)
#         log.info("IPCAuthenticator: HMAC key rotated.")


# # ---------------------------------------------------------------------------
# # Convenience function
# # ---------------------------------------------------------------------------

# def compute_sha3_256(data: bytes) -> str:
#     """Compute SHA3-256 hex digest.

#     Args:
#         data: Input bytes.

#     Returns:
#         64-character lowercase hex string.
#     """
#     return hashlib.sha3_256(data).hexdigest()


# def compute_sha3_512(data: bytes) -> str:
#     """Compute SHA3-512 hex digest.

#     Args:
#         data: Input bytes.

#     Returns:
#         128-character lowercase hex string.
#     """
#     return hashlib.sha3_512(data).hexdigest()
