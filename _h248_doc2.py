"""H248 follow-up 2: make the quarantine record state what actually happened.

`quarantine_reason()` should tell an operator whether capabilities were really
revoked, not leave that fact only in a log line.
"""
from __future__ import annotations

import io

SEC = "security/security.py"

with io.open(SEC, "r", encoding="utf-8", newline="") as fh:
    sec = fh.read()
original = sec


def crlf(block: str) -> str:
    return block.replace("\r\n", "\n").replace("\n", "\r\n")


OLD = crlf('''    def _trigger_quarantine(self, pid: int, process_name: str, reason: str) -> None:
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
''')

NEW = crlf('''    def _trigger_quarantine(self, pid: int, process_name: str, reason: str) -> None:
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
            "\\U0001F6A8 [SECURITY] PID %d (%s) QUARANTINED: %s",
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
''')

assert sec.count(OLD) == 1, "quarantine block anchor"
sec = sec.replace(OLD, NEW)
assert sec != original
assert "PID not registered in sandbox" in sec
assert "return set(), f\"revoked" not in sec

with io.open(SEC, "w", encoding="utf-8", newline="") as fh:
    fh.write(sec)

raw = open(SEC, "rb").read()
assert raw.count(b"\n") == raw.count(b"\r\n"), "bare LF introduced"
compile(raw, SEC, "exec")
print("security.py: %d -> %d chars, CRLF intact, compiles" % (len(original), len(sec)))
