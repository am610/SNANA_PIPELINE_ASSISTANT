from __future__ import annotations

import json
import os
from typing import Any, Callable

from .base import Backend, truncated as _truncated

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def _to_openai_tools(tool_schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anthropic-shaped {name, description, input_schema} -> OpenAI's
    {"type": "function", "function": {name, description, parameters}}."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tool_schemas
    ]


class OpenAIBackend(Backend):
    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        if OpenAI is None:
            raise RuntimeError("openai package not installed — pip install 'snana-assistant[openai]'")
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set.")
        self.client = OpenAI(api_key=key)
        self.model = model

    def diagnose(self, system_prompt, user_message, tool_schemas, dispatch, max_turns=15, max_tokens=4096, history=None, on_text=None) -> str:
        tools = _to_openai_tools(tool_schemas)
        messages: list[dict[str, Any]] = history if history is not None else []
        # Unlike Anthropic/Gemini, the system prompt is a message here -- only seed it
        # once, or a resumed conversation grows a duplicate system turn per exchange.
        if not messages:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        text_responses = []
        for _ in range(max_turns):
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, tools=tools, max_completion_tokens=max_tokens,
            )
            msg = response.choices[0].message
            turn_text = (msg.content or "").strip()
            if turn_text:
                text_responses.append(turn_text)

            messages.append(msg.model_dump(exclude_unset=True))
            if not msg.tool_calls:
                return "\n\n".join(text_responses)

            for tc in msg.tool_calls:
                kwargs = json.loads(tc.function.arguments or "{}")
                result = _call(dispatch, tc.function.name, kwargs)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})
        return _truncated(text_responses, max_turns)


def _call(dispatch: dict[str, Callable], name: str, kwargs: dict) -> str:
    fn = dispatch.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn(**kwargs)
    except Exception as exc:
        return f"Tool {name} raised: {exc}"
