"""Provider-neutral tool schema + the interface every backend implements.

Canonical schema lives once (tools.py's TOOL_SCHEMAS, which is already
Anthropic-shaped JSON Schema) and each backend translates it to whatever its SDK
expects. This is the concrete fix for the single-vendor lock-in flagged in
ROADMAP.md design principle #5: "backend-agnostic inference" originally meant
hosted-API-vs-local-model, but hosted-API was itself hardcoded to one vendor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


def truncated(text_responses: list[str], max_turns: int) -> str:
    """Terminal return for a loop that ran out of turns mid-investigation.

    Always marks the result, even when some text was emitted. The previous
    `"\\n\\n".join(...) or "Reached max_turns..."` only warned when *zero* text
    had accumulated, so a lone "let me check a few more things" preamble came
    back looking like a finished answer.
    """
    banner = (
        f"[incomplete: stopped after {max_turns} tool-use turns without reaching a "
        f"final answer -- rerun with a higher --max-turns]"
    )
    if not text_responses:
        return banner
    return "\n\n".join(text_responses) + "\n\n" + banner


class Backend(ABC):
    """One instance per (provider, model). `dispatch` is the {tool_name: callable}
    table from tools.make_dispatch — identical across all backends, since the tools
    themselves (squeue, diff, log tail, KB search) don't know or care which LLM is
    calling them.

    max_turns/max_tokens are sized for the *widest* query shape, not the narrowest.
    A curated-failure-mode hit resolves in 2-3 turns, but a file-review query
    ("what does this .input do, and what does it depend on?") spends its first
    three turns on search_knowledge/search_gotchas/search_manual before read_file
    ever opens the file, then follows INPUT_FILE_INCLUDE chains from there. At the
    original 6/1024 those queries ran out of loop and returned partial text -- or,
    if no turn had emitted text yet, nothing at all."""

    @abstractmethod
    def diagnose(
        self,
        system_prompt: str,
        user_message: str,
        tool_schemas: list[dict[str, Any]],
        dispatch: dict[str, Callable[..., str]],
        max_turns: int = 15,
        max_tokens: int = 4096,
        history: list[Any] | None = None,
    ) -> str:
        """Run one investigation and return the assistant's text.

        `history` makes the call conversational. Pass the same list back on the next
        call and the model sees everything that came before -- prior questions, its own
        answers, and every tool result it collected. The backend appends this exchange
        to it in place, including the final assistant turn.

        The list's *contents* are provider-specific (Anthropic message dicts, OpenAI
        message dicts, Gemini Contents) and callers must treat it as opaque: build it
        with one backend, use it only with that backend. Omit it (the default) for
        one-shot behaviour, where each call starts from an empty slate.
        """
        ...
