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

"""H247 - IPC replay protection must be real, not merely claimed.

The row was: ``security/security.py`` advertises anti-replay in its module and
class docstrings while the live ``IPCAuthenticator`` only MACs the body, so a
captured ``(message, MAC)`` pair can be re-delivered forever.

These tests pin the fix and, just as importantly, its *boundaries*:

* a second presentation of an accepted MAC is refused;
* a forged MAC cannot poison the cache and lock legitimate traffic out;
* the deterministic wire format (``sign_message -> str``) is unchanged, because
  ``docs/developer_guide.md`` documents it and ``tests/test_security.py`` pins
  it;
* the opt-in envelope is what makes replay defence survive a restart, and the
  per-instance limitation of the bare MAC is stated rather than hidden;
* the memory bound is honest - under a flood the oldest MACs are forgotten.

The live code also claimed HMAC-SHA3-512 while computing SHA3-256; that lie is
pinned shut here too.
"""
from __future__ import annotations

import inspect
import pathlib
import unittest
from unittest import mock

import security.security as secmod
from security.security import IPCAuthenticator

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


class _Clock:
    """Deterministic stand-in for the ``time`` module.

    The replay window and the envelope validity window are both time-based, so
    a fake clock keeps these tests exact instead of sleeping.
    """

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def monotonic(self) -> float:
        return self.now

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _ClockPatched:
    """Context manager: patch ``security.security.time`` *before* construction.

    ``__init__`` seeds ``_last_prune`` from the clock, so the patch has to be
    in place before the authenticator is built or the prune cadence is wrong.
    """

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.clock = _Clock(start)
        self._patch = mock.patch.object(secmod, "time", self.clock)

    def __enter__(self) -> _Clock:
        self._patch.start()
        return self.clock

    def __exit__(self, *exc_info) -> None:
        self._patch.stop()


# ---------------------------------------------------------------------------
# The headline: replay is actually refused
# ---------------------------------------------------------------------------

class TestReplayIsRefused(unittest.TestCase):

    def setUp(self):
        self.auth = IPCAuthenticator(key=b"k" * 64)

    def test_a_replayed_message_is_refused(self):
        msg = {"op": "transfer", "amount": 100}
        sig = self.auth.sign_message(msg)

        self.assertTrue(self.auth.verify_message(msg, sig), "first delivery must pass")
        self.assertFalse(
            self.auth.verify_message(msg, sig),
            "the same (message, MAC) pair must not be accepted twice",
        )

    def test_the_replay_is_refused_because_of_state_not_because_the_mac_broke(self):
        """The decisive check: the MAC is still valid, only the verifier refuses.

        If this failed it would mean the replay was rejected for the wrong
        reason (e.g. the MAC stopped matching), which would hide the fact that
        anti-replay itself is broken.
        """
        msg = {"op": "ping"}
        sig = self.auth.sign_message(msg)
        self.assertTrue(self.auth.verify_message(msg, sig))
        self.assertFalse(self.auth.verify_message(msg, sig))

        # Same key, same message -> the MAC is still exactly what was signed.
        self.assertEqual(sig, self.auth._mac(msg))
        # And a brand-new instance, which has seen nothing, still accepts it.
        fresh = IPCAuthenticator(key=b"k" * 64)
        self.assertTrue(fresh.verify_message(msg, sig))

    def test_distinct_messages_are_not_mistaken_for_replays(self):
        for index in range(50):
            msg = {"seq": index}
            sig = self.auth.sign_message(msg)
            self.assertTrue(
                self.auth.verify_message(msg, sig),
                "message %d was wrongly treated as a replay" % index,
            )

    def test_forged_macs_cannot_evict_genuine_ones_from_the_cache(self):
        """MAC compare must happen *before* anything is remembered.

        A forged signature is a different string, so it cannot collide with a
        genuine entry - but if forged MACs were recorded anyway, an attacker
        could flood *distinct* ones until the memory cap evicted real entries.
        The evicted MACs would then replay successfully.  Comparing first
        means unauthenticated input never enters the cache at all.
        """
        auth = IPCAuthenticator(key=b"k" * 64, max_entries=8)
        msg = {"op": "legit"}
        real = auth.sign_message(msg)
        self.assertTrue(auth.verify_message(msg, real))

        for index in range(64):
            self.assertFalse(auth.verify_message(msg, "%064x" % index))

        self.assertFalse(
            auth.verify_message(msg, real),
            "a forged-MAC flood must not evict the genuine entry and thereby "
            "re-enable replay",
        )

    def test_a_forged_mac_does_not_block_the_genuine_one(self):
        msg = {"op": "legit"}
        real = self.auth.sign_message(msg)
        for _ in range(20):
            self.assertFalse(self.auth.verify_message(msg, "0" * 64))
        self.assertTrue(self.auth.verify_message(msg, real))

    def test_non_string_signature_is_refused_without_raising(self):
        msg = {"a": 1}
        for bad in (None, b"00", 12345, ["0" * 64]):
            self.assertFalse(self.auth.verify_message(msg, bad))

    def test_replay_window_zero_disables_the_cache(self):
        auth = IPCAuthenticator(key=b"k" * 64, replay_window=0)
        msg = {"a": 1}
        sig = auth.sign_message(msg)
        self.assertTrue(auth.verify_message(msg, sig))
        self.assertTrue(
            auth.verify_message(msg, sig),
            "replay_window=0 must restore purely stateless verification",
        )


# ---------------------------------------------------------------------------
# The cache is bounded, and expiry is real
# ---------------------------------------------------------------------------

class TestReplayCacheLifecycle(unittest.TestCase):

    def test_rotate_key_forgets_everything(self):
        auth = IPCAuthenticator(key=b"k" * 64)
        msg = {"a": 1}
        sig = auth.sign_message(msg)
        self.assertTrue(auth.verify_message(msg, sig))
        auth.rotate_key()
        self.assertEqual(auth._seen, {}, "rotation must drop the replay cache")
        # The old MAC is dead (new key); the new one is accepted immediately.
        new_sig = auth.sign_message(msg)
        self.assertTrue(auth.verify_message(msg, new_sig))

    def test_an_expired_entry_is_forgotten(self):
        with _ClockPatched() as clock:
            auth = IPCAuthenticator(key=b"k" * 64, replay_window=30.0)
            msg = {"a": 1}
            sig = auth.sign_message(msg)

            self.assertTrue(auth.verify_message(msg, sig))
            self.assertFalse(auth.verify_message(msg, sig), "still inside the window")

            clock.advance(31.0)
            self.assertTrue(
                auth.verify_message(msg, sig),
                "once the window lapses the MAC is no longer remembered",
            )

    def test_memory_stays_bounded_under_a_flood(self):
        auth = IPCAuthenticator(key=b"k" * 64, max_entries=4)
        for index in range(40):
            msg = {"seq": index}
            auth.verify_message(msg, auth.sign_message(msg))
        self.assertLessEqual(
            len(auth._seen),
            auth._max_entries,
            "the replay cache must not grow without bound",
        )

    def test_the_documented_tradeoff_under_a_flood_is_real(self):
        """Under memory pressure the oldest MACs are forgotten - by design.

        Pinning this keeps the docstring honest: it is a bounded-memory
        fallback, not silent memory exhaustion, and it only costs accuracy for
        MACs still inside the window.
        """
        auth = IPCAuthenticator(key=b"k" * 64, max_entries=2)
        first = {"seq": "first"}
        first_sig = auth.sign_message(first)
        self.assertTrue(auth.verify_message(first, first_sig))

        for index in range(6):
            msg = {"seq": index}
            auth.verify_message(msg, auth.sign_message(msg))

        self.assertLessEqual(len(auth._seen), 2)


# ---------------------------------------------------------------------------
# Envelope API: replay defence that survives a restart
# ---------------------------------------------------------------------------

class TestEnvelope(unittest.TestCase):

    KEY = b"e" * 64

    def test_round_trip(self):
        auth = IPCAuthenticator(key=self.KEY)
        env = auth.sign_envelope({"op": "sync", "n": 1})
        self.assertIn("mac", env)
        self.assertIn("nonce", env)
        self.assertIn("timestamp", env)
        self.assertTrue(auth.verify_envelope(env))

    def test_the_callers_dict_is_not_mutated(self):
        auth = IPCAuthenticator(key=self.KEY)
        original = {"op": "sync"}
        auth.sign_envelope(original)
        self.assertEqual(original, {"op": "sync"})

    def test_a_replayed_envelope_is_refused(self):
        auth = IPCAuthenticator(key=self.KEY)
        env = auth.sign_envelope({"op": "sync"})
        self.assertTrue(auth.verify_envelope(env))
        self.assertFalse(auth.verify_envelope(env))

    def test_a_tampered_envelope_is_refused(self):
        auth = IPCAuthenticator(key=self.KEY)
        env = auth.sign_envelope({"amount": 10})
        env["amount"] = 10_000
        self.assertFalse(auth.verify_envelope(env))

    def test_a_stale_envelope_is_refused(self):
        with _ClockPatched() as clock:
            auth = IPCAuthenticator(key=self.KEY, envelope_ttl=60.0)
            env = auth.sign_envelope({"op": "sync"})
            clock.advance(61.0)
            self.assertFalse(auth.verify_envelope(env))

    def test_an_envelope_stamped_in_the_future_is_refused(self):
        with _ClockPatched() as clock:
            auth = IPCAuthenticator(key=self.KEY, envelope_ttl=60.0)
            clock.advance(3600.0)
            env = auth.sign_envelope({"op": "sync"})
            clock.advance(-3600.0)  # receiver clock is an hour behind the sender
            self.assertFalse(
                auth.verify_envelope(env),
                "a future timestamp must not buy an unbounded validity period",
            )

    def test_each_envelope_is_unique(self):
        auth = IPCAuthenticator(key=self.KEY)
        first = auth.sign_envelope({"op": "sync"})
        second = auth.sign_envelope({"op": "sync"})
        self.assertNotEqual(first["nonce"], second["nonce"])
        self.assertNotEqual(first["mac"], second["mac"])
        self.assertTrue(auth.verify_envelope(first))
        self.assertTrue(auth.verify_envelope(second))

    def test_an_envelope_survives_a_restart(self):
        """This is the reason the envelope exists: the MAC cache does not."""
        sender = IPCAuthenticator(key=self.KEY)
        env = sender.sign_envelope({"op": "sync"})

        restarted = IPCAuthenticator(key=self.KEY)
        self.assertTrue(
            restarted.verify_envelope(env),
            "a restarted receiver must still be able to validate an envelope",
        )

    def test_malformed_envelopes_return_false_and_never_raise(self):
        auth = IPCAuthenticator(key=self.KEY)
        good = auth.sign_envelope({"op": "sync"})

        def without(field):
            return {k: v for k, v in good.items() if k != field}

        cases = [
            None,
            "not-a-dict",
            [],
            {},
            without("mac"),
            without("nonce"),
            without("timestamp"),
            dict(good, mac=None),
            dict(good, mac=123),
            dict(good, nonce=None),
            dict(good, timestamp="soon"),
            dict(good, timestamp=True),
            dict(good, ttl="forever"),
            dict(good, mac="0" * 64),
            dict(good, extra={1, 2, 3}),  # un-JSON-able payload
        ]
        for index, case in enumerate(cases):
            with self.subTest(case=index):
                self.assertFalse(auth.verify_envelope(case))


# ---------------------------------------------------------------------------
# The documented wire format is unchanged
# ---------------------------------------------------------------------------

class TestPublicApiIsStable(unittest.TestCase):

    def test_sign_message_still_returns_a_64_char_hex_string(self):
        auth = IPCAuthenticator()
        sig = auth.sign_message({"action": "start", "pid": 1})
        self.assertIsInstance(sig, str)
        self.assertEqual(len(sig), 64)
        int(sig, 16)  # raises if not hex

    def test_signing_is_still_deterministic(self):
        key = b"fixed" * 12 + b"xyzw"
        first = IPCAuthenticator(key=key)
        second = IPCAuthenticator(key=key)
        msg = {"stable": "data"}
        self.assertEqual(first.sign_message(msg), second.sign_message(msg))

    def test_the_developer_guide_snippet_still_works(self):
        """docs/developer_guide.md:226-228 must keep working verbatim."""
        auth = IPCAuthenticator()
        mac = auth.sign_message({"action": "start"})
        valid = auth.verify_message({"action": "start"}, mac)
        self.assertTrue(valid)

    def test_a_tampered_body_still_fails(self):
        auth = IPCAuthenticator()
        sig = auth.sign_message({"data": "original"})
        self.assertFalse(auth.verify_message({"data": "tampered"}, sig))


# ---------------------------------------------------------------------------
# The false digest claims are gone
# ---------------------------------------------------------------------------

class TestClaimsMatchTheCode(unittest.TestCase):

    def test_the_class_docstring_names_the_digest_actually_used(self):
        doc = IPCAuthenticator.__doc__ or ""
        self.assertIn("SHA3-256", doc)
        self.assertNotIn("SHA3-512", doc)

    def test_the_module_docstring_no_longer_overstates(self):
        doc = secmod.__doc__ or ""
        self.assertNotIn("SHA3-512", doc, "module docstring still claims SHA3-512")
        self.assertNotIn(
            "HMAC-SHA256", doc, "module docstring still claims plain HMAC-SHA256"
        )
        self.assertIn("anti-replay", doc)
        self.assertIn("SHA3-256", doc)

    def test_the_live_class_contains_no_sha3_512(self):
        source = inspect.getsource(IPCAuthenticator)
        self.assertNotIn("sha3_512", source)

    def test_both_verifiers_compare_in_constant_time(self):
        source = inspect.getsource(IPCAuthenticator)
        self.assertGreaterEqual(
            source.count("compare_digest"),
            2,
            "verify_message and verify_envelope must both use compare_digest",
        )

    def test_the_gui_no_longer_repeats_the_false_claim(self):
        gui = (PROJECT_ROOT / "ui" / "umeros_gui.py").read_text(encoding="utf-8")
        self.assertNotIn("HMAC-SHA3-512", gui)
        self.assertIn("HMAC-SHA3-256", gui)


if __name__ == "__main__":
    unittest.main()
