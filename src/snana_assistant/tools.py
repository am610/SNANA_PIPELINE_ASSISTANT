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


def read_file(file_path: str, max_lines: int = 500) -> str:
    """Reads the contents of a file (up to max_lines) to check configuration parameters or input settings."""
    p = Path(file_path)
    if not p.exists():
        return f"File not found: {p}"
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        content = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            content += f"\n... [TRUNCATED, showing first {max_lines} of {len(lines)} lines] ..."
        return content
    except Exception as exc:
        return f"Failed to read {p}: {exc}"


# Bounds for the directory tools. A Pippin output tree is enormous and full of FITS/
# gzipped sim output: an unbounded walk would blow the context budget long before it
# found anything useful, so every limit below is deliberately conservative and any
# truncation is reported rather than silently applied.
_MAX_ENTRIES = 200
_MAX_HITS = 50
_MAX_DEPTH = 4
_SKIP_DIRS = {".git", "__pycache__", ".ipynb_checkpoints", "node_modules", ".venv"}
_BINARY_SUFFIXES = {
    ".fits", ".gz", ".tar", ".zip", ".npy", ".npz", ".pdf", ".png", ".jpg", ".jpeg",
    ".pyc", ".so", ".o", ".root", ".hdf5", ".h5", ".pkl", ".parquet",
}


def _looks_binary(p: Path) -> bool:
    if p.suffix.lower() in _BINARY_SUFFIXES:
        return True
    try:
        with open(p, "rb") as f:
            return b"\0" in f.read(2048)
    except Exception:
        return True


def list_directory(path: str = ".", pattern: str = "*") -> str:
    """List directory contents -- the equivalent of `ls`, so the assistant can discover
    which files exist instead of asking the user to paste an `ls` in."""
    import fnmatch

    d = Path(path).expanduser()
    if not d.exists():
        return f"Directory not found: {d}"
    if not d.is_dir():
        return f"Not a directory: {d} (use read_file for a single file)"
    try:
        entries = sorted(d.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return f"Permission denied: {d}"

    rows, shown = [], 0
    for e in entries:
        if e.name.startswith("."):
            continue
        if not e.is_dir() and not fnmatch.fnmatch(e.name, pattern):
            continue
        if shown >= _MAX_ENTRIES:
            rows.append(f"... [TRUNCATED at {_MAX_ENTRIES} entries; narrow with `pattern`]")
            break
        if e.is_dir():
            rows.append(f"{e.name}/")
        else:
            try:
                rows.append(f"{e.name}  ({e.stat().st_size:,} bytes)")
            except OSError:
                rows.append(e.name)
        shown += 1

    if not rows:
        return f"No entries matching {pattern!r} in {d}"
    return f"{d} ({shown} shown):\n" + "\n".join(f"  {r}" for r in rows)


def search_files(pattern: str, path: str = ".", glob: str = "*", recursive: bool = True) -> str:
    """Search file *contents* for a string -- a bounded `grep -r`.

    This is what answers "which script calls this input file?": grep the filename across
    the directory and the calling Pippin YAML / submit script falls out directly, instead
    of being inferred from naming convention.
    """
    import fnmatch

    root = Path(path).expanduser()
    if not root.exists():
        return f"Path not found: {root}"
    needle = pattern.lower()
    hits, scanned, truncated = [], 0, False

    def walk(d: Path, depth: int):
        nonlocal truncated
        if truncated or depth > _MAX_DEPTH:
            return
        try:
            entries = sorted(d.iterdir())
        except (PermissionError, OSError):
            return
        for e in entries:
            if truncated:
                return
            if e.is_symlink():
                continue  # /project2 is dense with symlinks; following them can loop
            if e.is_dir():
                if recursive and e.name not in _SKIP_DIRS and not e.name.startswith("."):
                    walk(e, depth + 1)
                continue
            if not fnmatch.fnmatch(e.name, glob) or _looks_binary(e):
                continue
            scan_file(e)

    def scan_file(f: Path):
        nonlocal scanned, truncated
        scanned += 1
        try:
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if needle in line.lower():
                    if len(hits) >= _MAX_HITS:
                        truncated = True
                        return
                    hits.append(f"{f}:{n}: {line.strip()[:200]}")
        except Exception:
            return

    if root.is_file():
        scan_file(root)
    else:
        walk(root, 0)

    if not hits:
        return f"No matches for {pattern!r} in {root} ({scanned} text files searched)."
    out = f"{len(hits)} match(es) for {pattern!r} in {root} ({scanned} text files searched):\n"
    out += "\n".join(f"  {h}" for h in hits)
    if truncated:
        out += f"\n... [TRUNCATED at {_MAX_HITS} matches; narrow with `glob` or a more specific pattern]"
    return out


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


def search_templates(query: str) -> str:
    """Job-setup mode only. Searches the user's own locally-indexed Pippin
    project templates (never the public knowledge base) for the closest
    matching past config to adapt. See templates.py -- this data never
    leaves the user's machine."""
    from . import templates

    results = templates.search(query)
    if not results:
        projects = templates.list_projects()
        hint = f" Indexed projects: {', '.join(projects)}." if projects else " No projects indexed yet -- run `snana-assistant index-project <path> --name <name>` first."
        return "No matching templates found." + hint

    blocks = []
    for e in results:
        content = templates.read_template(e["stored_path"])
        if len(content) > 4000:
            content = content[:4000] + "\n... [TRUNCATED, read full file at stored_path if needed] ..."
        params = e.get("key_params", {})
        blocks.append(
            f"[project={e['project']}, file={e['relative_path']}]\n"
            f"key_params: {params}\n"
            f"--- content ---\n{content}"
        )
    return "\n\n".join(blocks)


def write_project_files(output_dir: str, files: dict) -> str:
    """Job-setup mode only. Writes a NEW project's draft config files.
    Refuses if output_dir already exists and is non-empty -- this tool can
    scaffold a fresh project, never overwrite or modify an existing one, and
    never submits any job. `files` is {relative_path: content}."""
    out = Path(output_dir).expanduser()
    if out.exists() and any(out.iterdir()):
        return f"Refused: {out} already exists and is not empty. Choose a new, empty output directory."

    out.mkdir(parents=True, exist_ok=True)
    written = []
    for rel_path, content in files.items():
        dest = out / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        written.append(str(dest))

    return (
        f"Wrote {len(written)} file(s) to {out}:\n" + "\n".join(f"  - {w}" for w in written) +
        "\n\nNothing was submitted. Review these files, then run pippin.sh yourself when ready."
    )


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
        "name": "list_directory",
        "description": "List the files and subdirectories in a directory, like `ls`. Use this to discover what exists before guessing at filenames -- e.g. to find the Pippin YAML, submit script, or log files in the user's working directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to list (default '.', the current working directory)."},
                "pattern": {"type": "string", "description": "Optional glob to filter files, e.g. '*.yml' or '*.input'. Directories are always shown."},
            },
            "required": [],
        },
    },
    {
        "name": "search_files",
        "description": "Search file CONTENTS for a string across a directory tree, like `grep -r`. This is how you find which script or config references something: to answer 'what calls sim_ia_salt_des5yr.input?', search for that filename with glob '*.yml' or '*'. Returns file:line: matched-text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Text to search for (case-insensitive substring, not a regex)."},
                "path": {"type": "string", "description": "Directory or file to search (default '.')."},
                "glob": {"type": "string", "description": "Only search files matching this glob, e.g. '*.yml' or '*.input' (default '*')."},
                "recursive": {"type": "boolean", "description": "Recurse into subdirectories (default true, max depth 4)."},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a configuration, input, or text file on disk to check parameter settings and options.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative or absolute path to the file to read (e.g. 'sim_ia_salt_des5yr.input')."},
                "max_lines": {"type": "integer", "description": "Maximum number of lines to read (default 500)."}
            },
            "required": ["file_path"]
        }
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


SETUP_TOOL_SCHEMAS = [
    {
        "name": "search_templates",
        "description": "Search the user's own locally-indexed past Pippin project configs for the closest match to adapt for a new job. Always call this first in setup mode.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Describe the kind of job/survey/pipeline stage being set up."}},
            "required": ["query"],
        },
    },
    {
        "name": "search_knowledge",
        "description": "Search the curated SNANA/Pippin failure-mode knowledge base. Use this to self-check drafted parameters (e.g. HOSTLIB_DZTOL, GENPDF/AsymGauss blocks, GENVERSION length) against known failure modes before finalizing.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "search_manual",
        "description": "Search the SNANA manual for parameter details while drafting the config.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "search_gotchas",
        "description": "Search the user's personal gotchas/session notes for relevant setup precedent.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "write_project_files",
        "description": "Write the final drafted config file(s) to a NEW, empty output directory. Refuses if the directory already exists and is non-empty. Never submits any job. Call this exactly once, after self-checking the draft.",
        "input_schema": {
            "type": "object",
            "properties": {
                "output_dir": {"type": "string"},
                "files": {
                    "type": "object",
                    "description": "Map of relative file path -> full file content, e.g. {'my_pipeline.yml': '...', 'Inputs/sim.input': '...'}",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["output_dir", "files"],
        },
    },
]


def make_dispatch(kb: KnowledgeBase):
    """Returns a {name: callable} dispatch table bound to a specific KnowledgeBase."""
    return {
        "check_job_status": lambda **kw: check_job_status(**kw),
        "diff_config": lambda **kw: diff_config(**kw),
        "read_log_tail": lambda **kw: read_log_tail(**kw),
        "read_file": lambda **kw: read_file(**kw),
        "list_directory": lambda **kw: list_directory(**kw),
        "search_files": lambda **kw: search_files(**kw),
        "search_knowledge": lambda **kw: search_knowledge(kb=kb, **kw),
        "search_manual": lambda **kw: search_manual(**kw),
        "search_gotchas": lambda **kw: search_gotchas(**kw),
    }


def make_setup_dispatch(kb: KnowledgeBase):
    """Dispatch table for job-setup mode -- adds search_templates and the
    single scoped write tool, drops the diagnose-only tools (squeue/diff/log
    tail aren't relevant to drafting a new job)."""
    return {
        "search_templates": lambda **kw: search_templates(**kw),
        "search_knowledge": lambda **kw: search_knowledge(kb=kb, **kw),
        "search_manual": lambda **kw: search_manual(**kw),
        "search_gotchas": lambda **kw: search_gotchas(**kw),
        "write_project_files": lambda **kw: write_project_files(**kw),
    }


