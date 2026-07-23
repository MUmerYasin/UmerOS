"""
Umer OS AI Providers Architecture
=================================
Extensible LLM provider architecture supporting online API keys,
offline downloaded open-source models, and Model Context Protocol (MCP) data.
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any

log = logging.getLogger("UmerOS.AI.Providers")

class LLMProvider:
    """Base class for all LLM providers."""
    def __init__(self, name: str):
        self.name = name
        self.is_available = False

    def query(self, prompt: str, history: List[Dict[str, str]] = None) -> Optional[str]:
        raise NotImplementedError("Subclasses must implement query()")


class OnlineProvider(LLMProvider):
    """Provider for commercial APIs using user-supplied keys (OpenAI, Gemini, Anthropic)."""
    
    def __init__(self, config: dict):
        super().__init__("OnlineProvider")
        self.api_key = config.get("api_key")
        self.model_name = config.get("model", "gpt-4o-mini")
        self.provider_type = config.get("type", "openai").lower()
        
        if self.api_key:
            self.is_available = True
            log.info("OnlineProvider initialized with %s key.", self.provider_type)
        else:
            log.warning("OnlineProvider disabled: No API key provided.")

    def query(self, prompt: str, history: List[Dict[str, str]] = None) -> Optional[str]:
        if not self.is_available:
            return None
            
        try:
            # We use standard HTTP requests to avoid hard-dependencies on third-party SDKs
            # but users can pip install openai / google-generativeai for fuller features.
            import urllib.request
            import urllib.error
            import json
            
            # OpenAI / Compatible Endpoint implementation
            if self.provider_type in ["openai", "groq", "custom"]:
                url = config.get("endpoint", "https://api.openai.com/v1/chat/completions")
                messages = history or []
                messages.append({"role": "user", "content": prompt})
                
                req = urllib.request.Request(
                    url,
                    data=json.dumps({"model": self.model_name, "messages": messages}).encode('utf-8'),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    }
                )
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    res_body = json.loads(response.read().decode('utf-8'))
                    return res_body['choices'][0]['message']['content'].strip()
                    
            return f"[OnlineProvider] {self.provider_type} logic not yet implemented for direct HTTP."
        except Exception as e:
            log.error("OnlineProvider query failed: %s", e)
            return None


class OfflineProvider(LLMProvider):
    """Provider for offline downloaded models (GGUF via llama-cpp-python) or Ollama."""
    
    def __init__(self, config: dict):
        super().__init__("OfflineProvider")
        self.model_path = config.get("model_path")
        self.engine = config.get("engine", "ollama") # 'llama-cpp' or 'ollama'
        self.llm = None
        
        if self.engine == "llama-cpp" and self.model_path and os.path.exists(self.model_path):
            try:
                from llama_cpp import Llama
                self.llm = Llama(model_path=self.model_path, n_ctx=2048, verbose=False)
                self.is_available = True
                log.info("OfflineProvider loaded GGUF model: %s", self.model_path)
            except ImportError:
                log.error("llama-cpp-python not installed. Cannot load GGUF model.")
            except Exception as e:
                log.error("Failed to load GGUF model: %s", e)
                
        elif self.engine == "ollama":
            self.model_name = config.get("model", "llama3")
            self.is_available = True
            log.info("OfflineProvider configured for Ollama model: %s", self.model_name)

    def query(self, prompt: str, history: List[Dict[str, str]] = None) -> Optional[str]:
        if not self.is_available:
            return None
            
        try:
            if self.engine == "llama-cpp" and self.llm:
                # Basic inference (not chat-formatted for simplicity, could be upgraded)
                res = self.llm(f"Q: {prompt} A:", max_tokens=256, stop=["Q:", "\n"])
                return res["choices"][0]["text"].strip()
                
            elif self.engine == "ollama":
                import urllib.request
                import json
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/generate",
                    data=json.dumps({
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False
                    }).encode('utf-8'),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get("response", "").strip()
        except Exception as e:
            log.warning("OfflineProvider query failed: %s", e)
            return None


class MCPProvider(LLMProvider):
    """Wraps an underlying provider to inject Model Context Protocol (MCP) data."""
    
    def __init__(self, underlying_provider: LLMProvider, mcp_data_path: str):
        super().__init__("MCPProvider")
        self.provider = underlying_provider
        self.mcp_context = ""
        self.is_available = self.provider.is_available
        
        if os.path.exists(mcp_data_path):
            try:
                with open(mcp_data_path, "r", encoding="utf-8") as f:
                    self.mcp_context = f.read()
                log.info("Loaded MCP context from %s", mcp_data_path)
            except Exception as e:
                log.error("Failed to load MCP data: %s", e)
        else:
            log.debug("No MCP data file found at %s", mcp_data_path)

    def query(self, prompt: str, history: List[Dict[str, str]] = None) -> Optional[str]:
        if not self.is_available:
            return None
            
        if self.mcp_context:
            enriched_prompt = f"System Context (MCP):\n{self.mcp_context}\n\nUser Query: {prompt}"
        else:
            enriched_prompt = prompt
            
        return self.provider.query(enriched_prompt, history)


class AIConfigManager:
    """Manages the ai_config.json file and provider initialization."""
    
    def __init__(self, config_path: str = "ai_config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict:
        default_config = {
            "fallback_order": ["online", "offline", "heuristics"],
            "online": {
                "type": "openai",
                "model": "gpt-4o-mini",
                "api_key": "",
                "endpoint": "https://api.openai.com/v1/chat/completions"
            },
            "offline": {
                "engine": "ollama",
                "model": "llama3",
                "model_path": ""
            },
            "mcp_data_path": "mcp_context.txt"
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    # Merge logic could be added here, for now just update top level
                    for k, v in user_config.items():
                        default_config[k] = v
            except Exception as e:
                log.error("Error reading %s: %s", self.config_path, e)
        else:
            # Create default config for the user
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=4)
                log.info("Created default AI config at %s", self.config_path)
            except Exception as e:
                log.error("Failed to write default AI config: %s", e)
                
        return default_config
