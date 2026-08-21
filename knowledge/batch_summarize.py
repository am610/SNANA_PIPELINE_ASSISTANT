#!/usr/bin/env python3
"""Batch ingestion script for SNANA GitHub issues (Phase 1.5).

Takes a list of issue numbers, prepares LLM prompts with issue bodies and comments,
and calls the Agent's LLM backend to summarize each and register them as unverified entries.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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

def clean_yaml_response(response: str) -> str:
    response = response.strip()
    if response.startswith("```"):
        lines = response.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        response = "\n".join(lines).strip()
    return response

def main():
    parser = argparse.ArgumentParser(description="Batch summarize candidate issues into entries.yaml")
    parser.add_argument("numbers", type=int, nargs="+", help="The GitHub issue numbers to summarize.")
    parser.add_argument("--provider", choices=["anthropic", "openai", "gemini"], default=None, help="The backend provider to use.")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay in seconds between API calls.")
    args = parser.parse_args()

    if not CANDIDATES_PATH.exists():
        print(f"Error: Candidate issues file not found at {CANDIDATES_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(CANDIDATES_PATH) as f:
        candidates = json.load(f)

    # Initialize Agent
    print("Initializing Agent...")
    try:
        agent = Agent(provider=args.provider)
    except Exception as exc:
        print(f"Error initializing Agent: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Using backend: {agent.backend.__class__.__name__}")
    print(f"Starting batch process for {len(args.numbers)} issues...")
    print("-" * 60)

    successful = 0
    failed = 0

    for idx, num in enumerate(args.numbers):
        if idx > 0 and args.delay > 0:
            print(f"Sleeping for {args.delay} seconds...")
            time.sleep(args.delay)

        print(f"Processing Issue #{num} ({idx+1}/{len(args.numbers)})...")
        # Find the issue
        issue = None
        for c in candidates:
            if c["number"] == num:
                issue = c
                break

        if not issue:
            print(f"Error: Issue #{num} not found in candidates list. Skipping.", file=sys.stderr)
            failed += 1
            continue

        # Check if already ingested by checking source in entries.yaml
        with open(ENTRIES_PATH, "r") as f_in:
            current_entries = yaml.safe_load(f_in) or []
        is_already_ingested = False
        for e in current_entries:
            src = e.get("source", "")
            if f"Issue #{num}" in src or f"issue #{num}" in src.lower():
                is_already_ingested = True
                break
        if is_already_ingested:
            print(f"Issue #{num} is already ingested in entries.yaml. Skipping.")
            successful += 1
            continue

        print(f"Found Issue #{issue['number']}: {issue['title']}")
        
        comments_str = ""
        for c_idx, comment in enumerate(issue["comments"], 1):
            comments_str += f"\n--- Comment {c_idx} by {comment['author']} ---\n{comment['body']}\n"

        prompt = SUMMARIZE_PROMPT_TEMPLATE.format(
            number=issue["number"],
            title=issue["title"],
            body=issue["body"],
            comments_str=comments_str
        )

        print("Calling LLM...")
        try:
            system_prompt = "You are a precise technical summarizer. Output only valid YAML."
            response = agent.backend.diagnose(
                system_prompt=system_prompt,
                user_message=prompt,
                tool_schemas=[],
                dispatch={}
            )

            cleaned_response = clean_yaml_response(response)
            
            # Validate if it parses as YAML
            try:
                parsed = yaml.safe_load(cleaned_response)
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
                with open(ENTRIES_PATH, "r") as f_in:
                    current_entries = yaml.safe_load(f_in) or []
                
                existing_ids = {e.get("id") for e in current_entries}
                new_entries_to_add = [e for e in parsed if e.get("id") not in existing_ids]
                
                if new_entries_to_add:
                    current_entries.extend(new_entries_to_add)
                    with open(ENTRIES_PATH, "w") as f_out:
                        yaml.safe_dump(current_entries, f_out, sort_keys=False, default_flow_style=False)
                    print(f"Successfully added {len(new_entries_to_add)} entry/entries from Issue #{num}!")
                    successful += 1
                else:
                    print(f"No new unique entries added from Issue #{num} (ID may already exist).")
                    successful += 1
                    
            except Exception as e:
                print(f"Error parsing YAML response for Issue #{num}: {e}", file=sys.stderr)
                print(f"Raw response: {response}", file=sys.stderr)
                failed += 1
                
        except Exception as exc:
            print(f"Error calling LLM for Issue #{num}: {exc}", file=sys.stderr)
            failed += 1
            
        print("-" * 60)

    print("\nBatch Ingestion Complete!")
    print(f"Total:      {len(args.numbers)}")
    print(f"Successful: {successful}")
    print(f"Failed:     {failed}")

if __name__ == "__main__":
    main()
