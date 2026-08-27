from __future__ import annotations

import os
from typing import Any, Callable

from .base import Backend, truncated as _truncated

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

    def diagnose(self, system_prompt, user_message, tool_schemas, dispatch, max_turns=15, max_tokens=4096, history=None) -> str:
        messages: list[dict[str, Any]] = history if history is not None else []
        messages.append({"role": "user", "content": user_message})
        text_responses = []
        for _ in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                tools=tool_schemas,
                messages=messages,
            )
            turn_text = "".join(b.text for b in response.content if b.type == "text").strip()
            if turn_text:
                text_responses.append(turn_text)

            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                # Appended before returning: a conversational caller reuses this list,
                # and dropping the final answer would leave the model blind to what it
                # just said.
                return "\n\n".join(text_responses)

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = str(_call(dispatch, block.name, block.input)).strip()
                if not result:
                    result = "No matches or empty output."
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            messages.append({"role": "user", "content": tool_results})
        return _truncated(text_responses, max_turns)


def _call(dispatch: dict[str, Callable], name: str, kwargs: dict) -> str:
    fn = dispatch.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn(**kwargs)
    except Exception as exc:
        return f"Tool {name} raised: {exc}"
