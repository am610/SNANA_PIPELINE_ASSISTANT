#!/usr/bin/env python3
"""Summarizes a single GitHub issue candidate into a structured knowledge-base entry (Phase 1.5).

Takes an issue number, prepares an LLM prompt with the issue body and comments, and asks
the Agent's LLM backend to output a structured YAML block matching the entries.yaml schema.
"""

from __future__ import annotations

import argparse
import json
import sys
import yaml
from pathlib import Path

from snana_assistant.agent import Agent

CANDIDATES_PATH = Path(__file__).resolve().parent / "candidate_issues.json"
ENTRIES_PATH = Path(__file__).resolve().parent / "entries.yaml"

SUMMARIZE_PROMPT_TEMPLATE = """You are parsing a closed GitHub issue from the RickKessler/SNANA repository.
Your goal is to extract a structured failure-mode knowledge base entry from it.

Here is the issue information:
Number: #{number}
Title: {title}

Description:
{body}

Discussion/Comments:
{comments_str}

Please summarize this issue into the following YAML schema fields:
- id: a unique, dash-separated string id (e.g. "missing-fitres-after-merge-abort")
  symptom: a concise description of what the user sees (error log text, crash location, observable behavior)
  cause: the root cause of the error or bug
  fix: the concrete fix or workaround
  scope: universal | slurm | perlmutter
  status: unverified
  source: "GitHub Issue #{number}"

Make sure to output ONLY the valid YAML block, starting with "- id: ...". Do not wrap it in markdown code blocks or add any introductory/concluding text. Keep descriptions precise and based ONLY on the provided issue text.
"""

def main():
    parser = argparse.ArgumentParser(description="Summarize a candidate issue into entries.yaml")
    parser.add_argument("number", type=int, help="The GitHub issue number to summarize.")
    parser.add_argument("--provider", choices=["anthropic", "openai", "gemini"], default=None, help="The backend provider to use.")
    args = parser.parse_args()

    if not CANDIDATES_PATH.exists():
        print(f"Error: Candidate issues file not found at {CANDIDATES_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(CANDIDATES_PATH) as f:
        candidates = json.load(f)

    # Find the issue
    issue = None
    for c in candidates:
        if c["number"] == args.number:
            issue = c
            break

    if not issue:
        print(f"Error: Issue #{args.number} not found in candidate list.", file=sys.stderr)
        sys.exit(1)

    print(f"Found Issue #{issue['number']}: {issue['title']}")
    
    comments_str = ""
    for idx, comment in enumerate(issue["comments"], 1):
        comments_str += f"\n--- Comment {idx} by {comment['author']} ---\n{comment['body']}\n"

    prompt = SUMMARIZE_PROMPT_TEMPLATE.format(
        number=issue["number"],
        title=issue["title"],
        body=issue["body"],
        comments_str=comments_str
    )

    print("Initializing Agent to generate summary...")
    try:
        agent = Agent(provider=args.provider)
    except Exception as exc:
        print(f"Error initializing Agent: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Using backend: {agent.backend.__class__.__name__}")
    print("Calling LLM to generate entry...")
    try:
        # Call the backend directly to get the YAML block
        system_prompt = "You are a precise technical summarizer. Output only valid YAML."
        response = agent.backend.diagnose(
            system_prompt=system_prompt,
            user_message=prompt,
            tool_schemas=[],
            dispatch={}
        )
        print("\nGenerated Entry:")
        print("=" * 60)
        print(response.strip())
        print("=" * 60)

        # Validate if it parses as YAML
        try:
            parsed = yaml.safe_load(response)
            if not isinstance(parsed, list):
                if isinstance(parsed, dict):
                    parsed = [parsed]
                else:
                    raise ValueError("YAML root is not a list or dictionary.")
            
            # Verify fields
            required_fields = ["id", "symptom", "cause", "fix", "scope", "status", "source"]
            for entry in parsed:
                for field in required_fields:
                    if field not in entry:
                        print(f"Warning: Entry is missing field '{field}'")
            
            # Append to entries.yaml
            print(f"\nAppending generated entry to {ENTRIES_PATH.name}...")
            with open(ENTRIES_PATH, "r") as f_in:
                current_entries = yaml.safe_load(f_in) or []
            
            # Check for duplicates by id
            existing_ids = {e.get("id") for e in current_entries}
            new_entries_to_add = [e for e in parsed if e.get("id") not in existing_ids]
            
            if new_entries_to_add:
                current_entries.extend(new_entries_to_add)
                with open(ENTRIES_PATH, "w") as f_out:
                    yaml.safe_dump(current_entries, f_out, sort_keys=False, default_flow_style=False)
                print(f"Successfully added {len(new_entries_to_add)} new entry/entries to knowledge/entries.yaml!")
            else:
                print("No new unique entries were added (ID may already exist).")
                
        except Exception as e:
            print(f"Warning: Response is not valid YAML or is missing keys: {e}")
            
    except Exception as exc:
        print(f"Error calling LLM: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
