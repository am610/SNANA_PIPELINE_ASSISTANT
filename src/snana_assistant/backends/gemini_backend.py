"""Least-verified of the three backends — Gemini's function-calling surface has
churned across SDK generations (google-generativeai -> google-genai) more than
Anthropic's or OpenAI's. Structurally sound against the current google-genai SDK
patterns, but untested end-to-end (no API key available while building this).
Sanity-check against current Google docs before relying on it.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from .base import Backend

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
    def __init__(self, model: str = "gemini-2.5-pro", api_key: str | None = None):
        if genai is None:
            raise RuntimeError("google-genai package not installed — pip install 'snana-assistant[gemini]'")
        key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY / GEMINI_API_KEY not set.")
        self.client = genai.Client(api_key=key)
        self.model = model

    def diagnose(self, system_prompt, user_message, tool_schemas, dispatch, max_turns=6) -> str:
        tool = _to_gemini_tool(tool_schemas)
        config = types.GenerateContentConfig(system_instruction=system_prompt, tools=[tool])
        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part(text=user_message)])
        ]
        for _ in range(max_turns):
            response = self.client.models.generate_content(
                model=self.model, contents=contents, config=config,
            )
            candidate = response.candidates[0]
            function_calls = [p.function_call for p in candidate.content.parts if p.function_call]
            if not function_calls:
                return "".join(p.text or "" for p in candidate.content.parts)

            contents.append(candidate.content)
            response_parts = []
            for fc in function_calls:
                result = _call(dispatch, fc.name, dict(fc.args or {}))
                response_parts.append(
                    types.Part.from_function_response(name=fc.name, response={"result": str(result)})
                )
            contents.append(types.Content(role="user", parts=response_parts))
        return "Reached max_turns without a final answer."


def _call(dispatch: dict[str, Callable], name: str, kwargs: dict) -> str:
    fn = dispatch.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn(**kwargs)
    except Exception as exc:
        return f"Tool {name} raised: {exc}"
