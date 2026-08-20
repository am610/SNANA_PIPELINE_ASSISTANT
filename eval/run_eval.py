#!/usr/bin/env python3
"""Runner script for the SNANA Pipeline Assistant evaluation cases.

Reads queries from cases.yaml, runs the diagnose agent, and verifies if the expected
knowledge-base entry ID was cited in the diagnosis.
"""

from __future__ import annotations

import argparse
import sys
import time
import yaml
from pathlib import Path
from typing import Any

from snana_assistant.agent import Agent

def run_eval(cases_path: Path, provider: str | None = None, verbose: bool = False, delay: int = 0) -> bool:
    if not cases_path.exists():
        print(f"Error: Cases file not found at {cases_path}", file=sys.stderr)
        return False

    with open(cases_path) as f:
        cases = yaml.safe_load(f)

    if not cases:
        print("Error: No cases found in YAML.", file=sys.stderr)
        return False

    print(f"Loaded {len(cases)} evaluation cases from {cases_path}")
    if provider:
        print(f"Using forced provider: {provider}")
    else:
        print("Using auto-detected provider.")

    # Initialize agent once (this will check API keys and load KB)
    try:
        agent = Agent(provider=provider)
    except Exception as exc:
        print(f"Error initializing Agent: {exc}", file=sys.stderr)
        return False

    print(f"Agent initialized with backend: {agent.backend.__class__.__name__}")
    print("-" * 60)

    results = []
    passed = 0
    total = len(cases)
    start_time = time.time()

    for idx, case in enumerate(cases, 1):
        if idx > 1 and delay > 0:
            print(f"Waiting {delay} seconds to respect API rate limits...")
            time.sleep(delay)
        query = case["query"].strip()
        expected = case["expected_entry"].strip()
        print(f"Case {idx}/{total}: expected={expected}")
        if verbose:
            print(f"Query: {query}")
        
        case_start = time.time()
        try:
            response = agent.diagnose(query)
            case_elapsed = time.time() - case_start
            
            # Simple substring check (expected ID cited in response)
            is_success = expected in response
            
            if is_success:
                passed += 1
                status_str = "PASSED"
            else:
                status_str = "FAILED"
                
            print(f"  Result: {status_str} (took {case_elapsed:.2f}s)")
            
            if verbose or not is_success:
                print(f"  --- Agent Response ---")
                print(response.strip())
                print(f"  ----------------------")
                
            results.append({
                "index": idx,
                "expected": expected,
                "success": is_success,
                "elapsed_seconds": case_elapsed,
                "response": response
            })
        except Exception as exc:
            case_elapsed = time.time() - case_start
            print(f"  Result: ERROR - {exc} (took {case_elapsed:.2f}s)")
            results.append({
                "index": idx,
                "expected": expected,
                "success": False,
                "error": str(exc),
                "elapsed_seconds": case_elapsed,
            })
            
        print("-" * 60)

    elapsed_total = time.time() - start_time
    success_rate = (passed / total) * 100 if total > 0 else 0.0
    
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total Cases:     {total}")
    print(f"Passed:          {passed}")
    print(f"Failed:          {total - passed}")
    print(f"Success Rate:    {success_rate:.1f}%")
    print(f"Total Duration:  {elapsed_total:.2f}s ({elapsed_total/total:.2f}s per case)")
    print("=" * 60)

    # Save results to markdown file
    results_md_path = cases_path.parent / "results.md"
    try:
        with open(results_md_path, "w") as f_md:
            f_md.write("# Evaluation Results\n\n")
            f_md.write(f"- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f_md.write(f"- **Provider:** {agent.backend.__class__.__name__}\n")
            f_md.write(f"- **Success Rate:** {success_rate:.1f}% ({passed}/{total})\n")
            f_md.write(f"- **Total Time:** {elapsed_total:.2f}s\n\n")
            f_md.write("## Detailed Table\n\n")
            f_md.write("| # | Expected Entry ID | Result | Time | Notes |\n")
            f_md.write("|---|---|---|---|---|\n")
            for r in results:
                status = "✅ PASS" if r["success"] else "❌ FAIL"
                notes = ""
                if "error" in r:
                    notes = f"Error: {r['error']}"
                f_md.write(f"| {r['index']} | `{r['expected']}` | {status} | {r['elapsed_seconds']:.1f}s | {notes} |\n")
        print(f"Results report written to {results_md_path.name}")
    except Exception as exc:
        print(f"Warning: Failed to write results.md: {exc}", file=sys.stderr)

    return passed == total

def main():
    parser = argparse.ArgumentParser(description="SNANA Assistant Evaluation Runner")
    parser.add_argument(
        "--cases", default=str(Path(__file__).resolve().parent / "cases.yaml"),
        help="Path to cases YAML file"
    )
    parser.add_argument(
        "--provider", choices=["anthropic", "openai", "gemini", "local", "ollama"], default=None,
        help="Forced provider to use."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print verbose output (including successful responses)."
    )
    parser.add_argument(
        "--delay", type=int, default=None,
        help="Delay in seconds between running cases (defaults to 15 seconds if using gemini, else 0)."
    )
    args = parser.parse_args()

    delay = args.delay
    if delay is None:
        delay = 15 if args.provider == "gemini" else 0

    success = run_eval(Path(args.cases), provider=args.provider, verbose=args.verbose, delay=delay)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
