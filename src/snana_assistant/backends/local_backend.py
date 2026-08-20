from __future__ import annotations

import os

from .openai_backend import OpenAIBackend

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class LocalBackend(OpenAIBackend):
    """Local OpenAI-compatible backend (e.g. Ollama, vLLM, LM Studio).

    Defaults to Ollama's local URL (http://localhost:11434/v1) and looks for model configuration
    in OLLAMA_MODEL or LOCAL_MODEL environment variables (defaulting to 'llama3.1').
    """

    def __init__(self, model: str | None = None, api_key: str | None = None, base_url: str | None = None):
        if OpenAI is None:
            raise RuntimeError("openai package not installed — pip install 'snana-assistant[openai]'")
        
        url = base_url or os.environ.get("LOCAL_API_BASE") or os.environ.get("OLLAMA_HOST") or "http://localhost:11434/v1"
        # Standardize Ollama hostname formats to /v1
        if "11434" in url and not url.endswith("/v1") and not url.endswith("/v1/"):
            url = url.rstrip("/") + "/v1"
            
        key = api_key or os.environ.get("LOCAL_API_KEY") or "local"
        target_model = model or os.environ.get("LOCAL_MODEL") or os.environ.get("OLLAMA_MODEL") or "llama3.1"
        
        super().__init__(model=target_model, api_key=key)
        # Override client with custom base_url
        self.client = OpenAI(api_key=key, base_url=url)
