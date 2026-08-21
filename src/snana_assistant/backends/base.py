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


class Backend(ABC):
    """One instance per (provider, model). `dispatch` is the {tool_name: callable}
    table from tools.make_dispatch — identical across all backends, since the tools
    themselves (squeue, diff, log tail, KB search) don't know or care which LLM is
    calling them."""

    @abstractmethod
    def diagnose(
        self,
        system_prompt: str,
        user_message: str,
        tool_schemas: list[dict[str, Any]],
        dispatch: dict[str, Callable[..., str]],
        max_turns: int = 6,
        max_tokens: int = 1024,
    ) -> str:
        ...
