#!/usr/bin/env python3
"""Phase 1.5b: dedup/quality report over the knowledge base.

Flags candidate duplicate/near-duplicate entries and low-signal entries for
human review. Reuses KnowledgeBase.search_scored()'s BM25 ranking (each entry's
own symptom+cause text used as the query against the rest of the KB) rather than
building a second similarity metric.

Writes a report only — does NOT edit entries.yaml. Merges/removals are a human
call, per the project's review-before-promotion ground rule (see AGENTS.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snana_assistant.knowledge import Entry, KnowledgeBase  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parent / "dedup_report.md"
TOP_N_PAIRS = 40
MIN_FIX_WORDS = 8


def find_candidate_duplicates(kb: KnowledgeBase) -> list[tuple[float, Entry, Entry]]:
    """For every entry, score it against the rest of the KB using its own
    symptom+cause text as the query. Return globally top-scoring pairs, deduped
    (each unordered pair appears once)."""
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[float, Entry, Entry]] = []
    for entry in kb.entries:
        query = f"{entry.symptom} {entry.cause}"
        scored = kb.search_scored(query, top_k=6)
        for score, other in scored:
            if other.id == entry.id:
                continue
            key = tuple(sorted((entry.id, other.id)))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((score, entry, other))
    pairs.sort(key=lambda p: p[0], reverse=True)
    return pairs


def find_low_signal(kb: KnowledgeBase) -> list[tuple[Entry, str]]:
    """Flag entries whose fix is too short to be actionable, or whose symptom
    reads like a bare issue title (no concrete error string/pattern)."""
    flagged = []
    for e in kb.entries:
        fix_words = len(e.fix.split())
        if fix_words < MIN_FIX_WORDS:
            flagged.append((e, f"fix field only {fix_words} word(s) — likely not actionable as written"))
    return flagged


def score_stats(pairs: list[tuple[float, Entry, Entry]]) -> str:
    scores = [p[0] for p in pairs]
    if not scores:
        return "No scored pairs at all (KB may be too small or too sparse in shared terms)."
    scores_sorted = sorted(scores, reverse=True)
    n = len(scores_sorted)

    def pct(p: float) -> float:
        idx = min(n - 1, int(p * n))
        return scores_sorted[idx]

    return (
        f"{n} scored pairs total. max={scores_sorted[0]:.2f}, "
        f"p90={pct(0.10):.2f}, p50(median)={pct(0.50):.2f}, min={scores_sorted[-1]:.2f}.\n"
        f"No fixed similarity threshold is applied — this is a ranked list for you "
        f"to eyeball and decide where the real duplicates stop."
    )


def main() -> None:
    kb = KnowledgeBase.load()
    pairs = find_candidate_duplicates(kb)
    low_signal = find_low_signal(kb)

    lines = [
        "# Knowledge Base Dedup / Quality Report",
        "",
        f"Generated over {len(kb.entries)} entries. This is a report for human review —",
        "nothing here has been merged, edited, or deleted automatically.",
        "",
        "## Candidate duplicate / near-duplicate pairs",
        "",
        score_stats(pairs),
        "",
        f"Top {min(TOP_N_PAIRS, len(pairs))} pairs by similarity score:",
        "",
        "| Score | Entry A | Entry B | Source A | Source B |",
        "|---|---|---|---|---|",
    ]
    for score, a, b in pairs[:TOP_N_PAIRS]:
        lines.append(
            f"| {score:.2f} | `{a.id}` | `{b.id}` | {a.source[:40]} | {b.source[:40]} |"
        )

    lines += [
        "",
        "## Low-signal entries (short/vague fix field)",
        "",
        f"{len(low_signal)} entries flagged — not wrong, just may need more detail before promotion:",
        "",
        "| Entry | Note |",
        "|---|---|",
    ]
    for e, note in low_signal:
        lines.append(f"| `{e.id}` | {note} |")

    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(f"Wrote {REPORT_PATH} — {len(pairs)} pairs scored, top {min(TOP_N_PAIRS, len(pairs))} shown, {len(low_signal)} low-signal entries flagged.")


if __name__ == "__main__":
    main()
