"""CLI: snana-assistant diagnose "<description of what's going wrong>" """

from __future__ import annotations

import argparse
import sys

import os
from pathlib import Path

from .agent import Agent


def load_env() -> None:
    # Resolve .env relative to the package src dir
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(prog="snana-assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    diagnose_p = sub.add_parser("diagnose", help="Describe a failure; the assistant investigates.")
    diagnose_p.add_argument("description", help="What's failing, in your own words (paste error text if you have it).")
    diagnose_p.add_argument(
        "--provider", choices=["anthropic", "openai", "gemini", "local", "ollama"], default=None,
        help="Force a specific backend instead of auto-detecting from which API key is set.",
    )

    promote_p = sub.add_parser("promote", help="Promote a knowledge base entry from unverified to verified.")
    promote_p.add_argument("entry_id", help="The ID of the entry to promote (e.g. 'hostlib-nbrlist-crazy-sep').")

    args = parser.parse_args()

    if args.command == "diagnose":
        try:
            agent = Agent(provider=args.provider)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        print(agent.diagnose(args.description))
    elif args.command == "promote":
        from .knowledge import KnowledgeBase
        kb = KnowledgeBase.load()
        success = kb.promote(args.entry_id)
        if success:
            print(f"Successfully promoted entry '{args.entry_id}' to verified.")
            sys.exit(0)
        else:
            sys.exit(1)



if __name__ == "__main__":
    main()
