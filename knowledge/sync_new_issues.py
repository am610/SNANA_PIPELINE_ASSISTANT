#!/usr/bin/env python3
"""Phase 2(a): scheduled incremental ingestion of newly-closed GitHub issues.

Run weekly (see .github/workflows/weekly-ingest.yml) or manually. Finds issues
on RickKessler/SNANA that closed since the last run, applies the same
high-signal filter used for the original 1,294-issue dump (ingest_issues.py's
is_high_signal), summarizes qualifying ones with the LLM (batch_summarize.py's
summarize_issue), and appends them to entries.yaml as status: unverified.

State (knowledge/.ingest_state.json) tracks which issue numbers have already
been checked, not just a date cutoff -- a low-numbered issue can close well
after a higher-numbered one, so date-only watermarking would miss it. On first
run (no state file), the numbers already present in raw_closed_issues.json
seed the "already seen" set, and last_synced_at defaults to today -- this
script's job is catching NEW closures going forward, not backfilling the
original Phase 1.5 dump.

Requires: `gh` CLI authenticated (GH_TOKEN/GITHUB_TOKEN env var in CI), plus
whichever LLM API key the Agent picks up (ANTHROPIC_API_KEY etc.).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingest_issues import is_high_signal  # noqa: E402
from batch_summarize import summarize_issue  # noqa: E402
from snana_assistant.agent import Agent  # noqa: E402
import yaml  # noqa: E402

REPO = "RickKessler/SNANA"
STATE_PATH = Path(__file__).resolve().parent / ".ingest_state.json"
RAW_ISSUES_PATH = Path(__file__).resolve().parent / "raw_closed_issues.json"
ENTRIES_PATH = Path(__file__).resolve().parent / "entries.yaml"
PACKAGE_DATA_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "snana_assistant" / "data" / "entries.yaml"
)


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    # First run: seed from the original snapshot rather than reprocessing it.
    seen = []
    if RAW_ISSUES_PATH.exists():
        with open(RAW_ISSUES_PATH) as f:
            seen = [i["number"] for i in json.load(f)]
    return {"last_synced_at": date.today().isoformat(), "seen_issue_numbers": seen}


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def fetch_closed_since(since_date: str) -> list[dict]:
    """Search-API results are lightweight (number/title only) -- enough to
    diff against seen_issue_numbers before paying for a full fetch."""
    result = subprocess.run(
        [
            "gh", "api", "-X", "GET", "search/issues",
            "-f", f"q=repo:{REPO} is:issue is:closed closed:>={since_date}",
            "--paginate",
            "--jq", ".items[] | {number, title}",
        ],
        capture_output=True, text=True, check=True,
    )
    # --jq with --paginate emits one JSON object per line, not a single array.
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def fetch_full_issue(number: int) -> dict:
    result = subprocess.run(
        ["gh", "issue", "view", str(number), "--repo", REPO, "--json", "number,title,body,comments"],
        capture_output=True, text=True, check=True,
    )
    raw = json.loads(result.stdout)
    return {
        "number": raw["number"],
        "title": raw["title"],
        "body": raw.get("body") or "",
        "comments": [
            {"author": c.get("author", {}).get("login", "unknown"), "body": c.get("body", "")}
            for c in raw.get("comments", [])
        ],
    }


def sync_package_data() -> None:
    PACKAGE_DATA_PATH.write_text(ENTRIES_PATH.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync newly-closed SNANA GitHub issues into entries.yaml")
    parser.add_argument("--max-issues", type=int, default=20, help="Safety cap on LLM calls per run.")
    parser.add_argument("--dry-run", action="store_true", help="List what would be processed, call nothing.")
    parser.add_argument("--provider", choices=["anthropic", "openai", "gemini"], default=None)
    args = parser.parse_args()

    state = load_state()
    seen = set(state["seen_issue_numbers"])

    print(f"Checking for issues closed since {state['last_synced_at']}...")
    try:
        candidates = fetch_closed_since(state["last_synced_at"])
    except subprocess.CalledProcessError as exc:
        print(f"gh api search failed: {exc.stderr}", file=sys.stderr)
        sys.exit(1)

    new_numbers = [c["number"] for c in candidates if c["number"] not in seen]
    print(f"Found {len(candidates)} closed issues in range, {len(new_numbers)} not yet seen.")

    if len(new_numbers) > args.max_issues:
        print(f"Capping to {args.max_issues} of {len(new_numbers)} (safety limit) -- rest picked up next run.")
        new_numbers = new_numbers[: args.max_issues]

    if args.dry_run:
        print("Dry run -- would check:", new_numbers)
        return

    if not new_numbers:
        state["last_synced_at"] = date.today().isoformat()
        save_state(state)
        print("Nothing new. State updated, no LLM calls made.")
        return

    agent = Agent(provider=args.provider)
    print(f"Using backend: {agent.backend.__class__.__name__}")

    with open(ENTRIES_PATH) as f:
        current_entries = yaml.safe_load(f) or []
    existing_ids = {e.get("id") for e in current_entries}

    added = 0
    for num in new_numbers:
        issue = fetch_full_issue(num)
        seen.add(num)  # mark checked either way, so a low-signal issue isn't re-fetched every run

        if not is_high_signal(issue):
            print(f"#{num}: below signal threshold, skipping.")
            continue

        print(f"#{num}: {issue['title']} -- summarizing...")
        try:
            parsed = summarize_issue(issue, agent)
        except Exception as exc:
            print(f"#{num}: LLM call failed: {exc}", file=sys.stderr)
            continue

        if parsed is None:
            print(f"#{num}: LLM response was not parseable YAML, skipping.", file=sys.stderr)
            continue

        new_entries = [e for e in parsed if e.get("id") not in existing_ids]
        if new_entries:
            current_entries.extend(new_entries)
            existing_ids.update(e["id"] for e in new_entries)
            added += len(new_entries)
            print(f"#{num}: added {len(new_entries)} entry/entries.")
        else:
            print(f"#{num}: no new unique entries (id already exists).")

    if added:
        with open(ENTRIES_PATH, "w") as f:
            yaml.safe_dump(current_entries, f, sort_keys=False, default_flow_style=False)
        sync_package_data()

    state["seen_issue_numbers"] = sorted(seen)
    state["last_synced_at"] = date.today().isoformat()
    save_state(state)

    print(f"\nDone. {added} new unverified entries added. State advanced to {state['last_synced_at']}.")


if __name__ == "__main__":
    main()
