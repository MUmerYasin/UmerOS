"""H248 recon: confirm the live class boundaries before writing the applier."""
from __future__ import annotations

import io

PATH = "security/security.py"

with io.open(PATH, "r", encoding="utf-8", newline="") as fh:
    text = fh.read()

print("total chars:", len(text))
print("bare LF:", text.count("\n") - text.count("\r\n"))

start_anchor = "\nclass AIBehavioralMonitor:\r\n"
print("live class anchor count:", text.count(start_anchor))

start = text.index(start_anchor) + 1
# End: the closing log.critical line of _trigger_quarantine, found by its marker.
marker = "[AI SECURITY] ANOMALY DETECTED"
mid = text.index(marker, start)
end = text.index("\r\n", mid) + 2
region = text[start:end]

print("region length:", len(region))
print("region starts:", repr(region[:45]))
print("region ends:", repr(region[-60:]))
print("has commented code:", "# class" in region)
print("def count:", region.count("def "))
print("--- region verbatim ---")
print(region)
print("--- after region ---")
print(repr(text[end:end + 40]))
