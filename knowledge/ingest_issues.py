#!/usr/bin/env python3
"""Ingestion script for SNANA GitHub issues (Phase 1.5).

Loads raw downloaded closed issues from raw_closed_issues.json, filters them using
symptom/error heuristics to select high-signal failure candidates, and saves them
as candidate issues for the next review step.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAW_ISSUES_PATH = Path(__file__).resolve().parent / "raw_closed_issues.json"
CANDIDATE_ISSUES_PATH = Path(__file__).resolve().parent / "candidate_issues.json"

FAILURE_KEYWORDS = [
    "error", "abort", "fail", "crash", "segfault", "compile", "wrong", 
    "unable to", "cannot", "invalid", "missing", "collision", "segmentation fault"
]

def main() -> None:
    if not RAW_ISSUES_PATH.exists():
        print(f"Error: Raw issues file not found at {RAW_ISSUES_PATH}")
        return

    with open(RAW_ISSUES_PATH) as f:
        issues = json.load(f)

    print(f"Loaded {len(issues)} raw closed issues.")

    candidates = []
    for issue in issues:
        number = issue.get("number")
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        comments = issue.get("comments") or []
        
        # Combine all text content to scan for symptoms
        all_text = f"{title}\n{body}\n" + "\n".join(c.get("body", "") or "" for c in comments)
        all_text_lower = all_text.lower()
        
        # Heuristics:
        # 1. Must contain at least one failure keyword
        has_keyword = any(k in all_text_lower for k in FAILURE_KEYWORDS)
        
        # 2. Must have some discussion (at least 1 comment) to ensure there was a resolution discussed
        has_resolution_discussion = len(comments) >= 1
        
        # 3. Exclude simple trivial descriptions (e.g. less than 20 chars)
        has_sufficient_text = len(body.strip()) > 20 or any(len(c.get("body", "").strip()) > 30 for c in comments)

        if has_keyword and has_resolution_discussion and has_sufficient_text:
            candidates.append({
                "number": number,
                "title": title,
                "body": body,
                "comments_count": len(comments),
                "comments": [
                    {
                        "author": c.get("author", {}).get("login", "unknown"),
                        "body": c.get("body", "")
                    }
                    for c in comments
                ],
                "labels": [l.get("name") for l in issue.get("labels", []) if l.get("name")]
            })

    # Sort candidates by number of comments (higher comments usually means richer debugging history)
    candidates.sort(key=lambda x: x["comments_count"], reverse=True)

    print(f"Filtered down to {len(candidates)} high-signal candidate issues.")

    with open(CANDIDATE_ISSUES_PATH, "w") as f_out:
        json.dump(candidates, f_out, indent=2)

    print(f"Saved candidate issues to {CANDIDATE_ISSUES_PATH.name}")
    print("\nTop 5 candidate issues by comment volume:")
    for c in candidates[:5]:
        print(f"  #{c['number']}: {c['title']} ({c['comments_count']} comments)")

if __name__ == "__main__":
    main()
