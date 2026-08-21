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

DEFAULT_KNOWLEDGE_PATH = Path(__file__).resolve().parent / "data" / "entries.yaml"
if not DEFAULT_KNOWLEDGE_PATH.exists():
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
        """Lexical search using BM25 ranking (pure Python, Phase 1.7)."""
        import math
        from collections import Counter

        query_terms = re.findall(r"[a-z0-9_]+", query.lower())
        stop_words = {"the", "a", "an", "is", "of", "to", "in", "but", "it", "and", "or", "for", "with", "as", "by", "at", "from", "on", "re", "be", "this", "that"}
        query_terms = [t for t in query_terms if t not in stop_words]
        if not query_terms:
            return []

        # Filter entries by scope first
        filtered_entries = [e for e in self.entries if e.scope in scopes]
        if not filtered_entries:
            return []

        # Tokenize each entry's haystack
        corpus = []
        entry_haystacks = []
        for e in filtered_entries:
            haystack = f"{e.symptom} {e.cause} {e.fix} {e.id} {e.source}".lower()
            words = [w for w in re.findall(r"[a-z0-9_]+", haystack) if w not in stop_words]
            corpus.append(words)
            entry_haystacks.append(words)

        # Build BM25 index on the fly
        corpus_size = len(corpus)
        avg_doc_len = sum(len(doc) for doc in corpus) / corpus_size if corpus_size > 0 else 1.0
        doc_lens = [len(doc) for doc in corpus]
        
        # Compute doc frequencies
        doc_freqs = Counter()
        for doc in corpus:
            for word in set(doc):
                doc_freqs[word] += 1
                
        # Compute IDFs
        idfs = {}
        for word, freq in doc_freqs.items():
            idfs[word] = math.log((corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

        # Score each document
        k1 = 1.5
        b = 0.75
        scored_entries = []
        
        for idx, entry in enumerate(filtered_entries):
            doc_words = entry_haystacks[idx]
            doc_len = doc_lens[idx]
            word_counts = Counter(doc_words)
            score = 0.0
            
            for q in query_terms:
                freq = word_counts.get(q, 0.0)
                
                # Suffix/prefix/substring matching fallback if no exact word match
                if freq == 0.0:
                    for word, count in word_counts.items():
                        min_len = min(len(q), len(word))
                        if min_len >= 4:
                            prefix_len = 0
                            while prefix_len < min_len and q[prefix_len] == word[prefix_len]:
                                prefix_len += 1
                            if prefix_len >= 4:
                                freq += 0.5 * count
                                break
                        if len(q) >= 3 and len(word) >= 3 and (q in word or word in q):
                            freq += 0.25 * count
                            break
                            
                if freq == 0.0:
                    continue
                    
                # IDF calculation
                idf = idfs.get(q, math.log(corpus_size + 1.0))
                numerator = freq * (k1 + 1.0)
                denominator = freq + k1 * (1.0 - b + b * (doc_len / avg_doc_len))
                score += idf * (numerator / denominator)
                
            if score > 0.0:
                scored_entries.append((score, entry))

        scored_entries.sort(key=lambda pair: pair[0], reverse=True)
        return [e for _, e in scored_entries[:top_k]]

    def all_as_context(self, scopes: tuple[str, ...] = ("universal", "slurm", "perlmutter")) -> str:
        blocks = [e.as_context_block() for e in self.entries if e.scope in scopes]
        return "\n\n".join(blocks)

    def promote(self, entry_id: str, path: Path | str = DEFAULT_KNOWLEDGE_PATH) -> bool:
        """Promotes an entry from unverified to verified and saves it back to the YAML file."""
        found = False
        for entry in self.entries:
            if entry.id == entry_id:
                if entry.status == "verified":
                    print(f"Entry '{entry_id}' is already verified.")
                    return False
                entry.status = "verified"
                found = True
                break
        
        if not found:
            print(f"Error: Entry '{entry_id}' not found in the knowledge base.")
            return False

        # Save back to YAML
        raw_list = []
        for e in self.entries:
            raw_list.append({
                "id": e.id,
                "symptom": e.symptom,
                "cause": e.cause,
                "fix": e.fix,
                "scope": e.scope,
                "status": e.status,
                "source": e.source
            })
        
        with open(path, "w") as f:
            yaml.safe_dump(raw_list, f, sort_keys=False, default_flow_style=False)
            
        return True

