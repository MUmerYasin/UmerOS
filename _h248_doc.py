"""H248 follow-up: document that action and resource are capability names."""
from __future__ import annotations

import io

SEC = "security/security.py"

with io.open(SEC, "r", encoding="utf-8", newline="") as fh:
    sec = fh.read()
original = sec

old = (
    '        """Return True when the action may proceed, False when it must not.\r\n'
    "\r\n"
    "        A PID already under quarantine is refused unconditionally.\r\n"
    '        """\r\n'
)
new = (
    '        """Return True when the action may proceed, False when it must not.\r\n'
    "\r\n"
    "        A rule fires when either *action* or *resource* names the capability:\r\n"
    "        in this API both are short capability identifiers (``network_access``,\r\n"
    "        ``kernel_module_load``), not filesystem paths.\r\n"
    "\r\n"
    "        A PID already under quarantine is refused unconditionally.\r\n"
    '        """\r\n'
)
assert sec.count(old) == 1, "analyze_action docstring anchor"
sec = sec.replace(old, new)
assert sec != original
assert "not filesystem paths" in sec

with io.open(SEC, "w", encoding="utf-8", newline="") as fh:
    fh.write(sec)

raw = open(SEC, "rb").read()
assert raw.count(b"\n") == raw.count(b"\r\n"), "bare LF introduced"
compile(raw, SEC, "exec")
print("security.py: %d -> %d chars, CRLF intact, compiles" % (len(original), len(sec)))
