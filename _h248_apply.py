"""H248 applier: make the behavioural monitor honest, and its quarantine real.

Premise (drift-recon): TRUE.
  * "AI-driven" is false - it is a 4-entry static deny-table.
  * `_trigger_quarantine` only calls `log.critical`; nothing is isolated.
  * The rules flag ordinary behaviour, and an already-quarantined PID is
    reported "safe" on its next action.

CRLF preserved; every write asserted.
"""
from __future__ import annotations

import io

SEC = "security/security.py"
GUI = "ui/umeros_gui.py"


def read(path: str) -> str:
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def crlf(block: str) -> str:
    return block.replace("\r\n", "\n").replace("\n", "\r\n")


# ---------------------------------------------------------------------------
# 1. security/security.py
# ---------------------------------------------------------------------------
sec = read(SEC)
original = sec

# 1a. module docstring: stop claiming "AI".
old = "Implements Secure Boot, IPC Authentication (with replay protection), and AI Behavioral Monitoring.\r\n"
new = "Implements Secure Boot, IPC Authentication (with replay protection), and heuristic behavioural monitoring.\r\n"
assert sec.count(old) == 1, "docstring line 29 anchor"
sec = sec.replace(old, new)

old = "- AIBehavioralMonitor (Real-time anomaly detection)\r\n"
new = "- AIBehavioralMonitor (heuristic rule-based behavioural monitor; no model)\r\n"
assert sec.count(old) == 1, "docstring line 36 anchor"
sec = sec.replace(old, new)

# 1b. typing: Tuple is needed for the rule-table annotation.
old = "\r\nfrom typing import Dict, List, Optional, Set\r\n"
new = "\r\nfrom typing import Dict, List, Optional, Set, Tuple\r\n"
assert sec.count(old) == 1, "typing import anchor (line-anchored: the commented copies also match)"
sec = sec.replace(old, new)

# 1c. replace the live class body.
START = "\nclass AIBehavioralMonitor:\r\n"
assert sec.count(START) == 1, "exactly one live class"
start = sec.index(START) + 1
marker = "[AI SECURITY] ANOMALY DETECTED"
mid = sec.index(marker, start)
end = sec.index("\r\n", mid) + 2
region = sec[start:end]
assert "# class" not in region, "must not span the dead code"
assert region.count("def ") == 3, "expected __init__ + 2 methods"
assert "suspicious_patterns" in region and "log.critical" in region

NEW_CLASS = crlf('''class AIBehavioralMonitor:
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
        """Record the quarantine and revoke the process's sandbox capabilities."""
        with self.lock:
            if pid in self._quarantined:
                return
            self._quarantined[pid] = reason
            revoked = self._revoke_capabilities(pid)
        detail = (
            f"revoked {len(revoked)} capability/ies"
            if revoked
            else "no sandbox attached - capabilities NOT revoked"
        )
        log.critical(
            "\\U0001F6A8 [SECURITY] PID %d (%s) QUARANTINED: %s (%s)",
            pid, process_name, reason, detail,
        )

    def _revoke_capabilities(self, pid: int) -> Set[str]:
        """Revoke every capability *pid* holds in the attached sandbox."""
        sandbox = self._sandbox
        if sandbox is None:
            return set()
        records = getattr(sandbox, "processes", None)
        if not isinstance(records, dict) or pid not in records:
            return set()
        held = set(getattr(records[pid], "permissions", ()) or ())
        for capability in held:
            try:
                sandbox.revoke_permission(pid, capability)
            except Exception:  # pragma: no cover - defensive
                log.warning("Failed to revoke %r from PID %d.", capability, pid)
        self._revoked[pid] = held
        return held

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
''')

sec = sec[:start] + NEW_CLASS + sec[end:]

assert sec != original, "security.py must change"
assert sec.count(START) == 1
assert '\n    """AI-driven anomaly detection' not in sec, "the live AI claim must be gone"
assert "heuristic" in sec.lower()
assert "def release" in sec and "def is_quarantined" in sec
assert "def _revoke_capabilities" in sec
assert sec.count("\n    def analyze_action") == 1
write(SEC, sec)
print("security.py: %d -> %d chars" % (len(original), len(sec)))

# ---------------------------------------------------------------------------
# 2. ui/umeros_gui.py - the GUI repeated the "AI" framing
# ---------------------------------------------------------------------------
gui = read(GUI)
gui_original = gui
old = '"• AIBehavioralMonitor — anomaly detection"'
new = '"• AIBehavioralMonitor — heuristic anomaly rules (no model)"'
assert gui.count(old) == 1, "gui anchor"
gui = gui.replace(old, new)
assert gui != gui_original
write(GUI, gui)
print("umeros_gui.py: %d -> %d chars" % (len(gui_original), len(gui)))

# ---------------------------------------------------------------------------
# 3. verify
# ---------------------------------------------------------------------------
for path in (SEC, GUI):
    raw = open(path, "rb").read()
    lf, crlf_count = raw.count(b"\n"), raw.count(b"\r\n")
    assert lf == crlf_count, "%s has %d bare LF" % (path, lf - crlf_count)
    compile(raw, path, "exec")
    print("%s: %d lines, CRLF intact, compiles" % (path, crlf_count))

print("OK")
