"""Read-only Model Context Protocol (MCP) server for SNANA Pipeline Assistant.

Exposes deterministic, bounded, read-only diagnostic tools over standard MCP stdio protocol.
Wraps core application logic from `tools.py` and `knowledge.py` while enforcing
strict safety boundaries via `tool_policy.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .knowledge import KnowledgeBase
from .tool_policy import (
    DEFAULT_FILE_LINES,
    DEFAULT_LOG_TAIL_LINES,
    MAX_FILE_BYTES,
    MAX_FILE_LINES,
    MAX_LOG_TAIL_LINES,
    canonicalize_path,
    looks_binary,
    sanitize_environment,
)
from .tools import (
    check_job_status as _check_job_status,
    diff_config as _diff_config,
    list_directory as _list_directory,
    read_file as _read_file,
    read_log_tail as _read_log_tail,
    search_files as _search_files,
    search_manual as _search_manual,
)

# Initialize FastMCP server
mcp = FastMCP("snana-assistant")

# Shared lazy-loaded KnowledgeBase instance
_KB: Optional[KnowledgeBase] = None


def get_kb() -> KnowledgeBase:
    global _KB
    if _KB is None:
        _KB = KnowledgeBase.load()
    return _KB


@mcp.tool()
def search_knowledge(
    query: str,
    scope: Optional[str] = None,
    top_k: int = 5,
) -> str:
    """Search the curated SNANA/Pippin failure knowledge base using BM25 lexical ranking.

    Args:
        query: Symptom, error message, log fragment, or diagnostic term to search.
        scope: Optional scope filter: 'universal', 'slurm', or 'perlmutter'.
        top_k: Maximum number of ranked entries to return (default 5, max 15).
    """
    kb = get_kb()
    top_k = max(1, min(int(top_k), 15))
    scopes = (scope,) if scope in ("universal", "slurm", "perlmutter") else ("universal", "slurm", "perlmutter")

    scored_entries = kb.search_scored(query, scopes=scopes, top_k=top_k)
    if not scored_entries:
        return f"No matching entries found in knowledge base for query: '{query}'"

    blocks = []
    for score, entry in scored_entries:
        blocks.append(f"Score: {score:.2f}\n{entry.as_context_block()}")

    return f"Found {len(scored_entries)} match(es) in curated knowledge base:\n\n" + "\n\n".join(blocks)


@mcp.tool()
def search_manual(
    query: str,
    top_k: int = 3,
) -> str:
    """Search the pre-chunked SNANA reference manual index for parameter syntax, config keys, and formulas.

    Args:
        query: Manual keyword, section title, configuration keyword (e.g., 'SIMLIB', 'GENVERSION', 'HOSTLIB').
        top_k: Number of relevant manual passages to return (default 3, max 10).
    """
    top_k = max(1, min(int(top_k), 10))
    return _search_manual(query=query, top_k=top_k)


@mcp.tool()
def check_job_status(
    user: Optional[str] = None,
) -> str:
    """Read Slurm (squeue) or PBS (qstat) scheduler status for the specified user or $USER.

    Strictly read-only: does NOT submit, cancel, or modify batch jobs.

    Args:
        user: Username whose jobs to inspect. Defaults to current $USER.
    """
    return _check_job_status(user=user)


@mcp.tool()
def read_log_tail(
    log_path: str,
    n_lines: int = DEFAULT_LOG_TAIL_LINES,
) -> str:
    """Read a bounded tail from a pipeline or batch log file and flag failure signatures (OOM, killed, timeout, abort, segfault).

    Args:
        log_path: Path to the log file to inspect.
        n_lines: Number of lines to inspect from tail (default 200, max 1000).
    """
    p = canonicalize_path(log_path)
    if not p.exists():
        return f"File not found: {log_path}"
    if not p.is_file():
        return f"Not a regular file: {log_path}"
    if looks_binary(p):
        return f"Refused: {log_path} appears to be a binary file."

    bounded_lines = max(10, min(int(n_lines), MAX_LOG_TAIL_LINES))
    return _read_log_tail(log_path=str(p), n_lines=bounded_lines)


@mcp.tool()
def diff_config(
    source_path: str,
    cached_path: str,
) -> str:
    """Compare a source configuration file against Pippin's cached copy in the output staging directory.

    Identifies staged-vs-source configuration mismatches. Strictly read-only.

    Args:
        source_path: Path to the original source config file.
        cached_path: Path to the cached config copy in Pippin's staging area.
    """
    src = canonicalize_path(source_path)
    cached = canonicalize_path(cached_path)
    return _diff_config(source_path=str(src), cached_path=str(cached))


@mcp.tool()
def list_directory(
    path: str = ".",
    pattern: str = "*",
) -> str:
    """List directory contents with file sizes up to conservative limits. Truncation is explicitly reported.

    Args:
        path: Directory path to inspect (defaults to current directory '.').
        pattern: Optional fnmatch pattern to filter entries (e.g. '*.LOG', '*.input').
    """
    p = canonicalize_path(path)
    return _list_directory(path=str(p), pattern=pattern)


@mcp.tool()
def search_files(
    pattern: str,
    path: str = ".",
    glob: str = "*",
    recursive: bool = True,
) -> str:
    """Search text file contents for a string pattern across a directory (bounded grep -r).

    Never follows recursive symlink directories. Skips binary files, archives, and .git directories.

    Args:
        pattern: Substring or text pattern to search for within files.
        path: Base directory or file path to search.
        glob: File name glob filter (e.g., '*.input', '*.yml', '*.sh').
        recursive: Whether to search subdirectories recursively (capped at depth 4).
    """
    p = canonicalize_path(path)
    return _search_files(pattern=pattern, path=str(p), glob=glob, recursive=recursive)


@mcp.tool()
def read_text_file(
    file_path: str,
    max_lines: int = DEFAULT_FILE_LINES,
) -> str:
    """Read the contents of a small text or configuration file up to conservative limits (max 1000 lines, 500 KB).

    Rejects binary, FITS, gzipped, or oversized files.

    Args:
        file_path: Path to the text/config file to inspect.
        max_lines: Maximum number of lines to return (default 500, max 1000).
    """
    p = canonicalize_path(file_path)
    if not p.exists():
        return f"File not found: {file_path}"
    if not p.is_file():
        return f"Not a regular file: {file_path}"
    if looks_binary(p):
        return f"Refused: {file_path} appears to be a binary, archive, or FITS file."

    try:
        size = p.stat().st_size
        if size > MAX_FILE_BYTES:
            return (
                f"Refused: {file_path} size ({size:,} bytes) exceeds maximum allowed text limit "
                f"({MAX_FILE_BYTES:,} bytes). Use read_log_tail or search_files instead."
            )
    except OSError as e:
        return f"Could not inspect file metadata for {file_path}: {e}"

    bounded_lines = max(1, min(int(max_lines), MAX_FILE_LINES))
    return _read_file(file_path=str(p), max_lines=bounded_lines)


@mcp.tool()
def inspect_snana_environment() -> str:
    """Inspect safe, non-sensitive SNANA, Pippin, and HPC environment variables and paths.

    Never dumps full environment or sensitive secrets (tokens, keys, passwords).
    """
    env = sanitize_environment()
    if not env:
        return "No SNANA/Pippin/HPC environment variables currently detected."

    lines = ["SNANA / Pippin / HPC Environment:"]
    for k in sorted(env.keys()):
        lines.append(f"  {k} = {env[k]}")
    return "\n".join(lines)


def main():
    """CLI entrypoint for snana-assistant-mcp."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
