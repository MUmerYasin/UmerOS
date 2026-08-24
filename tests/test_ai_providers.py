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
Tests for the UmerOS AI provider layer: consent gate (H18 regression),
registry construction, OpenAI-compatible request building, config
masking and the model manager's path safety. All network I/O is mocked.

Run:  python -m pytest tests/test_ai_providers.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.consent import AIGovernance                      # noqa: E402
from ai.providers import (                                # noqa: E402
    AnthropicProvider,
    GeminiProvider,
    LlamaCppProvider,
    OllamaProvider,
    OpenAICompatProvider,
    ProviderRegistry,
)
from ai.model_manager import ModelManager                 # noqa: E402


def _fake_urlopen_json(payload):
    """Context-manager fake for urllib.request.urlopen returning JSON."""
    body = json.dumps(payload).encode("utf-8")

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return body

    return lambda req, timeout=None: FakeResp()


class TestConsentGate(unittest.TestCase):
    """H18 regression: online egress must fail closed without consent."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.path)
        self.gov = AIGovernance(ledger_path=self.path)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_default_deny(self):
        self.assertFalse(self.gov.check_consent("openai"))

    def test_grant_then_revoke(self):
        self.gov.grant_consent("openai", note="test")
        self.assertTrue(self.gov.check_consent("openai"))
        # persisted?
        second = AIGovernance(ledger_path=self.path)
        self.assertTrue(second.check_consent("openai"))

        second.revoke_consent("openai")
        third = AIGovernance(ledger_path=self.path)
        self.assertFalse(third.check_consent("openai"))
        self.assertIn("openai", third.list_consents()["denials"])


class _RecordingCompat(OpenAICompatProvider):
    """Captures request payloads instead of hitting the network."""

    last_body = None

    def query(self, messages, model=None, temperature=0.7, max_tokens=1024):  # noqa: D102
        type(self).last_body = {
            "url": f"{self.base_url}/chat/completions",
            "model": model or (self.list_models() or ["default"])[0],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "headers": self._headers(),
        }
        return "ok"


class TestOpenAICompat(unittest.TestCase):
    def _prov(self):
        return _RecordingCompat(
            "openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-test",
            name="OpenRouter",
            kind="free-online",
            preset_models=["meta-llama/llama-3.2-3b-instruct:free"],
        )

    def test_request_shape_and_auth_header(self):
        p = self._prov()
        reply = p.query(
            [{"role": "user", "content": "hi"}], model=None)
        self.assertEqual(reply, "ok")
        body = type(p).last_body
        self.assertEqual(body["url"],
                         "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(
            body["model"], "meta-llama/llama-3.2-3b-instruct:free",
            "must pick first preset model when model not given")
        self.assertEqual(body["headers"]["Authorization"], "Bearer sk-test")

    def test_paid_kind_requires_key(self):
        p = OpenAICompatProvider(
            "openai", base_url="https://api.openai.com/v1",
            api_key="", name="OpenAI", kind="paid-online",
            preset_models=["gpt-4o-mini"])
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertFalse(p.is_available)

    def test_local_kind_available_without_key_when_server_up(self):
        p = OpenAICompatProvider(
            "lmstudio", base_url="http://127.0.0.1:1234/v1",
            api_key="", name="LM Studio", kind="local", preset_models=[])
        with mock.patch(
                "ai.providers._http_json",
                side_effect=lambda *a, **k: {"data": [
                    {"id": "qwen2.5-7b"}]}):
            self.assertTrue(p.is_available)
            self.assertEqual(p.list_models(), ["qwen2.5-7b"])

    def test_stream_parses_sse_chunks(self):
        p = OpenAICompatProvider(
            "groq", base_url="https://api.groq.com/openai/v1",
            api_key="k", name="Groq", kind="free-online",
            preset_models=["llama-3.1-8b-instant"])
        lines = [
            'data: {"choices":[{"delta":{"content":"Hel"}}]}',
            "",
            'data: {"choices":[{"delta":{"content":"lo"}}]}',
            "data: [DONE]",
        ]
        with mock.patch("ai.providers._http_stream_lines",
                        return_value=iter(lines)):
            got = "".join(p.stream_iter([{"role": "user", "content": "x"}]))
        self.assertEqual(got, "Hello")


class TestRegistry(unittest.TestCase):
    def test_builtin_providers_present_and_described_without_leaking_keys(self):
        reg = ProviderRegistry({})
        ids = {p.id for p in reg.all()}
        expected = {"openai", "openrouter", "groq", "deepseek", "mistral",
                    "anthropic", "gemini", "ollama", "llamacpp"}
        self.assertTrue(expected.issubset(ids), f"missing: {expected - ids}")

        desc = json.dumps(reg.describe_all())
        self.assertNotIn("sk-", desc)

    def test_custom_endpoint_registered(self):
        reg = ProviderRegistry({"providers": {
            "custom": {"base_url": "http://127.0.0.1:9999/v1",
                       "name": "MyMCP", "kind": "local"}}})
        custom = reg.get("custom")
        self.assertIsNotNone(custom)
        self.assertEqual(custom.name, "MyMCP")


class TestModelManagerSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="umer_models_")
        self.mgr = ModelManager(models_dir=self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_catalog_flags_installed(self):
        self.assertTrue(all(not e["installed"]
                            for e in self.mgr.catalog()))
        open(os.path.join(self.tmp, "qwen2.5-0.5b-instruct-q4_k_m.gguf"),
             "wb").write(b"x")
        cat = {e["id"]: e for e in self.mgr.catalog()}
        self.assertTrue(cat["qwen2.5-0.5b-instruct-q4"]["installed"])

    def test_delete_rejects_unknown_names(self):
        open(os.path.join(self.tmp, "a.gguf"), "wb").write(b"x")
        self.assertFalse(self.mgr.delete_model("../../etc/passwd"))
        self.assertFalse(self.mgr.delete_model("not-installed.gguf"))
        self.assertTrue(self.mgr.delete_model("a.gguf"))

    def test_unknown_download_id_rejected(self):
        result = self.mgr.start_download("no-such-model")
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
