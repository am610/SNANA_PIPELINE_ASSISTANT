"""Least-verified of the three backends — Gemini's function-calling surface has
churned across SDK generations (google-generativeai -> google-genai) more than
Anthropic's or OpenAI's. Structurally sound against the current google-genai SDK
patterns, but untested end-to-end (no API key available while building this).
Sanity-check against current Google docs before relying on it.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from .base import Backend, truncated as _truncated

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


def _to_gemini_tool(tool_schemas: list[dict[str, Any]]) -> "types.Tool":
    declarations = [
        types.FunctionDeclaration(
            name=t["name"], description=t["description"], parameters=t["input_schema"]
        )
        for t in tool_schemas
    ]
    return types.Tool(function_declarations=declarations)


class GeminiBackend(Backend):
    def __init__(self, model: str = "gemini-3.6-flash", api_key: str | None = None):
        if genai is None:
            raise RuntimeError("google-genai package not installed — pip install 'snana-assistant[gemini]'")
        key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY / GEMINI_API_KEY not set.")
        self.client = genai.Client(api_key=key)
        self.model = model

    def diagnose(self, system_prompt, user_message, tool_schemas, dispatch, max_turns=15, max_tokens=4096, history=None, on_text=None) -> str:
        tool = _to_gemini_tool(tool_schemas)
        config = types.GenerateContentConfig(system_instruction=system_prompt, tools=[tool], max_output_tokens=max_tokens)
        contents: list[types.Content] = history if history is not None else []
        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
        text_responses = []
        for _ in range(max_turns):
            retries = 5
            backoff = 15
            for attempt in range(retries):
                try:
                    response = self.client.models.generate_content(
                        model=self.model, contents=contents, config=config,
                    )
                    break
                except Exception as exc:
                    if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                        if attempt == retries - 1:
                            raise
                        print(f"\n[Rate Limit] Hit 429. Retrying in {backoff} seconds (attempt {attempt+1}/{retries})...")
                        time.sleep(backoff)
                        backoff *= 2
                    else:
                        raise
            candidate = response.candidates[0]
            turn_text = "".join(p.text or "" for p in candidate.content.parts if p.text).strip()
            if turn_text:
                text_responses.append(turn_text)

            function_calls = [p.function_call for p in candidate.content.parts if p.function_call]
            contents.append(candidate.content)
            if not function_calls:
                return "\n\n".join(text_responses)

            response_parts = []
            for fc in function_calls:
                result = _call(dispatch, fc.name, dict(fc.args or {}))
                response_parts.append(
                    types.Part.from_function_response(name=fc.name, response={"result": str(result)})
                )
            contents.append(types.Content(role="user", parts=response_parts))
        return _truncated(text_responses, max_turns)


def _call(dispatch: dict[str, Callable], name: str, kwargs: dict) -> str:
    fn = dispatch.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn(**kwargs)
    except Exception as exc:
        return f"Tool {name} raised: {exc}"
