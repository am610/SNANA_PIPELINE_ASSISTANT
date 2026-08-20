"""The agent: fixed debugging logic + knowledge base, pluggable LLM backend.

BYOK across three providers — no subscription required for any of them, and no
lock-in to whichever vendor you happen to have credits with. Picks a backend
automatically from whichever API key is set (Anthropic > OpenAI > Gemini, in that
order, if more than one happens to be set), or takes an explicit `provider=`.
"""

from __future__ import annotations

import os

from .backends import AnthropicBackend, Backend, GeminiBackend, OpenAIBackend
from .knowledge import KnowledgeBase
from .tools import TOOL_SCHEMAS, make_dispatch

SYSTEM_PROMPT = """You are a SNANA/Pippin pipeline debugging assistant.

Follow this order, matching the project's own debugging discipline — do not jump to
config/code-level speculation before ruling out simpler operational causes:
1. Slurm job status / name conflicts (check_job_status)
2. Cached config vs. source config mismatch (diff_config)
3. Environment variables (ask the user to confirm SNDATA_ROOT / MY_SNDATA_ROOT if relevant)
4. OOM / walltime / abort patterns in the log (read_log_tail)
5. Only then: known config/code-level failure modes (search_knowledge)

Always call search_knowledge early with the user's symptom text — it may short-circuit
straight to a known fix. Cite the knowledge-base entry id when you use one. If nothing
matches, say so explicitly rather than guessing — this system is meant to be honest
about the edges of what it knows, not to fabricate a plausible-sounding diagnosis.
"""

_BACKEND_BY_PROVIDER = {
    "anthropic": (AnthropicBackend, "ANTHROPIC_API_KEY"),
    "openai": (OpenAIBackend, "OPENAI_API_KEY"),
    "gemini": (GeminiBackend, "GOOGLE_API_KEY"),
}


def _autodetect_backend() -> Backend:
    for provider, (cls, env_var) in _BACKEND_BY_PROVIDER.items():
        if os.environ.get(env_var) or (provider == "gemini" and os.environ.get("GEMINI_API_KEY")):
            return cls()
    raise RuntimeError(
        "No API key found. Set one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, "
        "GOOGLE_API_KEY (or GEMINI_API_KEY)."
    )


class Agent:
    def __init__(self, kb: KnowledgeBase | None = None, backend: Backend | None = None, provider: str | None = None):
        self.kb = kb or KnowledgeBase.load()
        self.dispatch = make_dispatch(self.kb)
        if backend is not None:
            self.backend = backend
        elif provider is not None:
            cls, _ = _BACKEND_BY_PROVIDER[provider]
            self.backend = cls()
        else:
            self.backend = _autodetect_backend()

    def diagnose(self, user_message: str, max_turns: int = 6) -> str:
        return self.backend.diagnose(SYSTEM_PROMPT, user_message, TOOL_SCHEMAS, self.dispatch, max_turns)
