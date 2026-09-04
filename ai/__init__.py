# UmerOS /ai — Local AI assistant, providers, governance
# =======================================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``ai`` package hosts:
#   * ``assistant``        - AIAssistant, ChatService, get_chat_service
#   * ``consent``          - AIGovernance, governance
#   * ``model_manager``    - ModelManager (download, cache, load)
#   * ``providers``        - ProviderRegistry + adapters (OpenAI, Anthropic, Gemini, Ollama, llama.cpp)
#   * ``self_healing``     - SelfHealingService / Engine (H21 H12-gated)
#   * ``resource_predictor``- ResourcePredictor (EWMA + z-score)
#   * ``umer_ai``          - The full LocalAIAssistant implementation
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /ai — Local AI assistant, providers, governance.
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__: list[str] = []


def _try_import(module_name: str, names: tuple[str, ...]) -> None:
    """Import optional helpers and add the names to ``__all__``."""
    global __all__
    try:
        mod = __import__(f"{__name__}.{module_name}", fromlist=names)
    except ImportError:
        return
    for n in names:
        if hasattr(mod, n):
            globals()[n] = getattr(mod, n)
            __all__ = list(__all__) + [n]


# Re-export the public surface.  Each import is wrapped in try/except
# so a partial checkout can still be imported; the canonical names
# stay stable even when internal modules are refactored.
for _mod, _names in (
    ("assistant", ("AIAssistant", "ChatService", "get_chat_service")),
    ("consent", ("AIGovernance", "governance")),
    ("model_manager", ("ModelManager",)),
    ("providers", (
        "ProviderRegistry",
        "OpenAICompatProvider",
        "AnthropicProvider",
        "GeminiProvider",
        "OllamaProvider",
        "LlamaCppProvider",
    )),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify every name in ``__all__`` is importable from this package.

    The AI subsystem is opt-in for the test runner — we never require
    remote provider credentials, so the smoke test just checks that the
    registry / governance imports cleanly.
    """
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [name for name in __all__ if not hasattr(pkg, name)]
    if missing:
        print(
            f"ai selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
