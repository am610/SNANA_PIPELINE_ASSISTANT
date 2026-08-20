"""CLI: snana-assistant diagnose "<description of what's going wrong>" """

from __future__ import annotations

import argparse
import sys

from .agent import Agent


def main() -> None:
    parser = argparse.ArgumentParser(prog="snana-assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    diagnose_p = sub.add_parser("diagnose", help="Describe a failure; the assistant investigates.")
    diagnose_p.add_argument("description", help="What's failing, in your own words (paste error text if you have it).")
    diagnose_p.add_argument(
        "--provider", choices=["anthropic", "openai", "gemini"], default=None,
        help="Force a specific backend instead of auto-detecting from which API key is set.",
    )

    args = parser.parse_args()

    if args.command == "diagnose":
        try:
            agent = Agent(provider=args.provider)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        print(agent.diagnose(args.description))


if __name__ == "__main__":
    main()
