"""The agent: fixed debugging logic + knowledge base, pluggable LLM backend.

BYOK across three providers — no subscription required for any of them, and no
lock-in to whichever vendor you happen to have credits with. Picks a backend
automatically from whichever API key is set (Anthropic > OpenAI > Gemini, in that
order, if more than one happens to be set), or takes an explicit `provider=`.
"""

from __future__ import annotations

import os
from pathlib import Path

from .backends.base import Backend
from .knowledge import KnowledgeBase
from .tools import TOOL_SCHEMAS, make_dispatch


def _load_env() -> None:
    # Resolve .env relative to the package src dir
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
    # Load global config settings as well
    from .config import load_all_config_to_env
    load_all_config_to_env()


_load_env()



SYSTEM_PROMPT = """You are a SNANA/Pippin pipeline debugging assistant.

Always call search_knowledge on the very first turn with the user's exact symptom/query text (verbatim, do not paraphrase, rewrite, or summarize) to check for matching curated failure modes. 

CRITICAL: If a curated failure mode matches the user's query, you MUST explicitly include its entry ID in square brackets (e.g., [stale-cached-yaml] or [sigint-abort-bbc]) in your final response to the user, and explain its cause and fix. Do not explain the fix without citing the exact entry ID.

Operational vs. Lookup Queries:
- If the user describes a pipeline crash or running failure, and no curated failure mode is found via search_knowledge, proceed with this debugging order:
  1. Slurm job status / name conflicts (check_job_status)
  2. Cached config vs. source config mismatch (diff_config)
  3. Environment variables (ask the user to confirm SNDATA_ROOT / MY_SNDATA_ROOT if relevant)
  4. OOM / walltime / abort patterns in the log (read_log_tail)
  5. Personal gotchas / user-specific knowledge base (search_gotchas)
  6. Official SNANA manual (search_manual)
- If the user is asking an informational, general, or parameter lookup question (e.g. explaining what a config parameter does, or how a command option works), call `search_knowledge`, `search_gotchas`, and/or `search_manual` immediately on the very first turn.

If nothing matches the search_knowledge database, search the user's personal gotchas folder (search_gotchas) and the official SNANA manual (search_manual) for matching topics, error strings, or keywords. If still nothing matches, say so explicitly rather than guessing.
"""

def _get_backend_class(provider: str):
    if provider == "anthropic":
        from .backends.anthropic_backend import AnthropicBackend
        return AnthropicBackend
    elif provider == "openai":
        from .backends.openai_backend import OpenAIBackend
        return OpenAIBackend
    elif provider == "gemini":
        from .backends.gemini_backend import GeminiBackend
        return GeminiBackend
    elif provider in ("local", "ollama"):
        from .backends.local_backend import LocalBackend
        return LocalBackend
    raise ValueError(f"Unknown provider: {provider}")


_PROVIDER_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "local": "LOCAL_API_BASE",
    "ollama": "OLLAMA_HOST",
}


def _autodetect_backend() -> Backend:
    for provider, env_var in _PROVIDER_ENV_VARS.items():
        if os.environ.get(env_var) or (provider == "gemini" and os.environ.get("GEMINI_API_KEY")):
            cls = _get_backend_class(provider)
            return cls()
    raise RuntimeError(
        "No API key or local host configuration found. Set one of: "
        "ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY (or GEMINI_API_KEY), "
        "LOCAL_API_BASE, or OLLAMA_HOST."
    )


class Agent:
    def __init__(self, kb: KnowledgeBase | None = None, backend: Backend | None = None, provider: str | None = None):
        self.kb = kb or KnowledgeBase.load()
        self.dispatch = make_dispatch(self.kb)
        if backend is not None:
            self.backend = backend
        elif provider is not None:
            cls = _get_backend_class(provider)
            self.backend = cls()
        else:
            self.backend = _autodetect_backend()


    def diagnose(self, user_message: str, max_turns: int = 6) -> str:
        return self.backend.diagnose(SYSTEM_PROMPT, user_message, TOOL_SCHEMAS, self.dispatch, max_turns)
