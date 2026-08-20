"""Agent tools — map directly onto the pipeline-debug checklist steps:
squeue conflicts -> cached-vs-source config -> env vars -> log OOM/walltime scan.

Each tool is (JSON schema for the Claude API, Python callable). `TOOLS` is the
registry `agent.py` hands to the API and dispatches against.
"""

from __future__ import annotations

import difflib
import os
import subprocess
from pathlib import Path

from .knowledge import KnowledgeBase


def check_job_status(user: str | None = None) -> str:
    """Wraps `squeue -u $USER` — step 1 of the pipeline-debug checklist (job name
    conflicts, stuck PD/CG jobs)."""
    user = user or os.environ.get("USER", "")
    try:
        out = subprocess.run(
            ["squeue", "-u", user], capture_output=True, text=True, timeout=15, check=False
        )
    except FileNotFoundError:
        return "squeue not available on this host (not a Slurm cluster, or not in PATH)."
    if out.returncode != 0:
        return f"squeue failed: {out.stderr.strip()}"
    return out.stdout.strip() or f"No jobs currently queued/running for user {user}."


def diff_config(source_path: str, cached_path: str) -> str:
    """Diffs a source config against Pippin's cached copy — step 2 of the
    pipeline-debug checklist. This is the single most common false 'the fix
    didn't work' report."""
    src = Path(source_path)
    cached = Path(cached_path)
    for p in (src, cached):
        if not p.exists():
            return f"File not found: {p}"
    src_lines = src.read_text().splitlines(keepends=True)
    cached_lines = cached.read_text().splitlines(keepends=True)
    diff = list(difflib.unified_diff(src_lines, cached_lines, fromfile=str(src), tofile=str(cached)))
    if not diff:
        return "No difference — the cached copy matches the source. The fix should be live; look elsewhere."
    return "Source and cached copy DIFFER (this is very likely the actual bug):\n" + "".join(diff[:200])


def read_log_tail(log_path: str, n_lines: int = 200) -> str:
    """Reads the last N lines of a log file — step 4 of the pipeline-debug
    checklist (OOM / walltime / abort scan)."""
    p = Path(log_path)
    if not p.exists():
        return f"File not found: {p}"
    lines = p.read_text(errors="replace").splitlines()
    tail = lines[-n_lines:]
    flags = [l for l in tail if any(k in l for k in ("OOM", "Killed", "TIMEOUT", "DUE TO TIME LIMIT", "Segmentation fault", "FATAL ERROR"))]
    header = f"Last {len(tail)} lines of {p} ({len(flags)} flagged lines found):\n"
    if flags:
        header += "\n--- FLAGGED ---\n" + "\n".join(flags) + "\n--- END FLAGGED ---\n\n"
    return header + "\n".join(tail[-80:])  # cap raw tail shown to keep context bounded


def search_knowledge(query: str, kb: KnowledgeBase) -> str:
    """Searches the structured failure-mode knowledge base."""
    results = kb.search(query)
    if not results:
        return "No matching entries in the knowledge base."
    return "\n\n".join(e.as_context_block() for e in results)


TOOL_SCHEMAS = [
    {
        "name": "check_job_status",
        "description": "Check the user's current Slurm queue (squeue -u $USER) for job-name conflicts or stuck PD/CG jobs.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "diff_config",
        "description": "Diff a source config/YAML file against Pippin's cached copy in the output staging directory. Use this whenever a config fix doesn't seem to have taken effect.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_path": {"type": "string", "description": "Path to the source config the user edited."},
                "cached_path": {"type": "string", "description": "Path to Pippin's cached copy of the same config."},
            },
            "required": ["source_path", "cached_path"],
        },
    },
    {
        "name": "read_log_tail",
        "description": "Read the tail of a Slurm/pipeline log file and flag OOM/walltime/abort patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string"},
                "n_lines": {"type": "integer", "description": "How many trailing lines to read (default 200)."},
            },
            "required": ["log_path"],
        },
    },
    {
        "name": "search_knowledge",
        "description": "Search the curated SNANA/Pippin failure-mode knowledge base for entries matching a symptom or error text.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]


def make_dispatch(kb: KnowledgeBase):
    """Returns a {name: callable} dispatch table bound to a specific KnowledgeBase."""
    return {
        "check_job_status": lambda **kw: check_job_status(**kw),
        "diff_config": lambda **kw: diff_config(**kw),
        "read_log_tail": lambda **kw: read_log_tail(**kw),
        "search_knowledge": lambda **kw: search_knowledge(kb=kb, **kw),
    }
