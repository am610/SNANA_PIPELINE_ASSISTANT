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
    # Load global config settings as well
    from .config import load_all_config_to_env
    load_all_config_to_env()


CHAT_BANNER = """SNANA assistant -- interactive session ({backend}).
Follow-ups remember this conversation, including files already read.
  /reset  start a fresh conversation (also frees up accumulated context)
  /exit   quit  (Ctrl-D works too)
"""


def _make_printer():
    """stdout writer for streamed fragments. Flushes per chunk -- buffered output would
    defeat the entire point by holding text until the turn completed anyway."""
    def _print(chunk: str) -> None:
        sys.stdout.write(chunk)
        sys.stdout.flush()
    return _print


def _run_chat(agent, max_turns: int, max_tokens: int, stream: bool = True) -> None:
    session = agent.session()
    print(CHAT_BANNER.format(backend=agent.backend.__class__.__name__))
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line in ("/exit", "/quit"):
            return
        if line == "/reset":
            session.reset()
            print("[conversation cleared]\n")
            continue
        try:
            if stream:
                print()
            answer = session.ask(
                line, max_turns=max_turns, max_tokens=max_tokens,
                on_text=_make_printer() if stream else None,
            )
        except KeyboardInterrupt:
            # Abandon this question, keep the session -- a long tool chain shouldn't
            # cost the user everything established so far.
            print("\n[interrupted]\n")
            continue
        except Exception as exc:
            print(f"\n[error: {exc}]\n", file=sys.stderr)
            continue
        print("\n" if stream else f"\n{answer}\n")


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
    diagnose_p.add_argument(
        "--max-turns", type=int, default=15,
        help="Tool-use turns the agent may take before giving up (default: 15). Raise for "
             "queries that read long include chains.",
    )
    diagnose_p.add_argument(
        "--max-tokens", type=int, default=4096,
        help="Token cap per model response (default: 4096).",
    )
    diagnose_p.add_argument(
        "--no-stream", action="store_true",
        help="Wait for the full answer instead of streaming it as it is written.",
    )

    chat_p = sub.add_parser(
        "chat",
        help="Multi-turn session: ask follow-ups that remember the earlier answers and "
             "files already read.",
    )
    chat_p.add_argument(
        "--provider", choices=["anthropic", "openai", "gemini", "local", "ollama"], default=None,
        help="Force a specific backend instead of auto-detecting from which API key is set.",
    )
    chat_p.add_argument("--max-turns", type=int, default=15, help="Tool-use turns per question (default: 15).")
    chat_p.add_argument("--max-tokens", type=int, default=4096, help="Token cap per model response (default: 4096).")
    chat_p.add_argument("--no-stream", action="store_true", help="Wait for the full answer instead of streaming it as it is written.")

    promote_p = sub.add_parser("promote", help="Promote a knowledge base entry from unverified to verified.")
    promote_p.add_argument("entry_id", help="The ID of the entry to promote (e.g. 'hostlib-nbrlist-crazy-sep').")

    init_p = sub.add_parser("init", help="Initialize and configure paths for SNANA/Pippin and local backends.")

    feedback_p = sub.add_parser("feedback", help="Provide feedback or report an uncaptured failure mode.")

    index_p = sub.add_parser(
        "index-project",
        help="Index a Pippin project's config files locally as job-setup templates. "
             "Stays on your machine only -- never uploaded, never part of the public repo.",
    )
    index_p.add_argument("path", help="Path to the Pippin project directory to index.")
    index_p.add_argument("--name", required=True, help="A short name to refer to this project by later.")

    setup_p = sub.add_parser(
        "setup",
        help="Draft a new Pippin job from your own indexed project templates. "
             "Writes to a new, empty output directory only -- never overwrites anything, never submits a job.",
    )
    setup_p.add_argument("description", help="Describe the job to set up, in your own words.")
    setup_p.add_argument("--output-dir", required=True, help="A new (or empty) directory to write the drafted files into.")
    setup_p.add_argument(
        "--provider", choices=["anthropic", "openai", "gemini", "local", "ollama"], default=None,
    )

    args = parser.parse_args()

    if args.command == "diagnose":
        try:
            agent = Agent(provider=args.provider)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        # Stream to stdout when attached to a terminal; when piped or redirected,
        # fall back to printing once at the end so downstream consumers get clean output.
        streaming = sys.stdout.isatty() and not args.no_stream
        printer = _make_printer() if streaming else None
        answer = agent.diagnose(
            args.description, max_turns=args.max_turns, max_tokens=args.max_tokens,
            on_text=printer,
        )
        if streaming:
            print()
        else:
            print(answer)
    elif args.command == "chat":
        try:
            agent = Agent(provider=args.provider)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        _run_chat(agent, args.max_turns, args.max_tokens, stream=not args.no_stream)
    elif args.command == "promote":
        from .knowledge import KnowledgeBase
        kb = KnowledgeBase.load()
        success = kb.promote(args.entry_id)
        if success:
            print(f"Successfully promoted entry '{args.entry_id}' to verified.")
            sys.exit(0)
        else:
            sys.exit(1)
    elif args.command == "init":
        from .config import load_config, save_config
        import urllib.request
        import json
        
        print("=== SNANA Pipeline Assistant Configuration Wizard ===")
        config = load_config()
        
        # Probe environment and defaults
        env_sndata = os.environ.get("SNDATA_ROOT")
        default_sndata = "/pscratch/sd/d/desctd/cfs_mirror/SNANA/SNDATA_ROOT"
        sndata_root = env_sndata or config.get("SNDATA_ROOT")
        if not sndata_root and Path(default_sndata).exists():
            sndata_root = default_sndata
            
        env_snanadir = os.environ.get("SNANA_DIR")
        default_snanadir = "/global/cfs/cdirs/lsst/groups/TD/SOFTWARE/SNANA"
        snana_dir = env_snanadir or config.get("SNANA_DIR")
        if not snana_dir:
            if Path(default_snanadir).exists():
                snana_dir = default_snanadir
            elif Path("/global/homes/a/ayanmitr/SNANA").exists():
                snana_dir = "/global/homes/a/ayanmitr/SNANA"
                
        env_setup = os.environ.get("SNANA_SETUP_COMMAND") or config.get("SNANA_SETUP_COMMAND")
        default_setup = "source /global/cfs/cdirs/lsst/groups/TD/setup_td.sh"
        if not env_setup and Path("/global/cfs/cdirs/lsst/groups/TD/setup_td.sh").exists():
            env_setup = default_setup

        # Probe local Ollama
        ollama_info = None
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=1.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    models = [m["name"] for m in data.get("models", [])]
                    ollama_info = {"host": "http://localhost:11434", "models": models}
        except Exception:
            pass

        # Interactive or silent configuration
        is_interactive = sys.stdin.isatty()
        
        if is_interactive:
            # Probe SNDATA_ROOT
            if sndata_root:
                res = input(f"Detected SNDATA_ROOT: {sndata_root}. Use this? [Y/n]: ").strip().lower()
                if res in ("n", "no"):
                    sndata_root = input("Enter path to SNDATA_ROOT: ").strip()
            else:
                sndata_root = input("Enter path to SNDATA_ROOT: ").strip()
                
            # Probe SNANA_DIR
            if snana_dir:
                res = input(f"Detected SNANA_DIR: {snana_dir}. Use this? [Y/n]: ").strip().lower()
                if res in ("n", "no"):
                    snana_dir = input("Enter path to SNANA_DIR: ").strip()
            else:
                snana_dir = input("Enter path to SNANA_DIR: ").strip()
                
            # Probe SNANA_SETUP_COMMAND
            if env_setup:
                res = input(f"Detected SNANA_SETUP_COMMAND: '{env_setup}'. Use this? [Y/n]: ").strip().lower()
                if res in ("n", "no"):
                    env_setup = input("Enter SNANA setup command: ").strip()
            else:
                env_setup = input("Enter SNANA setup command (optional): ").strip()
                
            # If Ollama found, ask if they want to configure it
            if ollama_info:
                print(f"\nDetected local Ollama instance running with models: {', '.join(ollama_info['models'])}")
                res = input("Would you like to configure local Ollama as the default backend? [y/N]: ").strip().lower()
                if res in ("y", "yes"):
                    config["LOCAL_API_BASE"] = "http://localhost:11434/v1"
                    if ollama_info["models"]:
                        print("Available models:")
                        for idx, m in enumerate(ollama_info["models"], 1):
                            print(f"  {idx}. {m}")
                        try:
                            m_idx = int(input("Select model number: ").strip()) - 1
                            if 0 <= m_idx < len(ollama_info["models"]):
                                config["LOCAL_MODEL"] = ollama_info["models"][m_idx]
                        except (ValueError, IndexError):
                            pass
        else:
            print("Running in non-interactive mode. Probing and configuring silently...")

        # Save config
        if sndata_root:
            config["SNDATA_ROOT"] = sndata_root
        if snana_dir:
            config["SNANA_DIR"] = snana_dir
        if env_setup:
            config["SNANA_SETUP_COMMAND"] = env_setup
            
        save_config(config)
        print("\nConfiguration saved successfully to ~/.config/snana-assistant/config.yaml")
        print("Configured paths:")
        print(f"  SNDATA_ROOT:         {config.get('SNDATA_ROOT')}")
        print(f"  SNANA_DIR:           {config.get('SNANA_DIR')}")
        if config.get("SNANA_SETUP_COMMAND"):
            print(f"  SNANA_SETUP_COMMAND: {config.get('SNANA_SETUP_COMMAND')}")
        if config.get("LOCAL_API_BASE"):
            print(f"  LOCAL_API_BASE:      {config.get('LOCAL_API_BASE')}")
            print(f"  LOCAL_MODEL:         {config.get('LOCAL_MODEL')}")
    elif args.command == "feedback":
        from .config import get_last_uncaptured_query
        import urllib.parse
        
        print("=== SNANA Pipeline Assistant Feedback & Contribution ===")
        query = get_last_uncaptured_query()
        
        title = "Uncaptured Failure Mode"
        if query:
            print(f"Found last uncaptured query: '{query}'")
            body = (
                "I encountered a failure mode that was not recognized by the SNANA Pipeline Assistant.\n\n"
                "### User Query / Symptom:\n"
                f"```\n{query}\n```\n\n"
                "### Suggested Cause:\n"
                "[Explain what caused the failure]\n\n"
                "### Suggested Fix:\n"
                "[Explain how to fix it]\n"
            )
        else:
            print("No local uncaptured queries found.")
            body = (
                "### User Query / Symptom:\n"
                "[Paste query/symptom/error log here]\n\n"
                "### Suggested Cause:\n"
                "[Explain what caused the failure]\n\n"
                "### Suggested Fix:\n"
                "[Explain how to fix it]\n"
            )
            
        params = {
            "title": title,
            "body": body,
            "labels": "unverified-failure"
        }
        url = "https://github.com/am610/SNANA_PIPELINE_ASSISTANT/issues/new?" + urllib.parse.urlencode(params)
        
        print("\nYou can submit this failure mode to the knowledge base by opening the pre-filled URL below in your browser:")
        print(f"\n  {url}\n")
        print("Once verified by a maintainer, this issue will be merged into the official knowledge base.")
    elif args.command == "index-project":
        from . import templates
        try:
            summary = templates.index_project(Path(args.path), args.name)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        print(f"Indexed project '{summary['project']}':")
        print(f"  {summary['templates_copied']} config file(s) copied to ~/.config/snana-assistant/templates/{summary['project']}/")
        print(f"  {summary['data_files_referenced']} data file(s) (SIMLIB/HOSTLIB) referenced by path only, not copied")
        print("\nThis data stays on your machine only -- never uploaded, never part of the public repo.")
    elif args.command == "setup":
        try:
            agent = Agent(provider=args.provider)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        print(agent.setup_job(args.description, args.output_dir))




if __name__ == "__main__":
    main()
