"""H247 applier: real IPC anti-replay + correct digest claims.

Idempotent-ish: asserts every intended write landed, aborts otherwise.
CRLF is preserved (files are pure CRLF; we read/write with newline='').
"""
from __future__ import annotations

import io
import sys

SEC = r"security/security.py"
GUI = r"ui/umeros_gui.py"


def read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def crlf(block: str) -> str:
    """Convert a \n-authored block to the file's CRLF convention."""
    return block.replace("\r\n", "\n").replace("\n", "\r\n")


# ---------------------------------------------------------------------------
# 1. security/security.py — module docstring claims (two false statements)
# ---------------------------------------------------------------------------
sec = read(SEC)
original_sec = sec

old_line21 = "  IPCAuthenticator  — HMAC-SHA256 message signing & verification.\r\n"
new_line21 = (
    "  IPCAuthenticator  — HMAC-SHA3-256 signing, replay-protected verification.\r\n"
)
assert sec.count(old_line21) == 1, "line 21 anchor"
sec = sec.replace(old_line21, new_line21)

old_line35 = "- IPCAuthenticator (HMAC-SHA3-512 message signing & anti-replay)\r\n"
new_line35 = "- IPCAuthenticator (HMAC-SHA3-256 message signing & anti-replay)\r\n"
assert sec.count(old_line35) == 1, "line 35 anchor"
sec = sec.replace(old_line35, new_line35)

# ---------------------------------------------------------------------------
# 2. security/security.py — replace the live IPCAuthenticator class body
# ---------------------------------------------------------------------------
START = "\nclass IPCAuthenticator:\r\n"
assert sec.count(START) == 1, "exactly one live class definition"
start = sec.index(START) + 1

END_ANCHOR = "        self._key = secrets.token_bytes(64)\r\n"
end = sec.index(END_ANCHOR, start) + len(END_ANCHOR)
region = sec[start:end]
assert "# class IPCAuthenticator" not in region, "must not span the dead code"
assert "def rotate_key" in region, "must include rotate_key"
assert "def verify_message" in region, "must include verify_message"
assert region.count("def sign_message") == 1

NEW_CLASS = crlf('''class IPCAuthenticator:
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
''')

sec = sec[:start] + NEW_CLASS + sec[end:]

assert sec != original_sec, "security.py must have changed"
assert sec.count(START) == 1
assert "hashlib.sha3_256" in sec
assert "HMAC-SHA3-512.\"\"\"" not in sec, "the class docstring lie must be gone"
assert "HMAC-SHA3-256" in sec
assert sec.count("\n    def verify_message") == 1, "exactly one live verify_message"
assert "def sign_envelope" in sec and "def verify_envelope" in sec
write(SEC, sec)
print("security.py: %d -> %d bytes" % (len(original_sec), len(sec)))

# ---------------------------------------------------------------------------
# 3. ui/umeros_gui.py — the GUI repeated the same false claim
# ---------------------------------------------------------------------------
gui = read(GUI)
original_gui = gui
old_gui = '"• IPCAuthenticator — HMAC-SHA3-512 sessions\\n"'
new_gui = '"• IPCAuthenticator — HMAC-SHA3-256 sessions (replay-protected)\\n"'
assert gui.count(old_gui) == 1, "gui anchor"
gui = gui.replace(old_gui, new_gui)
assert gui != original_gui
write(GUI, gui)
print("umeros_gui.py: %d -> %d bytes" % (len(original_gui), len(gui)))

# ---------------------------------------------------------------------------
# 4. verify: compile both files, CRLF preserved, no stray LF
# ---------------------------------------------------------------------------
for path in (SEC, GUI):
    raw = open(path, "rb").read()
    lf = raw.count(b"\n")
    crlf = raw.count(b"\r\n")
    assert lf == crlf, "%s has %d bare LF" % (path, lf - crlf)
    compile(raw, path, "exec")
    print("%s: %d lines, CRLF intact, compiles" % (path, crlf))

print("OK")
