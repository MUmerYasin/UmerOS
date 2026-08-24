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
Umer OS — LLM Provider Layer  [TODAY]
======================================
Transport layer for every kind of language model Umer OS can talk to:

  LOCAL   (free, on-device)
      * ollama      — native /api/chat + model listing via /api/tags
      * llama.cpp   — GGUF files downloaded by ai/model_manager.py,
                      loaded through llama-cpp-python when installed
      * openai-compat local servers (LM Studio, vLLM, llama-server)

  FREE ONLINE
      * OpenRouter  :free models, Groq free tier, any keyed gateway

  PAID ONLINE
      * OpenAI, Anthropic, Google Gemini, DeepSeek, Mistral, ...

Everything OpenAI-compatible collapses into one class
(:class:`OpenAICompatProvider`) because the ecosystem standardised on
that wire format — including MCP gateways that expose an OpenAI-style
endpoint.

Design rules:
  * NO key => provider simply reports unavailable; never crashes.
  * Keys are read from env first (UMEROS_<NAME>_API_KEY), then config.
    Keys are NEVER logged.
  * ``stream_iter()`` yields plain text deltas for SSE relay.

Author:  Umer OS Project
License: GPLv3
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional

log = logging.getLogger("UmerOS.AI.Providers")

DEFAULT_TIMEOUT = 120  # seconds; local models can be slow on CPU


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _http_json(url: str, payload: Optional[dict] = None,
               headers: Optional[Dict[str, str]] = None,
               timeout: int = DEFAULT_TIMEOUT) -> Any:
    """POST (or GET when payload None) returning decoded JSON."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_stream_lines(url: str, payload: dict,
                       headers: Dict[str, str],
                       timeout: int = DEFAULT_TIMEOUT) -> Iterator[str]:
    """Yield raw lines from a streaming POST response."""
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                yield line


# ---------------------------------------------------------------------------
# base
# ---------------------------------------------------------------------------

class LLMProvider:
    """Base class for every provider."""

    kind = "local"          # local | free-online | paid-online
    supports_stream = False

    def __init__(self, provider_id: str, name: str) -> None:
        self.id = provider_id
        self.name = name

    # -- introspection ---------------------------------------------------

    @property
    def is_available(self) -> bool:
        raise NotImplementedError

    def list_models(self) -> List[str]:
        return []

    def describe(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "available": self.is_available,
            "models": self.list_models(),
            "streaming": self.supports_stream,
        }

    def __repr__(self) -> str:  # never leak api keys
        return f"<{type(self).__name__} id={self.id!r} available={self.is_available}>"

    # -- inference -------------------------------------------------------

    def query(self, messages: List[Dict[str, str]],
              model: Optional[str] = None,
              temperature: float = 0.7,
              max_tokens: int = 1024) -> str:
        raise NotImplementedError

    def stream_iter(self, messages: List[Dict[str, str]],
                    model: Optional[str] = None,
                    temperature: float = 0.7,
                    max_tokens: int = 1024) -> Iterator[str]:
        """Default: fall back to non-streamed single delta."""
        yield self.query(messages, model, temperature, max_tokens)


# ---------------------------------------------------------------------------
# OpenAI-compatible (covers most of the market incl. MCP gateways)
# ---------------------------------------------------------------------------

class OpenAICompatProvider(LLMProvider):
    """Any endpoint speaking POST {base}/chat/completions."""

    supports_stream = True

    PRESETS: Dict[str, Dict[str, Any]] = {
        "openai": {
            "name": "OpenAI",
            "kind": "paid-online",
            "base": "https://api.openai.com/v1",
            "key_env": "OPENAI_API_KEY",
            "models": ["gpt-4o-mini", "gpt-4o", "o3-mini"],
        },
        "openrouter": {
            "name": "OpenRouter",
            "kind": "free-online",
            "base": "https://openrouter.ai/api/v1",
            "key_env": "OPENROUTER_API_KEY",
            "models": [
                "meta-llama/llama-3.2-3b-instruct:free",
                "google/gemini-2.0-flash-exp:free",
                "mistralai/mistral-7b-instruct:free",
                "anthropic/claude-3.5-sonnet",
                "openai/gpt-4o-mini",
            ],
        },
        "groq": {
            "name": "Groq",
            "kind": "free-online",
            "base": "https://api.groq.com/openai/v1",
            "key_env": "GROQ_API_KEY",
            "models": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile",
                       "mixtral-8x7b-32768"],
        },
        "deepseek": {
            "name": "DeepSeek",
            "kind": "paid-online",
            "base": "https://api.deepseek.com/v1",
            "key_env": "DEEPSEEK_API_KEY",
            "models": ["deepseek-chat", "deepseek-reasoner"],
        },
        "mistral": {
            "name": "Mistral",
            "kind": "paid-online",
            "base": "https://api.mistral.ai/v1",
            "key_env": "MISTRAL_API_KEY",
            "models": ["mistral-small-latest", "mistral-large-latest"],
        },
        "lmstudio": {
            "name": "LM Studio",
            "kind": "local",
            "base": "http://127.0.0.1:1234/v1",
            "key_env": "",       # no key needed
            "models": [],        # discovered live
        },
    }

    def __init__(self, provider_id: str, base_url: str,
                 api_key: str = "", name: str = "",
                 kind: str = "local",
                 preset_models: Optional[List[str]] = None) -> None:
        super().__init__(provider_id, name or provider_id.title())
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get(
            self.PRESETS.get(provider_id, {}).get("key_env", ""), "")
        self.kind = kind
        self._preset_models = preset_models or []
        self._discovered_models: List[str] = []

    # -- introspection ---------------------------------------------------

    @property
    def is_available(self) -> bool:
        if self.provider_requires_key and not self.api_key:
            return False
        try:
            self._refresh_models()
            return True
        except Exception:  # noqa: BLE001 — server unreachable etc.
            return False

    @property
    def provider_requires_key(self) -> bool:
        return self.kind in ("free-online", "paid-online")

    def _refresh_models(self) -> None:
        url = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"} \
            if self.api_key else {}
        try:
            data = _http_json(url, None, headers, timeout=5)
            raw = data.get("data", []) if isinstance(data, dict) else []
            ids = [m.get("id") for m in raw if isinstance(m, dict) and m.get("id")]
            if ids:
                self._discovered_models = sorted(ids)[:100]
        except Exception:  # noqa: BLE001 — fall back to preset list
            pass

    def list_models(self) -> List[str]:
        return self._discovered_models or self._preset_models

    # -- inference -------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def query(self, messages, model=None, temperature=0.7, max_tokens=1024):
        body = {
            "model": model or (self.list_models() or ["default"])[0],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = _http_json(f"{self.base_url}/chat/completions", body,
                          self._headers())
        return (data["choices"][0]["message"]["content"] or "").strip()

    def stream_iter(self, messages, model=None, temperature=0.7, max_tokens=1024):
        body = {
            "model": model or (self.list_models() or ["default"])[0],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        for line in _http_stream_lines(f"{self.base_url}/chat/completions",
                                       body, self._headers()):
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if chunk == "[DONE]":
                break
            try:
                obj = json.loads(chunk)
                delta = obj["choices"][0].get("delta", {})
                piece = delta.get("content")
                if piece:
                    yield piece
            except (json.JSONDecodeError, KeyError, IndexError):
                continue


# ---------------------------------------------------------------------------
# Anthropic (Messages API)
# ---------------------------------------------------------------------------

class AnthropicProvider(LLMProvider):
    """Claude family via api.anthropic.com/v1/messages."""

    kind = "paid-online"
    supports_stream = True

    MODELS = ["claude-sonnet-4-20250514", "claude-3-5-haiku-latest",
              "claude-opus-4-20250514"]

    def __init__(self, api_key: str = "") -> None:
        super().__init__("anthropic", "Anthropic Claude")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def list_models(self) -> List[str]:
        return list(self.MODELS)

    def _split(self, messages):
        system = "\n".join(m["content"] for m in messages
                           if m["role"] == "system") or None
        rest = [m for m in messages if m["role"] != "system"]
        return system, rest

    def query(self, messages, model=None, temperature=0.7, max_tokens=1024):
        system, msgs = self._split(messages)
        body: Dict[str, Any] = {
            "model": model or self.MODELS[0],
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            body["system"] = system
        data = _http_json(
            "https://api.anthropic.com/v1/messages", body,
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
        parts = [b.get("text", "") for b in data.get("content", [])
                 if b.get("type") == "text"]
        return "".join(parts).strip()

    def stream_iter(self, messages, model=None, temperature=0.7, max_tokens=1024):
        # Simple approach: reuse non-streamed call; SSE from Anthropic uses
        # a different event grammar we normalise away for now.
        yield self.query(messages, model, temperature, max_tokens)


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------

class GeminiProvider(LLMProvider):
    """Gemini via generativelanguage.googleapis.com."""

    kind = "paid-online"

    MODELS = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]

    def __init__(self, api_key: str = "") -> None:
        super().__init__("gemini", "Google Gemini")
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def list_models(self) -> List[str]:
        return list(self.MODELS)

    def query(self, messages, model=None, temperature=0.7, max_tokens=1024):
        system = "\n".join(m["content"] for m in messages
                           if m["role"] == "system")
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user",
             "parts": [{"text": m["content"]}]}
            for m in messages if m["role"] != "system"
        ]
        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        model_name = model or self.MODELS[0]
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model_name}:generateContent?key={self.api_key}")
        data = _http_json(url, body, {})
        parts = (data.get("candidates", [{}])[0]
                     .get("content", {}).get("parts", []))
        return "".join(p.get("text", "") for p in parts).strip()


# ---------------------------------------------------------------------------
# Ollama (native protocol, local & free)
# ---------------------------------------------------------------------------

class OllamaProvider(LLMProvider):
    """Local models served by Ollama at 127.0.0.1:11434."""

    kind = "local"
    supports_stream = True

    def __init__(self, host: str = "http://127.0.0.1:11434") -> None:
        super().__init__("ollama", "Ollama (Local)")
        self.host = host.rstrip("/")

    @property
    def is_available(self) -> bool:
        try:
            return bool(self.list_models())
        except Exception:  # noqa: BLE001
            return False

    def list_models(self) -> List[str]:
        data = _http_json(f"{self.host}/api/tags", None, {}, timeout=4)
        return sorted(m["name"] for m in data.get("models", []))

    def query(self, messages, model=None, temperature=0.7, max_tokens=1024):
        body = {
            "model": model or (self.list_models() or ["llama3"])[0],
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        data = _http_json(f"{self.host}/api/chat", body, {})
        return (data.get("message", {}).get("response", "") or "").strip()

    def stream_iter(self, messages, model=None, temperature=0.7, max_tokens=1024):
        body = {
            "model": model or (self.list_models() or ["llama3"])[0],
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        for line in _http_stream_lines(f"{self.host}/api/chat", body, {}):
            try:
                obj = json.loads(line)
                piece = obj.get("message", {}).get("response", "")
                if piece:
                    yield piece
                if obj.get("done"):
                    break
            except json.JSONDecodeError:
                continue


# ---------------------------------------------------------------------------
# llama.cpp (GGUF files managed by model_manager.py)
# ---------------------------------------------------------------------------

class LlamaCppProvider(LLMProvider):
    """Runs downloaded GGUF models in-process via llama-cpp-python."""

    kind = "local"

    def __init__(self, model_path: str = "",
                 models_dir: Optional[str] = None) -> None:
        super().__init__("llamacpp", "Local GGUF (llama.cpp)")
        self.models_dir = models_dir or os.path.join(
            os.path.expanduser("~"), ".umeros", "models")
        self.model_path = model_path
        self._llm: Any = None
        self._loaded_for: str = ""

    # -- introspection ---------------------------------------------------

    def list_installed(self) -> List[str]:
        try:
            return sorted(
                f for f in os.listdir(self.models_dir) if f.endswith(".gguf"))
        except OSError:
            return []

    def list_models(self) -> List[str]:
        return self.list_installed()

    @property
    def is_available(self) -> bool:
        if not self.list_installed():
            return False
        try:
            import llama_cpp  # noqa: F401
            return True
        except ImportError:
            return False

    # -- engine ----------------------------------------------------------

    def _ensure_loaded(self, filename: str) -> None:
        if self._llm is not None and self._loaded_for == filename:
            return
        from llama_cpp import Llama  # heavy import only when used
        path = os.path.join(self.models_dir, filename)
        log.info("Loading GGUF '%s' into memory...", filename)
        t0 = time.time()
        self._llm = Llama(model_path=path, n_ctx=4096, verbose=False)
        self._loaded_for = filename
        log.info("GGUF loaded in %.1fs.", time.time() - t0)

    def query(self, messages, model=None, temperature=0.7, max_tokens=1024):
        filename = model or (self.list_installed() or [""])[0]
        if not filename:
            raise RuntimeError("No GGUF model downloaded yet.")
        self._ensure_loaded(filename)
        out = self._llm.create_chat_completion(
            messages=messages, temperature=temperature, max_tokens=max_tokens)
        return (out["choices"][0]["message"]["content"] or "").strip()

    def unload(self) -> None:
        self._llm = None
        self._loaded_for = ""


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

class ProviderRegistry:
    """Builds and owns every configured provider instance."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self._providers: Dict[str, LLMProvider] = {}
        self._build(config)

    def _build(self, cfg: Dict[str, Any]) -> None:
        providers_cfg = cfg.get("providers", {})

        # Built-in presets (keys may come from env or providers config)
        for pid, preset in OpenAICompatProvider.PRESETS.items():
            p_cfg = providers_cfg.get(pid, {})
            self._providers[pid] = OpenAICompatProvider(
                pid,
                base_url=p_cfg.get("base_url", preset["base"]),
                api_key=p_cfg.get("api_key", ""),
                name=preset["name"],
                kind=p_cfg.get("kind", preset["kind"]),
                preset_models=p_cfg.get("models", preset["models"]),
            )

        self._providers["anthropic"] = AnthropicProvider(
            providers_cfg.get("anthropic", {}).get("api_key", ""))
        self._providers["gemini"] = GeminiProvider(
            providers_cfg.get("gemini", {}).get("api_key", ""))

        self._providers["ollama"] = OllamaProvider(
            providers_cfg.get("ollama", {}).get("host",
                                                "http://127.0.0.1:11434"))

        models_dir = providers_cfg.get("llamacpp", {}).get("models_dir")
        self._providers["llamacpp"] = LlamaCppProvider(models_dir=models_dir)

        # Custom user-defined openai-compatible endpoint ("custom" slot /
        # MCP gateways exposing OpenAI-style APIs).
        custom = providers_cfg.get("custom")
        if isinstance(custom, dict) and custom.get("base_url"):
            self._providers["custom"] = OpenAICompatProvider(
                "custom",
                base_url=custom["base_url"],
                api_key=custom.get("api_key", ""),
                name=custom.get("name", "Custom Endpoint"),
                kind=custom.get("kind", "local"),
            )

    # -- accessors ---------------------------------------------------------

    def get(self, provider_id: str) -> Optional[LLMProvider]:
        return self._providers.get(provider_id)

    def all(self) -> List[LLMProvider]:
        return list(self._providers.values())

    def describe_all(self) -> List[Dict[str, Any]]:
        return [p.describe() for p in self.all()]
