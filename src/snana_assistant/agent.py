"""The tool-use agent loop. BYOK: reads ANTHROPIC_API_KEY from the environment —
no subscription, no hosted backend, no cost to anyone but the person running it.

Local/open-weight backend (Phase 3) is not implemented yet — this module is the
hosted-API path only. See ROADMAP.md design principle #5.
"""

from __future__ import annotations

import json
import os

import anthropic

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


class Agent:
    def __init__(self, kb: KnowledgeBase | None = None, model: str = "claude-sonnet-5"):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. This tool is bring-your-own-key: "
                "export ANTHROPIC_API_KEY=sk-... before running."
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.kb = kb or KnowledgeBase.load()
        self.dispatch = make_dispatch(self.kb)

    def diagnose(self, user_message: str, max_turns: int = 6) -> str:
        messages = [{"role": "user", "content": user_message}]
        for _ in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
            if response.stop_reason != "tool_use":
                return "".join(block.text for block in response.content if block.type == "text")

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                fn = self.dispatch.get(block.name)
                if fn is None:
                    result = f"Unknown tool: {block.name}"
                else:
                    try:
                        result = fn(**block.input)
                    except Exception as exc:  # tool failures should inform the agent, not crash the loop
                        result = f"Tool {block.name} raised: {exc}"
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": str(result)}
                )
            messages.append({"role": "user", "content": tool_results})

        return "Reached max_turns without a final answer — the failure may need a human to look at it."
