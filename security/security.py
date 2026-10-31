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

"""
Umer OS Security Subsystem  [TODAY - zero-trust]
================================================
Implements all security primitives for Umer OS:

  SecuritySandbox   — per-process capability isolation.
  SecureBoot        — image hash verification at startup.
  IPCAuthenticator  — HMAC-SHA3-256 signing, replay-protected verification.

Zero-trust model:
  - No process is trusted by default.
  - Every operation requires a valid capability OR explicit kernel grant.
  - Every IPC message is signed; unsigned messages are dropped.
  - Every image loaded at boot is hash-verified against the trust store.
UMER OS - Core Security Primitives
Implements Secure Boot, IPC Authentication (with replay protection), and heuristic behavioural monitoring.
Umer OS Security Subsystem [TODAY - zero-trust]
================================================
Implements all security primitives for Umer OS:
- SecuritySandbox (in sandbox.py)
- SecureBoot (image hash verification at startup)
- IPCAuthenticator (HMAC-SHA3-256 message signing & anti-replay)
- AIBehavioralMonitor (heuristic rule-based behavioural monitor; no model)
"""
# CRITICAL: __future__ imports must be at the very top
from __future__ import annotations 
import hashlib
import hmac as _hmac
import json
import logging
import os
import secrets
import threading
import time
from typing import Dict, List, Optional, Set, Tuple

log = logging.getLogger("UmerOS.Security")

# ---------------------------------------------------------------------------
# SecureBoot (Upgraded with Strict Mode)
# ---------------------------------------------------------------------------
class SecureBoot:
    """Verifies kernel and service image integrity at boot time."""
    
    def __init__(self, strict_mode: bool = True):
        self._store: Dict[str, str] = {}
        self._strict_mode = strict_mode
        self._measurements: List[Dict] = []  # TPM-style measurement log
        self._lock: threading.Lock = threading.Lock()
        log.info("SecureBoot initialised (Strict Mode: %s)", strict_mode)

    # ------------------------------------------------------------------
    # Trust store
    # ------------------------------------------------------------------
    def register(self, name: str, expected_hash: str) -> None:
        """Add a component name and its expected SHA-3 hash to the trust store."""
        with self._lock:
            self._store[name] = expected_hash
        log.info("SecureBoot: registered '%s'.", name)

    def load_trust_store(self, path: str) -> bool:
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            with self._lock:
                self._store.update(data)
            log.info("Trust store loaded from '%s' (%d entries).", path, len(data))
            return True
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Failed to load trust store '%s': %s", path, exc)
            return False

    # ------------------------------------------------------------------
    # Verification helpers
    # ------------------------------------------------------------------
    def _compute_file_hash(self, path: str) -> str:
        h = hashlib.sha3_256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def verify_image(self, path: str, expected_hash: Optional[str] = None) -> bool:
        name = os.path.basename(path)
        stored = expected_hash or self._store.get(name)

        # Zero-trust is FAIL-CLOSED. An unknown component (no
        # trust-store entry AND no caller-supplied expected_hash) has no basis
        # for trust and MUST be denied. The previous code returned True here
        # (fail-open), letting arbitrary, unverified images boot/load.
        if stored is None:
            if self._strict_mode:
                raise PermissionError(f"🚨 Zero-Trust Violation: Unknown component '{name}' blocked.")
            log.warning("Zero-Trust: denying unknown component '%s' (dev mode).", name)
            return False

        try:
            computed = self._compute_file_hash(path)
        except OSError as exc:
            log.error("SecureBoot: cannot read '%s': %s", path, exc)
            return False

        ok = _hmac.compare_digest(computed, stored.lower())
        self.record_measurement(name, computed)

        if not ok:
            log.critical("🚨 SecureBoot VIOLATION: '%s' hash mismatch!", path)
            return False

        log.debug("SecureBoot OK: '%s'.", name)
        return ok

    def verify_bytes(self, data: bytes, name: str, expected_hash: Optional[str] = None) -> bool:
        """Verify in-memory *data* against an expected SHA-3-256 hash."""
        stored = expected_hash or self._store.get(name)
        # Unknown component (no trust entry, no expected hash) is
        # denied in both strict and dev modes — fail-closed by default.
        if stored is None:
            if self._strict_mode:
                raise PermissionError(f"Zero-Trust Violation: Unknown component '{name}' blocked.")
            log.warning("Zero-Trust: denying unknown component '%s' (dev mode).", name)
            return False

        computed = hashlib.sha3_256(data).hexdigest()
        self.record_measurement(name, computed)
        return _hmac.compare_digest(computed, stored.lower())

    # ------------------------------------------------------------------
    # Measurement log
    # ------------------------------------------------------------------
    def record_measurement(self, component: str, hash_hex: str) -> None:
        entry = {"component": component, "hash": hash_hex, "ts": time.time()}
        with self._lock:
            self._measurements.append(entry)

    def get_measurement_log(self) -> List[Dict]:
        with self._lock:
            return list(self._measurements)

# ---------------------------------------------------------------------------
# IPCAuthenticator (Upgraded with Anti-Replay Protection)
# ---------------------------------------------------------------------------
class IPCAuthenticator:
    """Signs and verifies IPC messages with HMAC-SHA3-256 and blocks replays.

    Wire format: :meth:`sign_message` returns a 64-character hex MAC over the
    canonical JSON encoding of the payload, keyed with a 512-bit HMAC key.
    The MAC is deliberately deterministic - the same message always yields the
    same string - because callers cache and compare signatures.  That same
    property is exactly why replay detection is required: an attacker who
    captures a ``(message, MAC)`` pair can re-send it verbatim without ever
    learning the key.

    Replay defence therefore lives in the verifier, not in the MAC:

    * :meth:`verify_message` remembers every MAC it accepts for
      ``replay_window`` seconds and rejects a second presentation of the same
      MAC, so a captured IPC frame cannot be re-delivered to this instance.
    * The MAC is compared *before* anything is remembered.  An attacker must
      not be able to poison the replay cache with forged MACs and thereby lock
      legitimate traffic out of the accept path (a denial-of-service).
    * :meth:`sign_envelope` / :meth:`verify_envelope` are the opt-in form for
      callers that need replay protection to survive a restart or to hold
      across receiver instances: the envelope binds a timestamp and a random
      nonce into the signed bytes, so it is unique per call and valid only
      inside its ``ttl``.

    Both comparisons use :func:`hmac.compare_digest` (constant time).

    Args:
        key: Optional HMAC key.  64 random bytes are generated when omitted.
        replay_window: Seconds an accepted MAC is remembered.  ``0`` disables
            the per-instance cache (stateless callers only).
        max_entries: Hard cap on remembered MACs; the oldest half is dropped
            when a flood would otherwise exceed it.
        envelope_ttl: Default validity of a signed envelope, in seconds.
    """

    DEFAULT_REPLAY_WINDOW = 300.0
    DEFAULT_MAX_ENTRIES = 100_000
    DEFAULT_ENVELOPE_TTL = 60.0

    def __init__(
        self,
        key: Optional[bytes] = None,
        *,
        replay_window: float = DEFAULT_REPLAY_WINDOW,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        envelope_ttl: float = DEFAULT_ENVELOPE_TTL,
    ) -> None:
        # 64-byte key (512-bit) for quantum-resistant security margin
        self._key = key if key is not None else secrets.token_bytes(64)
        self._replay_window = max(0.0, float(replay_window))
        self._max_entries = max(1, int(max_entries))
        self._envelope_ttl = max(0.0, float(envelope_ttl))
        self._seen: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._last_prune = time.monotonic()

    # -- MAC ------------------------------------------------------------
    def _mac(self, payload: dict) -> str:
        """Return the hex HMAC-SHA3-256 of *payload*'s canonical JSON form."""
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return _hmac.new(self._key, raw, hashlib.sha3_256).hexdigest()

    # -- deterministic API (documented; signature kept stable) ----------
    def sign_message(self, msg: dict) -> str:
        """Return HMAC-SHA3-256 hex digest of the JSON-encoded message."""
        return self._mac(msg)

    def verify_message(self, msg: dict, signature: str) -> bool:
        """Return True when *signature* is authentic and not a replay."""
        if not isinstance(signature, str):
            return False
        expected = self._mac(msg)
        # Constant-time compare FIRST: never remember an unauthenticated MAC.
        if not _hmac.compare_digest(expected, signature):
            return False
        return self._remember(signature)

    # -- envelope API (nonce + timestamp; survives a restart) -----------
    def sign_envelope(self, msg: dict, *, ttl: Optional[float] = None) -> dict:
        """Return a copy of *msg* carrying ``timestamp``, ``nonce`` and ``mac``.

        The caller's dict is never mutated.  ``ttl`` defaults to
        ``envelope_ttl`` and travels inside the signed bytes, so the receiver
        validates against the sender's intent rather than its own default.
        """
        envelope = dict(msg)
        envelope["timestamp"] = time.time()
        envelope["nonce"] = secrets.token_hex(16)
        envelope["ttl"] = self._envelope_ttl if ttl is None else max(0.0, float(ttl))
        envelope["mac"] = self._mac(envelope)
        return envelope

    def verify_envelope(self, envelope: dict) -> bool:
        """Return True when *envelope* is authentic, fresh and unused.

        Total function: malformed input yields False rather than raising,
        because envelopes arrive from untrusted peers.
        """
        if not isinstance(envelope, dict):
            return False
        mac = envelope.get("mac")
        nonce = envelope.get("nonce")
        timestamp = envelope.get("timestamp")
        if not isinstance(mac, str) or not isinstance(nonce, str):
            return False
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            return False
        try:
            body = {k: v for k, v in envelope.items() if k != "mac"}
            expected = self._mac(body)
        except (TypeError, ValueError):
            return False
        if not _hmac.compare_digest(expected, mac):
            return False
        ttl = body.get("ttl", self._envelope_ttl)
        if not isinstance(ttl, (int, float)) or isinstance(ttl, bool):
            return False
        age = time.time() - float(timestamp)
        # Reject stale envelopes *and* ones stamped implausibly far in the
        # future: otherwise a bad sender clock buys an attacker an unbounded
        # validity period.
        if age > float(ttl) or age < -float(ttl):
            log.warning("IPC replay blocked: envelope outside its validity window.")
            return False
        return self._remember(nonce)

    # -- shared replay cache --------------------------------------------
    def _remember(self, key: str) -> bool:
        """Record *key* as used; return False when it was already present."""
        if self._replay_window <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            if key in self._seen:
                log.warning("IPC replay blocked: duplicate frame rejected.")
                return False
            self._seen[key] = now
            return True

    def _prune(self, now: float) -> None:
        """Drop expired entries and enforce the hard cap.  Caller holds _lock."""
        if not self._seen:
            self._last_prune = now
            return
        overdue = now - self._last_prune >= self._replay_window
        if not overdue and len(self._seen) < self._max_entries:
            return
        cutoff = now - self._replay_window
        for key in [k for k, seen in self._seen.items() if seen <= cutoff]:
            del self._seen[key]
        if len(self._seen) >= self._max_entries:
            # Bounded-memory fallback under a flood: forget the oldest half.
            # Only ever reached once memory is already exhausted, and only
            # costs accuracy for MACs still inside the window.
            ordered = sorted(self._seen.items(), key=lambda item: item[1])
            for key, _ in ordered[: len(ordered) // 2]:
                del self._seen[key]
        self._last_prune = now

    def rotate_key(self) -> None:
        """Replace the current key with a fresh random one (invalidates old sigs)."""
        self._key = secrets.token_bytes(64)
        with self._lock:
            self._seen.clear()
            self._last_prune = time.monotonic()
        log.info("IPCAuthenticator: HMAC key rotated.")

# ---------------------------------------------------------------------------
# AIBehavioralMonitor (New Feature)
# ---------------------------------------------------------------------------
class AIBehavioralMonitor:
    """Heuristic, rule-based behavioural monitor - **not** a trained model.

    The historical name is kept because the GUI and the module docstring refer
    to it, but nothing here learns: the decision is a static deny-table of
    ``(process, capability)`` pairs.  It is documented that way so no caller
    mistakes it for anomaly detection with a model behind it.

    Three things make this an actual control rather than a log line:

    * **A quarantine that does something.**  :meth:`_trigger_quarantine`
      records the PID and revokes every capability the process holds in the
      ``SecuritySandbox`` it was constructed with, so
      ``sandbox.check_permission`` starts denying.  Without a sandbox the
      monitor still records and logs, and says in the reason that nothing was
      revoked.
    * **Sticky.**  Once quarantined, every later action for that PID is
      refused, including innocuous ones - a monitor that answers "safe" on the
      next call has not quarantined anything.
    * **Severity tiers.**  ``BLOCK`` pairs are impossible for that class of
      program and quarantine on the first hit; ``WARN`` pairs are merely
      unusual and need ``strike_threshold`` hits inside ``strike_window``, so
      ordinary behaviour cannot strip a process's capabilities on one event.

    Args:
        sandbox: Optional ``SecuritySandbox``.  When supplied, quarantine
            revokes the process's capabilities for real.
        strike_threshold: Hits on a ``WARN`` pair before quarantining.
        strike_window: Seconds after which a stale strike is forgotten, so a
            legitimate process cannot accumulate strikes over a long session
            while an attacker still cannot interleave clean actions to reset
            the count.
        rules: Optional rule table replacing :attr:`DEFAULT_RULES`.

    Note:
        ``process_name`` is supplied by the caller and is therefore spoofable.
        This is a defence-in-depth signal, **not** an authorization decision;
        the authoritative check remains ``SecuritySandbox.check_permission``.
    """

    BLOCK = "block"
    WARN = "warn"

    DEFAULT_RULES: Dict[Tuple[str, str], str] = {
        # Impossible for the program class -> quarantine immediately.
        ("text_editor", "network_access"): BLOCK,
        ("calculator", "kernel_module_load"): BLOCK,
        ("media_player", "process_injection"): BLOCK,
        # Unusual but legitimate (save games and configuration legitimately
        # land under a system path), so this warns and only quarantines on
        # repetition.  Downgraded from an unconditional block: that entry was
        # the false positive this row is about.
        ("game", "filesystem_write_system"): WARN,
    }

    STRIKE_WINDOW = 300.0

    def __init__(
        self,
        sandbox: Optional[object] = None,
        *,
        strike_threshold: int = 3,
        strike_window: float = STRIKE_WINDOW,
        rules: Optional[Dict[Tuple[str, str], str]] = None,
    ) -> None:
        self._sandbox = sandbox
        self._rules: Dict[Tuple[str, str], str] = dict(
            self.DEFAULT_RULES if rules is None else rules
        )
        self._strike_threshold = max(1, int(strike_threshold))
        self._strike_window = max(0.0, float(strike_window))
        self._strikes: Dict[int, Tuple[int, float]] = {}
        self._quarantined: Dict[int, str] = {}
        self._revoked: Dict[int, Set[str]] = {}
        # RLock: analyze_action holds it while calling _trigger_quarantine.
        self.lock = threading.RLock()

    # -- rule table -----------------------------------------------------
    @property
    def suspicious_patterns(self) -> frozenset:
        """The ``BLOCK``-severity pairs (read-only compatibility view)."""
        return frozenset(p for p, sev in self._rules.items() if sev == self.BLOCK)

    def add_rule(self, process_name: str, capability: str, severity: str = BLOCK) -> None:
        """Add or re-tune a rule.  *severity* is ``BLOCK`` or ``WARN``."""
        if severity not in (self.BLOCK, self.WARN):
            raise ValueError("severity must be BLOCK or WARN")
        with self.lock:
            self._rules[(str(process_name).lower(), str(capability))] = severity

    # -- evaluation -----------------------------------------------------
    def analyze_action(self, pid: int, process_name: str, action: str, resource: str) -> bool:
        """Return True when the action may proceed, False when it must not.

        A rule fires when either *action* or *resource* names the capability:
        in this API both are short capability identifiers (``network_access``,
        ``kernel_module_load``), not filesystem paths.

        A PID already under quarantine is refused unconditionally.
        """
        name = str(process_name).lower()
        with self.lock:
            if pid in self._quarantined:
                return False
            severity = None
            for key in ((name, action), (name, resource)):
                if key in self._rules:
                    severity = self._rules[key]
                    break
            if severity is None:
                return True
            if severity == self.BLOCK:
                self._trigger_quarantine(
                    pid, process_name, f"Blocked capability {action!r} on {resource!r}"
                )
                return False
            count, last = self._strikes.get(pid, (0, float("-inf")))
            if time.monotonic() - last > self._strike_window:
                count = 0
            count += 1
            self._strikes[pid] = (count, time.monotonic())
            if count < self._strike_threshold:
                log.warning(
                    "Behavioural monitor: PID %d (%s) %s on %s - strike %d/%d.",
                    pid, process_name, action, resource, count, self._strike_threshold,
                )
                return True
            self._trigger_quarantine(
                pid, process_name,
                f"Repeated suspicious capability {action!r} ({count} strikes)",
            )
            return False

    # -- quarantine -----------------------------------------------------
    def _trigger_quarantine(self, pid: int, process_name: str, reason: str) -> None:
        """Record the quarantine and revoke the process's sandbox capabilities.

        The stored reason carries the outcome, so ``quarantine_reason()`` says
        whether capabilities were actually revoked rather than leaving that
        fact in a log line nobody reads.
        """
        with self.lock:
            if pid in self._quarantined:
                return
            revoked, detail = self._revoke_capabilities(pid)
            record = f"{reason} [{detail}]"
            self._quarantined[pid] = record
        log.critical(
            "\U0001F6A8 [SECURITY] PID %d (%s) QUARANTINED: %s",
            pid, process_name, record,
        )

    def _revoke_capabilities(self, pid: int) -> Tuple[Set[str], str]:
        """Revoke every capability *pid* holds; return ``(revoked, detail)``."""
        sandbox = self._sandbox
        if sandbox is None:
            return set(), "no sandbox attached - capabilities NOT revoked"
        records = getattr(sandbox, "processes", None)
        if not isinstance(records, dict) or pid not in records:
            return set(), "PID not registered in sandbox - capabilities NOT revoked"
        held = set(getattr(records[pid], "permissions", ()) or ())
        for capability in held:
            try:
                sandbox.revoke_permission(pid, capability)
            except Exception:  # pragma: no cover - defensive
                log.warning("Failed to revoke %r from PID %d.", capability, pid)
        self._revoked[pid] = held
        return held, f"revoked {len(held)} capability/ies"

    def is_quarantined(self, pid: int) -> bool:
        """Return True when *pid* is under quarantine."""
        with self.lock:
            return pid in self._quarantined

    def quarantine_reason(self, pid: int) -> Optional[str]:
        """Return the recorded reason for *pid*, or None."""
        with self.lock:
            return self._quarantined.get(pid)

    @property
    def quarantined_pids(self) -> Tuple[int, ...]:
        """PIDs currently under quarantine, sorted."""
        with self.lock:
            return tuple(sorted(self._quarantined))

    def quarantine(self, pid: int, reason: str = "manual quarantine") -> None:
        """Quarantine *pid* explicitly; same effect as a rule hit."""
        self._trigger_quarantine(pid, f"pid:{pid}", reason)

    def release(self, pid: int) -> bool:
        """Lift a quarantine and restore the revoked capabilities.

        Returns True when *pid* had been quarantined.  Grants are restored
        additively, so a capability re-granted while the process was
        quarantined is not lost.
        """
        with self.lock:
            if pid not in self._quarantined:
                return False
            del self._quarantined[pid]
            self._strikes.pop(pid, None)
            revoked = self._revoked.pop(pid, set())
        for capability in revoked:
            try:
                self._sandbox.grant_permission(pid, capability)
            except Exception:  # pragma: no cover - defensive
                log.warning("Failed to restore %r to PID %d.", capability, pid)
        log.info("PID %d released from quarantine.", pid)
        return True

# --------------------------


# from __future__ import annotations
# import hashlib
# import hmac as _hmac
# import json
# import logging
# import os
# import secrets
# import threading
# import time
# from typing import Dict, List, Optional, Set

# log = logging.getLogger("UmerOS.Security")

# # ---------------------------------------------------------------------------
# # SecureBoot (Upgraded with Strict Mode)
# # ---------------------------------------------------------------------------
# class SecureBoot:
#     """Verifies kernel and service image integrity at boot time."""
    
#     def __init__(self, strict_mode: bool = True):
#         self._store: Dict[str, str] = {}
#         self._strict_mode = strict_mode
#         self._measurements: List[Dict] = []  # TPM-style measurement log
#         self._lock: threading.Lock = threading.Lock()
#         log.info("SecureBoot initialised (Strict Mode: %s)", strict_mode)

#     def load_trust_store(self, path: str) -> bool:
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

#     def verify_image(self, path: str, expected_hash: Optional[str] = None) -> bool:
#         name = os.path.basename(path)
#         stored = expected_hash or self._store.get(name)

#         if stored is None:
#             if self._strict_mode:
#                 raise PermissionError(f"🚨 Zero-Trust Violation: Unknown component '{name}' blocked.")
#             else:
#                 log.warning("Dev Mode: Allowing unknown component '%s'.", name)
#                 return True

#         try:
#             h = hashlib.sha3_512()  # Upgraded to SHA3-512 for quantum-resistant margin
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
#             log.critical("🚨 SecureBoot VIOLATION: '%s' hash mismatch! Boot aborted.", path)
#             raise PermissionError(f"Integrity check failed for {path}")
            
#         log.debug("SecureBoot OK: '%s'.", name)
#         return ok

#     def record_measurement(self, component: str, hash_hex: str) -> None:
#         entry = {"component": component, "hash": hash_hex, "ts": time.time()}
#         with self._lock:
#             self._measurements.append(entry)

# # ---------------------------------------------------------------------------
# # IPCAuthenticator (Upgraded with Anti-Replay Protection)
# # ---------------------------------------------------------------------------
# class IPCAuthenticator:
#     """Signs and verifies IPC messages with HMAC-SHA3-512 and nonce/timestamp."""
    
#     def __init__(self, key: Optional[bytes] = None):
#         # 64-byte key (512-bit) for quantum-resistant security margin
#         self._key = key if key is not None else secrets.token_bytes(64)
#         self._seen_nonces: Set[str] = set()
#         self._lock: threading.Lock = threading.Lock()
#         self._nonce_ttl = 60  # Seconds

#     def sign_message(self, msg: dict) -> dict:
#         msg = msg.copy()
#         msg['timestamp'] = time.time()
#         msg['nonce'] = secrets.token_hex(16)
        
#         raw = json.dumps(msg, sort_keys=True, separators=(",", ":")).encode()
#         mac = _hmac.new(self._key, raw, hashlib.sha3_512).hexdigest()
#         msg['mac'] = mac
#         return msg

#     def verify_message(self, msg: dict) -> bool:
#         with self._lock:
#             # 1. Check timestamp (prevent old messages)
#             if time.time() - msg.get('timestamp', 0) > self._nonce_ttl:
#                 log.warning("IPC Replay blocked: Message timestamp expired.")
#                 return False
            
#             # 2. Check nonce (prevent exact replay)
#             nonce = msg.get('nonce')
#             if nonce in self._seen_nonces:
#                 log.warning("IPC Replay blocked: Nonce already used.")
#                 return False
            
#             # 3. Verify MAC
#             mac = msg.pop('mac', None)
#             if not mac:
#                 return False
            
#             raw = json.dumps(msg, sort_keys=True, separators=(",", ":")).encode()
#             expected_mac = _hmac.new(self._key, raw, hashlib.sha3_512).hexdigest()
            
#             is_valid = _hmac.compare_digest(expected_mac, mac)
            
#             if is_valid:
#                 self._seen_nonces.add(nonce)
#                 # Memory management: clear old nonces periodically
#                 if len(self._seen_nonces) > 50000:
#                     self._seen_nonces.clear() 
                    
#             return is_valid

# # ---------------------------------------------------------------------------
# # AIBehavioralMonitor (New Feature)
# # ---------------------------------------------------------------------------
# class AIBehavioralMonitor:
#     """AI-driven anomaly detection for real-time threat mitigation."""
#     def __init__(self):
#         self.suspicious_patterns = {
#             ("text_editor", "network_access"),
#             ("calculator", "kernel_module_load"),
#             ("game", "filesystem_write_system"),
#             ("media_player", "process_injection")
#         }
#         self.lock = threading.Lock()

#     def analyze_action(self, pid: int, process_name: str, action: str, resource: str) -> bool:
#         """Evaluates if a process action is anomalous. Returns True if safe, False if quarantined."""
#         pattern = (process_name.lower(), action)
        
#         if pattern in self.suspicious_patterns or (process_name.lower(), resource) in self.suspicious_patterns:
#             self._trigger_quarantine(pid, process_name, f"Anomalous behavior: {action} on {resource}")
#             return False
            
#         return True

#     def _trigger_quarantine(self, pid: int, process_name: str, reason: str) -> None:
#         log.critical("🚨 [AI SECURITY] ANOMALY DETECTED: PID %d (%s) quarantined. Reason: %s", pid, process_name, reason)



# -------------------------------------------------------------------
# import os
# import json
# import time
# import secrets
# import hashlib
# import hmac
# import asyncio
# import logging
# from typing import Dict, List, Optional, Set

# logging.basicConfig(level=logging.INFO)
# log = logging.getLogger("UmerOS_Security")

# class SecurityViolationError(Exception):
#     """Raised when a Zero-Trust security policy is violated."""
#     pass

# # ---------------------------------------------------------------------------
# # SecureBoot
# # ---------------------------------------------------------------------------
# class SecureBoot:
#     """
#     Verifies kernel and service image integrity at boot time.
#     Enforces Zero-Trust: Unknown components are rejected in strict mode.
#     """

#     def __init__(self, strict_mode: bool = True):
#         self._store: Dict[str, str] = {}
#         self._strict_mode = strict_mode
#         self._measurements: List[Dict] = []  # TPM-style measurement log
#         self._lock = asyncio.Lock()
#         log.info("SecureBoot initialized (Strict Mode: %s)", strict_mode)

#     async def load_trust_store(self, path: str) -> bool:
#         """Load a JSON trust store mapping component names to SHA3-516 hex digests."""
#         try:
#             with open(path, encoding="utf-8") as fh:
#                 data = json.load(fh)
#             async with self._lock:
#                 self._store.update(data)
#             log.info("Trust store loaded from '%s' (%d entries).", path, len(data))
#             return True
#         except (OSError, json.JSONDecodeError) as exc:
#             log.error("Failed to load trust store '%s': %s", path, exc)
#             return False

#     async def verify_image(self, path: str, expected_hash: Optional[str] = None) -> bool:
#         """Hash a file and verify it against the trust store using SHA3-512."""
#         name = os.path.basename(path)
#         stored = expected_hash or self._store.get(name)

#         if stored is None:
#             if self._strict_mode:
#                 raise SecurityViolationError(f"Zero-Trust Violation: Unknown component '{name}' blocked.")
#             else:
#                 log.warning("Dev Mode: Allowing unknown component '%s'.", name)
#                 return True

#         try:
#             h = hashlib.sha3_512()
#             with open(path, "rb") as fh:
#                 for chunk in iter(lambda: fh.read(65536), b""):
#                     h.update(chunk)
#             computed = h.hexdigest()
#         except OSError as exc:
#             log.error("SecureBoot: Cannot read '%s': %s", path, exc)
#             return False

#         # Constant-time comparison
#         is_valid = hmac.compare_digest(computed, stored.lower())
#         await self.record_measurement(name, computed)
        
#         if not is_valid:
#             log.critical("🚨 SecureBoot VIOLATION: '%s' hash mismatch! Boot aborted.", path)
#             raise SecurityViolationError(f"Integrity check failed for {path}")
            
#         log.debug("SecureBoot OK: '%s'.", name)
#         return is_valid

#     async def record_measurement(self, component: str, hash_hex: str) -> None:
#         """Append a measurement to the TPM-style boot log."""
#         entry = {"component": component, "hash": hash_hex, "ts": time.time()}
#         async with self._lock:
#             self._measurements.append(entry)

# # ---------------------------------------------------------------------------
# # IPCAuthenticator (Quantum-Resistant Margin)
# # ---------------------------------------------------------------------------
# class IPCAuthenticator:
#     """
#     Signs and verifies IPC messages with HMAC-SHA3-512.
#     Includes nonce and timestamp to prevent Replay Attacks.
#     """

#     def __init__(self, key: Optional[bytes] = None):
#         # 64-byte key (512-bit) for quantum-resistant security margin
#         self._key = key if key is not None else secrets.token_bytes(64)
#         self._seen_nonces: Set[str] = set()
#         self._lock = asyncio.Lock()
#         self._nonce_ttl = 60  # Seconds

#     async def sign_message(self, msg: dict) -> dict:
#         """Compute HMAC-SHA3-512 over a dict payload with anti-replay fields."""
#         msg = msg.copy()  # Avoid mutating original
#         msg['timestamp'] = time.time()
#         msg['nonce'] = secrets.token_hex(16)
        
#         raw = json.dumps(msg, sort_keys=True, separators=(",", ":")).encode()
#         mac = hmac.new(self._key, raw, hashlib.sha3_512).hexdigest()
#         msg['mac'] = mac
#         return msg

#     async def verify_message(self, msg: dict) -> bool:
#         """Verify a previously signed dict, checking for replay attacks."""
#         async with self._lock:
#             # 1. Check timestamp (prevent old messages)
#             if time.time() - msg.get('timestamp', 0) > self._nonce_ttl:
#                 log.warning("IPC Replay blocked: Message timestamp expired.")
#                 return False
            
#             # 2. Check nonce (prevent exact replay)
#             nonce = msg.get('nonce')
#             if nonce in self._seen_nonces:
#                 log.warning("IPC Replay blocked: Nonce already used.")
#                 return False
            
#             # 3. Verify MAC
#             mac = msg.pop('mac', None)
#             if not mac:
#                 return False
            
#             raw = json.dumps(msg, sort_keys=True, separators=(",", ":")).encode()
#             expected_mac = hmac.new(self._key, raw, hashlib.sha3_512).hexdigest()
            
#             is_valid = hmac.compare_digest(expected_mac, mac)
            
#             if is_valid:
#                 self._seen_nonces.add(nonce)
#                 # Memory management: clear old nonces periodically
#                 if len(self._seen_nonces) > 50000:
#                     self._seen_nonces.clear() 
                    
#             return is_valid

#     async def rotate_key(self) -> None:
#         """Generate a new random HMAC key for forward secrecy."""
#         self._key = secrets.token_bytes(64)
#         self._seen_nonces.clear()
#         log.info("IPCAuthenticator: HMAC key rotated for forward secrecy.")

# # ---------------------------------------------------------------------------
# # AI Behavioral Monitor (New Feature)
# # ---------------------------------------------------------------------------
# class AIBehavioralMonitor:
#     """
#     AI-driven anomaly detection for real-time threat mitigation.
#     Monitors permission requests and flags deviations from baseline behavior.
#     """
#     def __init__(self):
#         self.suspicious_patterns = {
#             ("text_editor", "network_access"),
#             ("calculator", "kernel_module_load"),
#             ("game", "filesystem_write_system"),
#             ("media_player", "process_injection")
#         }
#         self.lock = asyncio.Lock()

#     async def analyze_action(self, pid: int, process_name: str, action: str, resource: str) -> bool:
#         """
#         Evaluates if a process action is anomalous.
#         Returns True if safe, False if quarantined.
#         """
#         # In a production OS, this would query an ONNX LSTM model.
#         # Here, we use heuristic rule-based AI simulation.
#         pattern = (process_name.lower(), action)
        
#         if pattern in self.suspicious_patterns or (process_name.lower(), resource) in self.suspicious_patterns:
#             await self._trigger_quarantine(pid, process_name, f"Anomalous behavior: {action} on {resource}")
#             return False
            
#         return True

#     async def _trigger_quarantine(self, pid: int, process_name: str, reason: str) -> None:
#         """Automatically isolates the offending process."""
#         log.critical("🚨 [AI SECURITY] ANOMALY DETECTED: PID %d (%s) quarantined. Reason: %s", pid, process_name, reason)
#         # Hook: In the full kernel, this would call sandbox.revoke_all_permissions(pid)
        # and notify the AI Orchestrator to spawn a clean replacement instance.


# -------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def compute_sha3_256(data: bytes) -> str:
    """Compute SHA3-256 hex digest.

    Args:
        data: Input bytes.

    Returns:
        64-character lowercase hex string.
    """
    return hashlib.sha3_256(data).hexdigest()


def compute_sha3_512(data: bytes) -> str:
    """Compute SHA3-512 hex digest.

    Args:
        data: Input bytes.

    Returns:
        128-character lowercase hex string.
    """
    return hashlib.sha3_512(data).hexdigest()
