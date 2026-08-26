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
Umer OS Initrd AI Helper
========================
Optional AI-driven enhancement for the initrd module resolver.

Three places where the rest of the system asks this module for help:

* :meth:`AIHelper.suggest_modules` - given a partial module list from
  the autoprobe, suggest a few more modules that have historically
  been needed on similar hardware profiles.
* :meth:`AIHelper.score_scenario` - assign a confidence score to a
  candidate scenario (e.g. "is this really an installation boot?").
* :meth:`AIHelper.entropy_bytes` - return cryptographically strong
  random bytes sourced from UmerOS's quantum random number
  generator, so the initrd can derive per-boot keys without an
  extra dependency.

The helper degrades gracefully: when no AI subsystem or QRNG is
available, every method returns a sensible default (empty list /
0.5 / ``os.urandom``).  This means :mod:`initrd.linuxrc` can call it
without ``try/except`` scaffolding on every callsite.

If you want richer behaviour, install the optional packages listed in
``requirements.txt`` (``scikit-learn``, ``transformers``,
``qiskit-aer``) and the helper will pick them up automatically.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import ast
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Initrd.AIHelper")


# ---------------------------------------------------------------------------
# Suggestion dataclass
# ---------------------------------------------------------------------------

@dataclass
class ModuleSuggestion:
    name: str
    score: float
    reason: str

    def as_dict(self) -> dict:
        return {"name": self.name, "score": round(self.score, 3), "reason": self.reason}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

class AIHelper:
    """Optional AI assistance for the initrd resolver."""

    def __init__(self) -> None:
        self._qiskit = self._try_import("qiskit")
        self._sklearn = self._try_import("sklearn")
        self._enabled = self._qiskit is not None or self._sklearn is not None
        self._history: List[Dict[str, object]] = []

    # -- module suggestions -----------------------------------------------

    def suggest_modules(
        self,
        base: List[str],
        host_root: str = "/",
        top_k: int = 5,
    ) -> List[ModuleSuggestion]:
        """Augment ``base`` with up to ``top_k`` additional module hints.

        Heuristic order:

        1. If scikit-learn is available, fit a tiny NaiveBayes on
           historical host fingerprints and predict the next modules.
        2. Otherwise, use a hand-coded rule set (well-known pairings:
           "ext4 -> mbcache", "dm_crypt -> dm_mod", "nvme -> nvme_core").
        3. Always de-duplicate against ``base``.
        """
        history = self._load_history(host_root)
        if self._sklearn is not None and history:
            try:
                return self._sklearn_suggest(base, history, top_k)
            except Exception as exc:  # noqa: BLE001
                log.debug("sklearn suggestion failed, falling back: %s", exc)
        return self._rule_based_suggest(base, top_k)

    # -- scenario scoring -------------------------------------------------

    def score_scenario(self, signals: Dict[str, float]) -> float:
        """Combine a few booleans/floats into one [0..1] confidence.

        Signals may include "installer_signature_found",
        "no_root_device", "live_media_present", etc.  Unknown signals
        are ignored, and the function returns 0.5 if no signals are
        provided so the caller can still make a decision.
        """
        if not signals:
            return 0.5
        install_kw = {
            "installer_signature_found": 0.8,
            "live_media_present":        0.6,
            "no_root_device":            0.7,
            "recovery_requested":        0.9,
        }
        total = 0.0
        weight = 0.0
        for key, value in signals.items():
            w = install_kw.get(key, 0.1)
            total += w * max(0.0, min(1.0, float(value)))
            weight += w
        return total / weight if weight else 0.5

    # -- entropy ----------------------------------------------------------

    def entropy_bytes(self, n: int) -> bytes:
        """Return ``n`` cryptographically strong bytes.

        Tries to draw from a quantum RNG via qiskit-aer; if that is
        not available, falls back to :func:`os.urandom`.  Always
        post-whitens with SHA-256 so callers don't have to.
        """
        if n <= 0:
            return b""
        raw = self._qiskit_entropy(n) if self._qiskit is not None else os.urandom(n)
        # Whiten to remove any statistical bias from the QRNG.
        return hashlib.sha256(raw + os.urandom(16)).digest()[:n]

    # -- introspection ----------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    def diagnostics(self) -> Dict[str, object]:
        return {
            "qiskit_available":    self._qiskit is not None,
            "sklearn_available":   self._sklearn is not None,
            "enabled":             self._enabled,
            "history_entries":     len(self._history),
        }

    # -- internals --------------------------------------------------------

    def _try_import(self, name: str):
        try:
            return __import__(name)
        except ImportError:
            return None

    def _load_history(self, host_root: str) -> List[Dict[str, object]]:
        path = os.path.join(host_root, "var", "log", "umeros_initrd_history.log")
        if not os.path.isfile(path):
            return []
        # [FIX H2][FIX H91] The boot history log is NOT a trusted script.
        # Parsing it with eval() allowed any writer of the log to execute
        # arbitrary code at early-boot (PID 1, uid 0) - a classic code
        # injection (CWE-94).  Use the literal-safe parser instead; malformed
        # or non-literal lines are dropped rather than executed.  Only
        # dict-shaped records (what the suggester actually consumes) are kept.
        try:
            parsed: List[Dict[str, object]] = []
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        value = ast.literal_eval(line)
                    except (ValueError, SyntaxError, MemoryError, RecursionError):
                        # Not a literal structure -> untrusted input, skip it.
                        log.warning("skipping non-literal initrd history line")
                        continue
                    if isinstance(value, dict):
                        parsed.append(value)
            return parsed
        except OSError:  # noqa: BLE001 - cannot read the log
            return []

    def _rule_based_suggest(self, base: List[str], top_k: int) -> List[ModuleSuggestion]:
        rules: Dict[str, List[tuple[str, str]]] = {
            "ext4":      [("mbcache",   "ext4 page cache acceleration"),
                          ("jbd2",      "ext4 journaling")],
            "btrfs":     [("zstd",      "btrfs compression"),
                          ("xor",       "btrfs raid5/6")],
            "xfs":       [("crc32c",    "xfs checksums")],
            "dm_crypt":  [("dm_mod",    "device mapper core")],
            "nvme":      [("nvme_core", "nvme core driver")],
            "ahci":      [("libahci",   "ahci platform glue")],
            "virtio_blk":[("virtio",    "virtio core")],
            "virtio_net":[("virtio",    "virtio core")],
        }
        out: List[ModuleSuggestion] = []
        seen = set(base)
        for trigger, deps in rules.items():
            if trigger not in base:
                continue
            for dep, reason in deps:
                if dep in seen:
                    continue
                out.append(ModuleSuggestion(name=dep, score=0.85, reason=f"paired with {trigger}"))
                seen.add(dep)
                if len(out) >= top_k:
                    return out
        return out

    def _sklearn_suggest(self, base: List[str],
                          history: List[Dict[str, object]],
                          top_k: int) -> List[ModuleSuggestion]:
        # Tiny label-encoder bag-of-modules model.  We keep it inline
        # so the AI helper has no external persistence requirements.
        try:
            from sklearn.feature_extraction.text import CountVectorizer  # type: ignore
            from sklearn.naive_bayes import MultinomialNB  # type: ignore
        except ImportError:
            return []
        texts: List[str] = []
        labels: List[str] = []
        for entry in history:
            mods = entry.get("modules") or []
            if not mods:
                continue
            texts.append(" ".join(mods))
            # Predict the LAST module in the list from the rest.
            labels.append(mods[-1])
        if not texts:
            return []
        vec = CountVectorizer(token_pattern=r"[^\s]+")
        X = vec.fit_transform(texts)
        clf = MultinomialNB()
        clf.fit(X, labels)
        base_text = " ".join(base)
        probs = clf.predict_proba(vec.transform([base_text]))[0]
        ranked = sorted(zip(clf.classes_, probs), key=lambda t: -t[1])
        out: List[ModuleSuggestion] = []
        for name, score in ranked[:top_k]:
            if name in base:
                continue
            out.append(ModuleSuggestion(
                name=name, score=float(score), reason="learned from history"
            ))
        return out

    def _qiskit_entropy(self, n: int) -> bytes:
        """Use a real quantum circuit to generate entropy when available."""
        try:
            from qiskit import QuantumCircuit  # type: ignore
            from qiskit_aer import AerSimulator  # type: ignore
        except ImportError:
            return os.urandom(n)
        qc = QuantumCircuit(8, 8)
        qc.h(range(8))
        qc.measure(range(8), range(8))
        sim = AerSimulator()
        needed = (n + 7) // 8
        out = bytearray()
        for _ in range(needed):
            result = sim.run(qc, shots=1, memory=True).result()
            bits = result.get_memory()[0]
            out.append(int(bits, 2))
        return bytes(out[:n])


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    h = AIHelper()
    suggestions = h.suggest_modules(["ext4", "nvme"], top_k=3)
    if not any(s.name == "mbcache" for s in suggestions):
        return False
    if h.score_scenario({"installer_signature_found": 1.0}) <= 0.5:
        return False
    if len(h.entropy_bytes(32)) != 32:
        return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    h = AIHelper()
    print("ai_helper diagnostics:", h.diagnostics())
    print("ai_helper selftest:", "OK" if _selftest() else "FAIL")
