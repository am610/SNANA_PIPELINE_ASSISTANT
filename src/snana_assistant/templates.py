"""Personal, local-only Pippin project template index (job-setup feature).

CRITICAL DIFFERENCE FROM knowledge.py: this NEVER ships as package data and
NEVER goes into the public repo. It indexes a user's own real project
directories, which may contain embargoed or collaboration-sensitive science
configs (survey parameters, unpublished cadence/HOSTLIB choices, etc.) --
copies live only under ~/.config/snana-assistant/templates/ on the user's own
machine. `snana-assistant index-project` is opt-in per user, per directory.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TEMPLATES_ROOT = Path("~/.config/snana-assistant/templates").expanduser()
INDEX_PATH = TEMPLATES_ROOT / "index.json"

# Small text configs worth copying as adaptable templates.
TEMPLATE_SUFFIXES = {".yml", ".yaml", ".input", ".INPUT", ".nml", ".NML"}
# Bulk data files -- record the path as a reference only, never copy content
# (HOSTLIBs/SIMLIBs can be gigabytes and aren't "templates" to adapt).
DATA_REFERENCE_SUFFIXES = {".simlib", ".SIMLIB", ".hostlib", ".HOSTLIB"}
MAX_TEMPLATE_FILE_BYTES = 200_000

# Best-effort key-parameter extraction so search/self-check has something
# structured to work with without re-parsing full YAML/NML grammar.
KEY_PARAM_PATTERNS = [
    "GENVERSION", "SURVEY", "GENFILTERS", "SIMLIB_FILE", "HOSTLIB_FILE",
    "GENMODEL", "GENRANGE_REDSHIFT", "SNTYPE_LIST", "GENTYPE",
    "HOSTLIB_DZTOL", "BATCH_WALLTIME", "BATCH_MEM", "OPT_PHOTOZ",
]


def _extract_key_params(text: str) -> dict:
    found = {}
    for key in KEY_PARAM_PATTERNS:
        m = re.search(rf"^\s*{re.escape(key)}\s*[:=]\s*(.+)$", text, re.MULTILINE)
        if m:
            found[key] = m.group(1).strip().split("#")[0].split("!")[0].strip()
    return found


def _load_index() -> list[dict]:
    if not INDEX_PATH.exists():
        return []
    with open(INDEX_PATH) as f:
        return json.load(f)


def _save_index(entries: list[dict]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def index_project(source_dir: Path, project_name: str) -> dict:
    """Walks source_dir, copies small text configs into
    ~/.config/snana-assistant/templates/<project_name>/, and records bulk
    data files (SIMLIB/HOSTLIB) as path-only references. Returns a summary
    dict. Re-indexing a project name overwrites its prior entries only."""
    source_dir = Path(source_dir).expanduser().resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Not a directory: {source_dir}")

    dest_root = TEMPLATES_ROOT / project_name
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True)

    entries = [e for e in _load_index() if e.get("project") != project_name]
    now = datetime.now(timezone.utc).isoformat()
    copied, referenced = 0, 0

    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix

        if suffix in DATA_REFERENCE_SUFFIXES or path.name.endswith((".HOSTLIB.gz", ".simlib.gz")):
            entries.append({
                "project": project_name, "kind": "data_reference",
                "original_path": str(path), "relative_path": str(path.relative_to(source_dir)),
                "indexed_at": now,
            })
            referenced += 1
            continue

        if suffix not in TEMPLATE_SUFFIXES:
            continue
        try:
            size = path.stat().st_size
            if size > MAX_TEMPLATE_FILE_BYTES:
                continue
            text = path.read_text(errors="replace")
        except Exception:
            continue

        rel = path.relative_to(source_dir)
        dest_path = dest_root / rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(text)

        entries.append({
            "project": project_name, "kind": "template",
            "relative_path": str(rel), "stored_path": str(dest_path),
            "key_params": _extract_key_params(text), "indexed_at": now,
        })
        copied += 1

    _save_index(entries)
    return {"project": project_name, "templates_copied": copied, "data_files_referenced": referenced}


def search(query: str, top_k: int = 5) -> list[dict]:
    """Simple keyword-overlap ranking over project name + relative path +
    key params -- same v1 tradeoff as knowledge.py's original search: this
    corpus is small (a handful of indexed projects) and easy to eyeball,
    not worth embeddings yet."""
    entries = [e for e in _load_index() if e.get("kind") == "template"]
    terms = set(re.findall(r"[a-z0-9_]+", query.lower()))
    if not terms:
        return []

    scored = []
    for e in entries:
        haystack = f"{e['project']} {e['relative_path']} {json.dumps(e.get('key_params', {}))}".lower()
        haystack_words = set(re.findall(r"[a-z0-9_]+", haystack))
        score = sum(1 for t in terms if t in haystack_words or any(t in w for w in haystack_words))
        if score > 0:
            scored.append((score, e))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [e for _, e in scored[:top_k]]


def read_template(stored_path: str) -> str:
    return Path(stored_path).read_text(errors="replace")


def list_projects() -> list[str]:
    return sorted({e["project"] for e in _load_index()})
