"""The agent: fixed debugging logic + knowledge base, pluggable LLM backend.

BYOK across three providers — no subscription required for any of them, and no
lock-in to whichever vendor you happen to have credits with. Picks a backend
automatically from whichever API key is set (Anthropic > OpenAI > Gemini, in that
order, if more than one happens to be set), or takes an explicit `provider=`.
"""

from __future__ import annotations

import os
from pathlib import Path

from .backends.base import Backend
from .knowledge import KnowledgeBase
from .tools import TOOL_SCHEMAS, SETUP_TOOL_SCHEMAS, make_dispatch, make_setup_dispatch


def _load_env() -> None:
    # Resolve .env relative to the package src dir
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
    # Load global config settings as well
    from .config import load_all_config_to_env
    load_all_config_to_env()


_load_env()



SYSTEM_PROMPT = """You are a SNANA/Pippin pipeline debugging assistant.

Always call search_knowledge on the very first turn with the user's exact symptom/query text (verbatim, do not paraphrase, rewrite, or summarize) to check for matching curated failure modes. 

CRITICAL: If a curated failure mode matches the user's query, you MUST explicitly include its entry ID in square brackets (e.g., [stale-cached-yaml] or [sigint-abort-bbc]) in your final response to the user, and explain its cause and fix. Do not explain the fix without citing the exact entry ID.

Operational vs. Lookup Queries:
- If the user describes a pipeline crash or running failure, and no curated failure mode is found via search_knowledge, proceed with this debugging order:
  1. Slurm job status / name conflicts (check_job_status)
  2. Cached config vs. source config mismatch (diff_config)
  3. Environment variables (ask the user to confirm SNDATA_ROOT / MY_SNDATA_ROOT if relevant)
  4. OOM / walltime / abort patterns in the log (read_log_tail)
  5. Personal gotchas / user-specific knowledge base (search_gotchas)
  6. Official SNANA manual (search_manual)
- If the user is asking an informational, general, or parameter lookup question (e.g. explaining what a config parameter does, or how a command option works), call `search_knowledge`, `search_gotchas`, and/or `search_manual` immediately on the very first turn.

If nothing matches the search_knowledge database, search the user's personal gotchas folder (search_gotchas) and the official SNANA manual (search_manual) for matching topics, error strings, or keywords. If still nothing matches, say so explicitly rather than guessing.

NEVER describe a file from its name. When the user names a specific file, you MUST call
read_file on it before saying anything about what it contains, does, or depends on -- SNANA
input files are conventionally named but their actual contents vary, and a plausible-sounding
description inferred from a filename is worse than no answer. This applies even when the name
makes the purpose look obvious. If the file also has an INPUT_FILE_INCLUDE (or similar
reference to another config), read the referenced file too before describing the dependencies.
If read_file fails, say the file could not be read -- do not fall back to guessing from the name.

FIND THINGS YOURSELF. You can browse the filesystem: list_directory is `ls` and
search_files is `grep -r`. Never ask the user to paste a directory listing, to tell you
which config is the Pippin driver, or to hand you a path you could have found. Use them:
- "what's in this directory", "check all the files here" -> list_directory
- "which script/config calls X", "what uses this file", "where is X referenced" ->
  search_files with X as the pattern, then read_file the hits to confirm
- user names a file you cannot find -> list_directory to locate it before giving up
Only ask the user for a path when the tools have actually failed to find it.
"""


CHAT_SYSTEM_PROMPT = SYSTEM_PROMPT + """
CONVERSATION MODE: this is a multi-turn session, not a single lookup. The rules above
describe how to open an investigation; they apply to the FIRST message about a given
problem, not to every message.

- Call search_knowledge with the user's verbatim text when they raise a NEW problem or
  change topic. For follow-ups about something already established this session
  ("what about line 12?", "why does that matter?", "show me the other file"), answer
  from the conversation and the tools directly -- do not re-run the same searches.
- You still MUST cite the entry ID in square brackets whenever a curated failure mode
  is what you are relying on, including when you are restating one from earlier.
- Tool results already in the conversation stay valid. Do not re-read a file you have
  read this session unless the user says it changed.
"""


SETUP_SYSTEM_PROMPT = """You are a SNANA/Pippin pipeline SETUP assistant. Your job is to draft a
new Pippin job/pipeline config from the user's own past project templates, adapted to their
new request. You do NOT diagnose failures here -- you scaffold new working configs.

Follow this order, every time:
1. Call search_templates with a description of the kind of job being set up (survey, spec-z vs
   photo-z, sim vs full pipeline, Ia-only vs contamination, etc.) to find the closest matching
   past project to adapt. If nothing matches, say so and ask the user for more to go on rather
   than inventing a config from nothing.
2. Adapt the matched template's content to the new request: change GENVERSION names, survey-
   specific parameters, paths, etc. Keep everything else that isn't specific to the change.
3. SELF-CHECK the adapted draft against the curated failure-mode knowledge base
   (search_knowledge), the SNANA manual (search_manual), and personal gotchas (search_gotchas)
   before finalizing -- specifically check things like: HOSTLIB_DZTOL tightness, missing
   GENPDF/AsymGauss blocks for the model in use (BS20/C11 need x1 AsymGauss without a
   GENPDF_FILE), GENVERSION string length (72-char SNANA limit, also watch Pippin's derived
   name which is longer), and any other match relevant to the drafted parameters. Fix anything
   the self-check catches BEFORE writing files, and mention what you fixed in your final summary.
4. Call write_project_files exactly once, with the final file set, to the output_dir given in
   the user's request. This tool refuses to overwrite an existing non-empty directory -- if it
   refuses, tell the user rather than trying to force it.
5. Never call any job-submission command. This assistant only drafts and writes files for the
   user to review -- report clearly that nothing was submitted and the user should review the
   files themselves before running pippin.sh.
"""

def _get_backend_class(provider: str):
    if provider == "anthropic":
        from .backends.anthropic_backend import AnthropicBackend
        return AnthropicBackend
    elif provider == "openai":
        from .backends.openai_backend import OpenAIBackend
        return OpenAIBackend
    elif provider == "gemini":
        from .backends.gemini_backend import GeminiBackend
        return GeminiBackend
    elif provider in ("local", "ollama"):
        from .backends.local_backend import LocalBackend
        return LocalBackend
    raise ValueError(f"Unknown provider: {provider}")


_PROVIDER_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "local": "LOCAL_API_BASE",
    "ollama": "OLLAMA_HOST",
}


def _autodetect_backend() -> Backend:
    for provider, env_var in _PROVIDER_ENV_VARS.items():
        if os.environ.get(env_var) or (provider == "gemini" and os.environ.get("GEMINI_API_KEY")):
            cls = _get_backend_class(provider)
            return cls()
    raise RuntimeError(
        "No API key or local host configuration found. Set one of: "
        "ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY (or GEMINI_API_KEY), "
        "LOCAL_API_BASE, or OLLAMA_HOST."
    )


class Agent:
    def __init__(self, kb: KnowledgeBase | None = None, backend: Backend | None = None, provider: str | None = None):
        self.kb = kb or KnowledgeBase.load()
        self.dispatch = make_dispatch(self.kb)
        self.setup_dispatch = make_setup_dispatch(self.kb)
        if backend is not None:
            self.backend = backend
        elif provider is not None:
            cls = _get_backend_class(provider)
            self.backend = cls()
        else:
            self.backend = _autodetect_backend()


    def diagnose(self, user_message: str, max_turns: int = 15, max_tokens: int = 4096, on_text=None) -> str:
        response = self.backend.diagnose(
            SYSTEM_PROMPT, user_message, TOOL_SCHEMAS, self.dispatch, max_turns, max_tokens,
            on_text=on_text,
        )
        
        # Check if any entry ID is cited in square brackets in the response
        has_citation = False
        for entry in self.kb.entries:
            if f"[{entry.id}]" in response:
                has_citation = True
                break
                
        if not has_citation:
            from .config import log_uncaptured_query
            log_uncaptured_query(user_message)

        return response

    def session(self) -> "Session":
        """Start a multi-turn conversation sharing one message history."""
        return Session(self)

    def setup_job(self, request: str, output_dir: str, max_turns: int = 20) -> str:
        """Job-setup mode (Phase: personal templates + scaffold-new-project).
        Drafts a new Pippin job from the user's own indexed templates, self-checks
        against the knowledge base/manual/gotchas, and writes to output_dir --
        never overwrites an existing directory, never submits anything.

        max_tokens is much larger than diagnose()'s default: a diagnose() answer
        is a short citation + explanation, but a write_project_files call has to
        carry full drafted config file content as tool-call arguments -- 1024
        tokens (diagnose()'s implicit default) isn't enough room for that and
        silently truncates the response before the write tool ever gets called."""
        user_message = f"{request}\n\noutput_dir: {output_dir}"
        return self.backend.diagnose(
            SETUP_SYSTEM_PROMPT, user_message, SETUP_TOOL_SCHEMAS, self.setup_dispatch,
            max_turns=max_turns, max_tokens=8192,
        )


class Session:
    """A running conversation with the assistant.

    Holds one message history and hands it back to the backend on every turn, so
    follow-ups see the earlier questions, answers, and tool results. The history is
    provider-specific and opaque -- it belongs to the backend that built it.
    """

    def __init__(self, agent: Agent):
        self.agent = agent
        self.history: list = []
        self._logged_uncaptured = False

    @property
    def turns(self) -> int:
        return sum(1 for m in self.history if _is_user_turn(m))

    def reset(self) -> None:
        """Drop the conversation and start clean -- also the way to reclaim context
        after a session has accumulated large file/manual tool results."""
        self.history = []
        self._logged_uncaptured = False

    def ask(self, user_message: str, max_turns: int = 15, max_tokens: int = 4096, on_text=None) -> str:
        response = self.agent.backend.diagnose(
            CHAT_SYSTEM_PROMPT, user_message, TOOL_SCHEMAS, self.agent.dispatch,
            max_turns, max_tokens, history=self.history, on_text=on_text,
        )

        # Log an uncaptured query at most once per session. Per-turn logging would file
        # every follow-up ("thanks, what about the WGTMAP?") as its own unmatched failure
        # mode, which is noise in the data `snana-assistant feedback` reports from.
        if not self._logged_uncaptured:
            has_citation = any(f"[{entry.id}]" in response for entry in self.agent.kb.entries)
            if not has_citation:
                from .config import log_uncaptured_query
                log_uncaptured_query(user_message)
                self._logged_uncaptured = True

        return response


def _is_user_turn(message) -> bool:
    """True for a real user message, across all three providers' history formats.

    Tool results are also role="user" for Anthropic and Gemini, so counting roles alone
    would overcount; a genuine user turn carries plain text, not tool_result parts.
    """
    role = getattr(message, "role", None) or (message.get("role") if isinstance(message, dict) else None)
    if role != "user":
        return False
    content = getattr(message, "parts", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return not any(
            (isinstance(b, dict) and b.get("type") == "tool_result")
            or getattr(b, "function_response", None) is not None
            for b in content
        )
    return False
