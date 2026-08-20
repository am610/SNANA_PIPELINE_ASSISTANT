# SNANA Pipeline Assistant

An LLM-based operations assistant for SNANA/Pippin pipelines. Ingests logs, configs,
and Slurm state; diagnoses failures against a curated, structured knowledge base of
known failure modes; follows the same operational-first debugging discipline an
experienced SNANA user would (job conflicts and cached configs before code-level
speculation).

Status: early prototype (Phase 1 of `ROADMAP.md`). Not yet published — see
`ROADMAP.md`/`GRANTS.md` for the fuller plan and funding strategy.

## Two ways to run this

Not "free vs. proper" — two different guarantees, same underlying knowledge base
(`knowledge/entries.yaml`, single source of truth for both):

- **Quick start — Claude Code skill** (`skill/SKILL.md`): zero setup, uses whatever
  Claude Code session/plan you already have. Best-effort — model and exact tool
  behavior depend on your session, not pinned, not covered by the eval harness.
  Install: `git clone` this repo, then symlink or copy `skill/` into your own
  `~/.claude/skills/snana-assistant/` (path may vary by Claude Code version/config).
  **No auto-update** — this is a plain cloned skill, not a Claude Code plugin, so
  updates mean `git pull` in your clone. A real plugin-marketplace distribution
  (which does support auto-update, via `/plugin install`) is a possible later
  upgrade, not built yet — see `ROADMAP.md`.
- **Reproducible/scripted — standalone CLI** (below): pinned model, deterministic
  tools, covered by `eval/cases.yaml`, works non-interactively. Needs your own API
  key for one of Anthropic/OpenAI/Gemini.

## Install (standalone CLI)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

If you've sourced a shared SNANA/DESC environment setup script (e.g. `SNANA.sh`)
first, check `$PYTHONPATH` before creating the venv — a stale, permission-denied
path in it can break `pip` even inside a fresh venv (hit this during initial setup;
see the git history / DEV_NOTES for the exact symptom). Working fix used here:
`env -u PYTHONPATH python3 -m venv .venv`.

## Use

Bring your own Anthropic API key — no subscription, no hosted backend:

```bash
export ANTHROPIC_API_KEY=sk-...
snana-assistant diagnose "BBC aborts citing sigint, tried sigint_fix, still fails"
```

## Layout

- `knowledge/entries.yaml` — structured knowledge base (symptom/cause/fix/scope/status)
- `src/snana_assistant/knowledge.py` — loader + keyword-overlap search (v1; swap for
  embeddings once the KB outgrows a single prompt — see Phase 1.5 in `ROADMAP.md`)
- `src/snana_assistant/tools.py` — agent tools, one per pipeline-debug checklist step
- `src/snana_assistant/agent.py` — the Claude tool-use loop
- `eval/cases.yaml` — eval harness seed cases (no runner script yet)

## Design principles

See `ROADMAP.md` for the full phased plan. Short version: knowledge is structured
and scope-tagged (universal/slurm/perlmutter) from day one, scheduler access sits
behind a thin interface, retrieval is decoupled from the data source, and inference
supports both a hosted API (BYOK) and, eventually, a local open-weight backend — so
later phases (a growing/reviewed knowledge base, platform independence) don't
require rewriting earlier work.
