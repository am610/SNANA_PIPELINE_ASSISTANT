from __future__ import annotations

import os
from typing import Any, Callable

from .base import Backend, truncated as _truncated

try:
    import anthropic
except ImportError:
    anthropic = None


_EPHEMERAL = {"type": "ephemeral"}


def _cacheable_system(system_prompt: str):
    """System prompt as a cacheable block.

    The cache prefix is ordered tools -> system -> messages, so one breakpoint here
    covers both the tool schemas (~2.7k tokens, byte-identical every turn) and the
    system prompt. Without it every turn re-uploads and re-processes all of it.
    """
    return [{"type": "text", "text": system_prompt, "cache_control": _EPHEMERAL}]


def _mark_conversation_cache(messages: list) -> None:
    """Move the rolling cache breakpoint to the end of the conversation so far.

    Each turn resends the whole history, so without this the growing prefix -- prior
    tool results, file contents, manual chunks -- is reprocessed from scratch every
    time. Old marks are stripped first: the API caps the number of breakpoints, and
    marking every turn would blow past it.

    Only plain dict blocks are marked. Assistant turns hold SDK block objects, which
    do not take a cache_control key; they still get cached as part of the prefix
    covered by a later breakpoint.
    """
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    block.pop("cache_control", None)

    if not messages:
        return
    content = messages[-1].get("content")
    if isinstance(content, str):
        messages[-1]["content"] = [
            {"type": "text", "text": content, "cache_control": _EPHEMERAL}
        ]
    elif isinstance(content, list) and content and isinstance(content[-1], dict):
        content[-1]["cache_control"] = _EPHEMERAL


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
        use_cache = os.environ.get("SNANA_ASSISTANT_NO_CACHE", "").lower() not in ("1", "true", "yes")
        for _ in range(max_turns):
            if use_cache:
                _mark_conversation_cache(messages)
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=_cacheable_system(system_prompt) if use_cache else system_prompt,
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
