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
    """Wraps squeue (Slurm) or qstat (PBS) to check scheduler state — step 1 of the pipeline-debug checklist."""
    user = user or os.environ.get("USER", "")
    
    # Try squeue (Slurm)
    try:
        out = subprocess.run(
            ["squeue", "-u", user], capture_output=True, text=True, timeout=15, check=False
        )
        if out.returncode == 0:
            return out.stdout.strip() or f"No jobs currently queued/running for user {user}."
    except FileNotFoundError:
        pass
        
    # Try qstat (PBS)
    try:
        out = subprocess.run(
            ["qstat", "-u", user], capture_output=True, text=True, timeout=15, check=False
        )
        if out.returncode == 0:
            return out.stdout.strip() or f"No jobs currently queued/running for user {user}."
    except FileNotFoundError:
        pass
        
    return "No supported scheduler (squeue/qstat) found on this host."


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


DEFAULT_MANUAL_INDEX_PATH = Path(__file__).resolve().parent / "data" / "manual_chunks.json"
if not DEFAULT_MANUAL_INDEX_PATH.exists():
    DEFAULT_MANUAL_INDEX_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "manual_chunks.json"



def search_manual(query: str, manual_index_path: str | None = None, top_k: int = 3) -> str:
    """Search the pre-chunked SNANA manual index (Phase 1.6)."""
    if not manual_index_path:
        manual_index_path = os.environ.get("SNANA_MANUAL_INDEX_PATH") or str(DEFAULT_MANUAL_INDEX_PATH)
        
    p = Path(manual_index_path)
    if not p.exists():
        return f"Manual index file not found at {manual_index_path}."

    import json
    import re
    try:
        with open(p) as f:
            chunks = json.load(f)
    except Exception as e:
        return f"Error reading manual index: {e}"

    query_lower = query.lower()
    terms = set(re.findall(r"[a-z0-9_]+", query_lower))
    stop_words = {"the", "a", "an", "is", "of", "to", "in", "but", "it", "and", "or", "for", "with", "as", "by", "at", "from", "on", "re", "be", "this", "that"}
    terms = terms - stop_words
    if not terms:
        return "No search terms provided."

    scored = []
    for chunk in chunks:
        # Score the text and titles
        title_text = f"{chunk.get('section', '')} {chunk.get('subsection', '')} {chunk.get('subsubsection', '')}".lower()
        chunk_text = chunk.get("text", "").lower()
        
        score = 0
        title_words = set(re.findall(r"[a-z0-9_]+", title_text)) - stop_words
        chunk_words = set(re.findall(r"[a-z0-9_]+", chunk_text)) - stop_words
        
        for t in terms:
            # Match in titles (high weight)
            if t in title_words:
                score += 5
            else:
                for tw in title_words:
                    if len(t) >= 4 and len(tw) >= 4 and t[:4] == tw[:4]:
                        score += 3
                        break
            
            # Match in chunk text
            if t in chunk_words:
                score += 3
            else:
                for cw in chunk_words:
                    if len(t) >= 4 and len(cw) >= 4 and t[:4] == cw[:4]:
                        score += 2
                        break
                    if len(t) >= 3 and len(cw) >= 3 and (t in cw or cw in t):
                        score += 1
                        break
        
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    if not scored:
        return f"No occurrences of '{query}' found in the SNANA manual."

    results = []
    for score, chunk in scored[:top_k]:
        header_parts = []
        if chunk.get("section"):
            header_parts.append(chunk["section"])
        if chunk.get("subsection"):
            header_parts.append(chunk["subsection"])
        if chunk.get("subsubsection"):
            header_parts.append(chunk["subsubsection"])
        header = " > ".join(header_parts)
        
        results.append(
            f"=== Section: {header} (lines {chunk['start_line']}-{chunk['end_line']}, Score: {score}) ===\n"
            f"{chunk['text']}\n"
        )
    
    return f"Found {len(scored)} relevant sections in the manual. Showing top {top_k}:\n\n" + "\n\n".join(results)


def search_knowledge(query: str, kb: KnowledgeBase) -> str:
    """Searches the structured failure-mode knowledge base."""
    results = kb.search(query)
    if not results:
        return "No matching entries in the knowledge base."
    return "\n\n".join(e.as_context_block() for e in results)


def search_gotchas(query: str, gotchas_dir: str | None = None, window: int = 10) -> str:
    """Search the user's custom gotchas and SNANA knowledge files (~/.claude/snana-knowledge/*.md)."""
    if not gotchas_dir:
        gotchas_dir = os.environ.get("SNANA_GOTCHAS_DIR") or "~/.claude/snana-knowledge"
        
    base_path = Path(gotchas_dir).expanduser()
    if not base_path.exists():
        return (
            f"Gotchas directory not found. Checked path: {gotchas_dir}.\n"
            "If you have personal gotchas/notes, set SNANA_GOTCHAS_DIR in your environment or .env file."
        )
        
    md_files = list(base_path.glob("*.md"))
    if not md_files:
        return "No gotcha files found."
        
    query_lower = query.lower()
    matches = []
    
    for fpath in md_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
            
        lines = content.splitlines()
        file_matches = []
        for idx, line in enumerate(lines):
            if query_lower in line.lower():
                file_matches.append(idx)
                
        if not file_matches:
            continue
            
        # Group match indices
        groups = []
        current_group = []
        for idx in file_matches:
            if not current_group or idx - current_group[-1] < window:
                current_group.append(idx)
            else:
                groups.append(current_group)
                current_group = [idx]
        if current_group:
            groups.append(current_group)
            
        # Extract context
        for g in groups[:3]:  # cap at top 3 per file
            start = max(0, g[0] - window)
            end = min(len(lines), g[-1] + window + 1)
            chunk = []
            for i in range(start, end):
                prefix = "MATCH >>> " if i in g else "          "
                chunk.append(f"{prefix}{i+1}: {lines[i]}")
            matches.append(f"[{fpath.name} (lines {start+1}-{end})]:\n" + "\n".join(chunk))
            
    if not matches:
        return f"No occurrences of '{query}' found in your gotchas folder."
        
    result = f"Found matches in your gotchas folder:\n\n" + "\n\n".join(matches)
    if len(result) > 15000:
        result = result[:15000] + "\n... [TRUNCATED] ..."
    return result


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
    {
        "name": "search_manual",
        "description": "Search the raw LaTeX source of the SNANA Manual for details on command options, config parameters, and program operations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The parameter name, command, or option to search for (e.g. 'OPT_PHOTOZ', 'NBR_LIST', 'sigmb_biascor')."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_gotchas",
        "description": "Search the user's personal/custom SNANA and Pippin gotchas, tips, and session logs (~/.claude/snana-knowledge/*.md) for specific error resolutions, directory pathways, or cluster configurations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The gotcha topic or error string to search for (e.g. 'Euclid', 'scone', 'zHOST')."}
            },
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
        "search_manual": lambda **kw: search_manual(**kw),
        "search_gotchas": lambda **kw: search_gotchas(**kw),
    }


