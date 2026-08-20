"""Loads and queries the structured failure-mode knowledge base.

v1 design choice: at ~8-20 entries the whole knowledge base fits comfortably in a
single prompt, so `search()` does simple keyword overlap rather than embeddings.
The interface is written so Phase 2/3 (a growing, reviewed knowledge base) can swap
in real vector retrieval later without changing any call site — see ROADMAP.md
design principle #4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_KNOWLEDGE_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "entries.yaml"


@dataclass
class Entry:
    id: str
    symptom: str
    cause: str
    fix: str
    scope: str  # universal | slurm | perlmutter
    status: str  # verified | unverified
    source: str

    def as_context_block(self) -> str:
        return (
            f"[{self.id}] (scope={self.scope}, status={self.status})\n"
            f"  symptom: {self.symptom.strip()}\n"
            f"  cause:   {self.cause.strip()}\n"
            f"  fix:     {self.fix.strip()}\n"
            f"  source:  {self.source.strip()}"
        )


@dataclass
class KnowledgeBase:
    entries: list[Entry] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | str = DEFAULT_KNOWLEDGE_PATH) -> "KnowledgeBase":
        with open(path) as f:
            raw = yaml.safe_load(f)
        return cls(entries=[Entry(**e) for e in raw])

    def search(self, query: str, scopes: tuple[str, ...] = ("universal", "slurm", "perlmutter"), top_k: int = 5) -> list[Entry]:
        """Keyword-overlap ranking. Replace with embeddings when the KB outgrows a single prompt."""
        terms = set(re.findall(r"[a-z0-9_]+", query.lower()))
        scored = []
        for e in self.entries:
            if e.scope not in scopes:
                continue
            haystack = f"{e.symptom} {e.cause} {e.fix} {e.id}".lower()
            score = sum(1 for t in terms if t in haystack)
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [e for _, e in scored[:top_k]] or self.entries[:top_k]  # fall back to showing something

    def all_as_context(self, scopes: tuple[str, ...] = ("universal", "slurm", "perlmutter")) -> str:
        blocks = [e.as_context_block() for e in self.entries if e.scope in scopes]
        return "\n\n".join(blocks)
