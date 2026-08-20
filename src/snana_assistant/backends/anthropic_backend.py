from __future__ import annotations

import os
from typing import Any, Callable

from .base import Backend

try:
    import anthropic
except ImportError:
    anthropic = None


class AnthropicBackend(Backend):
    """Native Anthropic tool-use format — TOOL_SCHEMAS is already shaped this way."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        if anthropic is None:
            raise RuntimeError("anthropic package not installed — pip install 'snana-assistant[anthropic]'")
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set.")
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model or os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5"

    def diagnose(self, system_prompt, user_message, tool_schemas, dispatch, max_turns=6) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        for _ in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                tools=tool_schemas,
                messages=messages,
            )
            if response.stop_reason != "tool_use":
                return "".join(b.text for b in response.content if b.type == "text")

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = _call(dispatch, block.name, block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})
            messages.append({"role": "user", "content": tool_results})
        return "Reached max_turns without a final answer."


def _call(dispatch: dict[str, Callable], name: str, kwargs: dict) -> str:
    fn = dispatch.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn(**kwargs)
    except Exception as exc:
        return f"Tool {name} raised: {exc}"
