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
Umer OS — Assistant Chat Service  [TODAY]
==========================================
The single brain shared by the HTTP server, the kernel's
``LocalAIAssistant`` and any other consumer.

Responsibilities:
  * Own the :class:`ProviderRegistry` + persisted chat config.
  * Enforce the H18 consent gate: **every** online-provider call is
    checked against :mod:`ai.consent` and fails closed otherwise.
  * Provide both blocking ``chat()`` and streaming ``chat_stream()``.
  * Maintain a bounded conversation history per session id.

Config lives at ~/.umeros/ai_state/chat_config.json and stores only
NON-SECRET fields (provider/model choice, temperature...). API keys go
through env vars or the optional providers section which the server
masks on read.

Author:  Umer OS Project
License: GPLv3
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, Iterator, List, Optional

from ai.consent import governance
from ai.providers import LLMProvider, ProviderRegistry

log = logging.getLogger("UmerOS.AI.Chat")

_STATE_DIR = os.environ.get(
    "UMEROS_AI_STATE_DIR",
    os.path.join(os.path.expanduser("~"), ".umeros", "ai_state"),
)
_CONFIG_FILE = os.path.join(_STATE_DIR, "chat_config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "active_provider": "ollama",
    "model": None,
    "temperature": 0.7,
    "max_tokens": 1024,
    "system_prompt": (
        "You are Umer OS Assistant, the built-in AI of the Umer OS "
        "operating system. Be concise, accurate and friendly."
    ),
}

ONLINE_KINDS = {"free-online", "paid-online"}
MAX_HISTORY = 40  # messages kept per session


class ChatService:
    """Facade over providers with consent + config + history."""

    def __init__(self, config_path: Optional[str] = None,
                 registry: Optional[ProviderRegistry] = None) -> None:
        self._config_path = config_path or _CONFIG_FILE
        self._lock = threading.Lock()
        self._sessions: Dict[str, List[Dict[str, str]]] = {}
        self.config: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.registry = registry or ProviderRegistry(self._load_provider_cfg())
        self._load_config()

    # ── config ──────────────────────────────────────────────────────────

    def _load_provider_cfg(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, "r", encoding="utf-8") as fh:
                    return json.load(fh).get("providers", {})
        except Exception as exc:  # noqa: BLE001
            log.warning("Provider config unreadable: %s", exc)
        return {}

    def _load_config(self) -> None:
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, "r", encoding="utf-8") as fh:
                    stored = json.load(fh)
                for key in DEFAULT_CONFIG:
                    if key in stored and key != "providers":
                        self.config[key] = stored[key]
        except Exception as exc:  # noqa: BLE001
            log.warning("Chat config unreadable: %s", exc)

    def save_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Merge allowed keys and persist. Returns current public config."""
        allowed = set(DEFAULT_CONFIG) | {"providers"}
        for k, v in updates.items():
            if k in allowed:
                self.config[k] = v
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as fh:
                json.dump(self.config, fh, indent=2)
        except Exception as exc:  # noqa: BLE001
            log.error("Failed saving chat config: %s", exc)
        return self.public_config()

    def public_config(self) -> Dict[str, Any]:
        """Config safe to send to UI — provider api_keys masked."""
        pub = {k: v for k, v in self.config.items() if k != "providers"}
        prov_pub: Dict[str, Any] = {}
        for pid, pcfg in (self.config.get("providers") or {}).items():
            masked = dict(pcfg)
            if masked.get("api_key"):
                masked["api_key"] = "***saved***"
            prov_pub[pid] = masked
        pub["providers"] = prov_pub
        return pub

    # ── providers ────────────────────────────────────────────────────────

    def list_providers(self) -> List[Dict[str, Any]]:
        out = []
        for p in self.registry.all():
            d = p.describe()
            d["consent"] = governance.check_consent(p.id)
            out.append(d)
        return out

    def _resolve(self, provider_id: Optional[str],
                 model: Optional[str]) -> LLMProvider:
        pid = provider_id or self.config.get("active_provider") or "ollama"
        provider = self.registry.get(pid)
        if provider is None:
            raise ValueError(f"Unknown provider '{pid}'.")
        return provider

    # ── history ──────────────────────────────────────────────────────────

    def _history(self, session_id: str,
                 extra_user_msg: Optional[str]) -> List[Dict[str, str]]:
        msgs: List[Dict[str, str]] = []
        sys_prompt = self.config.get("system_prompt")
        if sys_prompt:
            msgs.append({"role": "system", "content": sys_prompt})
        msgs.extend(self._sessions.get(session_id, [])[-MAX_HISTORY:])
        if extra_user_msg:
            msgs.append({"role": "user", "content": extra_user_msg})
        return msgs

    def reset_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    # ── core chat paths ──────────────────────────────────────────────────

    def _check_consent_or_raise(self, provider: LLMProvider) -> None:
        if provider.kind in ONLINE_KINDS and \
                not governance.check_consent(provider.id):
            raise PermissionError(
                f"Consent not granted for online provider '{provider.id}'. "
                "Grant it in AI settings before sending prompts off-device.")

    def chat(self, message: str, session_id: str = "default",
             provider_id: Optional[str] = None,
             model: Optional[str] = None) -> Dict[str, Any]:
        """Blocking chat turn. Returns reply + metadata."""
        provider = self._resolve(provider_id, model)
        self._check_consent_or_raise(provider)

        messages = self._history(session_id, message)
        reply = provider.query(
            messages,
            model=model or self.config.get("model"),
            temperature=float(self.config.get("temperature", 0.7)),
            max_tokens=int(self.config.get("max_tokens", 1024)),
        )
        self._remember(session_id, message, reply)
        return {
            "reply": reply,
            "provider": provider.id,
            "kind": provider.kind,
        }

    def chat_stream(self, message: str, session_id: str = "default",
                    provider_id: Optional[str] = None,
                    model: Optional[str] = None) -> Iterator[str]:
        """Streaming chat turn yielding text deltas."""
        provider = self._resolve(provider_id, model)
        self._check_consent_or_raise(provider)

        messages = self._history(session_id, message)
        collected: List[str] = []
        for delta in provider.stream_iter(
                messages,
                model=model or self.config.get("model"),
                temperature=float(self.config.get("temperature", 0.7)),
                max_tokens=int(self.config.get("max_tokens", 1024))):
            collected.append(delta)
            yield delta
        self._remember(session_id, message, "".join(collected))

    def _remember(self, session_id: str, user_msg: str, reply: str) -> None:
        with self._lock:
            hist = self._sessions.setdefault(session_id, [])
            hist.append({"role": "user", "content": user_msg})
            hist.append({"role": "assistant", "content": reply})
            del hist[:-MAX_HISTORY]

    # ── status snapshot for UI ───────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        ollama = self.registry.get("ollama")
        llamacpp = self.registry.get("llamacpp")
        online_ready = [
            p.id for p in self.registry.all()
            if p.kind in ONLINE_KINDS and p.is_available
        ]
        local_ready = [
            p.id for p in self.registry.all()
            if p.kind == "local" and p.is_available
        ]
        return {
            "backend": "umer-ai",
            "active_provider": self.config.get("active_provider"),
            "online_providers_ready": online_ready,
            "local_providers_ready": local_ready,
            "ollama_installed": bool(ollama and ollama.is_available),
            "llamacpp_runtime_installed": _llamacpp_importable(),
            "installed_models": llamacpp.list_installed()
            if llamacpp else [],
        }


def _llamacpp_importable() -> bool:
    try:
        import llama_cpp  # noqa: F401,F403
        return True
    except ImportError:
        return False


# Shared instance for the server process.
chat_service = ChatService()
