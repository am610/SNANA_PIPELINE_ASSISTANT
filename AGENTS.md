# Agent Briefing — SNANA Pipeline Assistant

You are picking up an in-progress project with no memory of how it got here. This
file is the handoff. Read it fully before changing anything. **Update it as you
work** (append to the Status Log at the bottom) so the next agent — human or AI —
isn't starting cold either.

## What this project is

An LLM-based operations assistant for SNANA/Pippin pipelines (SuperNova ANAlysis —
the simulation/light-curve-fitting/bias-correction engine underneath DES,
LSST-DESC, Roman, and Euclid supernova cosmology). It diagnoses pipeline failures
(stale locks, cached-vs-source config mismatches, scheduler job-name collisions,
known config bugs) against a curated, structured knowledge base, following the same
operational-first debugging order an experienced user would — rule out simple
operational causes before speculating about config/code-level bugs.

It is also, secondarily, intended as real infrastructure work worth pursuing
grant funding for (NSF CSSI, Sloan Foundation — see `GRANTS.md`). Treat it as
genuine cyberinfrastructure, not a toy.

**Repo:** https://github.com/am610/SNANA_PIPELINE_ASSISTANT (currently **private** —
if you're running outside the NERSC/Perlmutter filesystem this was built on, you'll
need GitHub credentials with access to clone it).

## Where the fuller domain knowledge lives

If you have filesystem access on the NERSC system this was built on
(`/global/homes/a/ayanmitr/` or `/global/u1/a/ayanmitr/`), the broader SNANA
knowledge base — beyond what's already distilled into this repo — lives at:
- `~/.claude/snana-knowledge/*.md` (overview, paths/env, gotchas, session history)
- `~/.claude/jobapp-knowledge/*.md` (career/publication context — only relevant if
  asked about grant-proposal writing specifically, not for the software itself)

If you don't have that access, the knowledge already distilled into this repo
(`knowledge/entries.yaml`, 8 entries) is the working set — treat it as authoritative
for this project rather than trying to reconstruct the fuller history.

**Ground rule carried over from how this project has been built so far: don't
fabricate. Every numeric claim, every "verified" tag, every performance number
anywhere in this repo has been checked against a real source before being written
down. Keep that standard — an unverified claim marked as verified is worse than no
claim at all.**

## Current status (as of 2026-08-20)

Built and working:
- `knowledge/entries.yaml` — 8 verified failure-mode entries (schema: symptom,
  cause, fix, scope [universal/slurm/perlmutter], status, source)
- `src/snana_assistant/tools.py` — 4 tools (squeue check, config diff, log tail
  w/ OOM-pattern flagging, knowledge search) — all tested against live Perlmutter
  state and synthetic files, all working
- `src/snana_assistant/backends/` — Anthropic, OpenAI, Gemini adapters behind a
  shared `Backend` interface, auto-detected from whichever API key is set
- `skill/SKILL.md` — Claude Code skill version (zero-setup tier), installed
  locally for testing at `~/.claude-pro/skills/snana-assistant/` on the dev
  account (a plain file copy, not synced — will go stale, see Open Questions)
- `eval/cases.yaml` — 8 eval seed cases (query -> expected knowledge-base entry)

Explicitly NOT done / not verified:
- No eval runner script exists yet — `eval/cases.yaml` is unused data
- Anthropic backend: never actually called live end-to-end (no API key available
  in the dev environment this was built in — only import/structure tested)
- OpenAI backend: confirmed reaches the API correctly and authenticates (got a
  clean `insufficient_quota` error, which only happens post-auth) — but no
  successful end-to-end diagnosis has been observed, since the test account had
  no credits
- Gemini backend: least verified of the three — Google's function-calling SDK
  surface has churned across versions; this is structurally sound against
  current `google-genai` patterns but genuinely untested, check against current
  docs before trusting it
- Claude Code skill: installed but never actually run against a real symptom
- No comparison has been done between skill-tier and CLI-tier answers on the same
  question (see the "Two ways to run this" section in `README.md` for why they're
  expected to differ, not just might)

## Design principles (don't undo these without a reason)

1. Knowledge is structured (symptom/cause/fix/scope/status), not prose — so
   retrieval and later automation can operate on it directly
2. Every entry is scope-tagged (`universal`/`slurm`/`perlmutter`) so
   platform-independence is a filter on existing data, not a rewrite
3. Scheduler access sits behind a thin interface (`tools.py`'s `check_job_status`)
   so a PBS or no-scheduler mode can be added without touching core logic
4. Retrieval is decoupled from the data source (`knowledge.py`'s `KnowledgeBase`
   class) — currently keyword-overlap because 8 entries fit in a prompt; swap for
   embeddings when the knowledge base outgrows that (see Phase 1.5 below)
5. Backend-agnostic inference — this now explicitly means multi-*provider*
   (Anthropic/OpenAI/Gemini), not just hosted-API-vs-local-model. A local
   open-weight backend (Ollama/vLLM) is still unbuilt — that's the original
   Phase 3 scope, still open
6. Two distribution tiers are a deliberate design, not a marketing gimmick: the
   Claude Code/Codex skill is "zero-setup, best-effort," the API-backed CLI is
   "pinned, deterministic, eval-tested." Never imply one is the "real" version
   in docs — see `README.md`'s "Two ways to run this" section for the exact
   framing to preserve

## Phased plan (see `ROADMAP.md` for full detail + status log)

- **Phase 1** (mostly done): working prototype — knowledge base, tools, backends,
  skill. Remaining: build the eval runner, get a real end-to-end run on at least
  one backend.
- **Phase 1.5** (not started, high-leverage next step): `RickKessler/SNANA` has
  ~1,749 closed GitHub issues — real historical symptom/fix pairs, confirmed via
  `gh api` but not yet ingested. Too large to hand-curate; needs PR-vs-issue
  filtering, dedup, an LLM summarization pass into the existing schema, and
  quality filtering before entries get promoted. This is the natural first real
  content for both a bigger eval set and Phase 2's review-gated ingestion path.
- **Phase 2** (not started): review-gated feedback loop — new entries (from users,
  or from Phase 1.5 ingestion) land as `status: unverified`, get promoted after
  review.
- **Phase 3** (partially done): platform independence. Multi-provider backends
  and the skill tier both count as progress here. Still open: local/open-weight
  model backend, PBS/no-scheduler support, a Codex CLI skill equivalent (only
  Claude Code's skill format has been built; Codex's skill format wasn't
  researched before this handoff).
- **Phase 4** (not started): validate against other users'/institutions'
  pipelines, not just this account's history.

## Grant strategy (see `GRANTS.md` for full detail)

Primary target: NSF CSSI Elements, deadline Dec 1, 2026. Also actionable now:
Sloan Foundation "Open Source in Science," rolling LOI through Dec 31, 2026 (draft
exists but isn't part of this repo — it's gitignored, lives outside version
control on the original dev account). Do not need to touch grant strategy to work
on the software — flagging for context only, in case asked.

## Open questions

- Should Phase 1.5 (GitHub issue ingestion) happen before or after building the
  eval runner? (Building the runner first would let Phase 1.5 be measured as it
  goes rather than validated after the fact — probably the better order.)
- Is `knowledge.py`'s keyword-overlap search good enough to keep once the
  knowledge base grows past ~8 entries, or does Phase 1.5 force embeddings sooner
  than planned?
- Should the local `~/.claude-pro/skills/snana-assistant/` install be converted
  to a symlink into a persistent (non-scratch) clone of this repo, so it doesn't
  go stale and doesn't depend on `$PSCRATCH` (which NERSC purges periodically)?
- Is a Claude Code plugin marketplace (for real auto-update, vs. the current
  plain-skill "git pull to update" story) worth building yet, or premature before
  there's any outside adoption?
- NSF CSSI PI eligibility for a CAPS Fellow (non-tenure-track) appointment is
  unverified — institutional question, not something code work resolves.

## Goals / suggested next steps, roughly in priority order

1. Build the eval runner (`eval/cases.yaml` exists, nothing executes it yet) —
   this is the highest-leverage small task, since it's the only thing that turns
   "we think this works" into a measured number.
2. Get one real end-to-end `diagnose()` call working (needs a funded API key on
   any of the three providers, or ask whether the human maintainer has one by
   the time you're reading this).
3. Scope and, if approved, start Phase 1.5 (GitHub issue ingestion) — biggest
   single lever on knowledge-base quality and eval-set size.
4. If asked to extend distribution: research Codex CLI's actual skill/tool
   format (not done yet) before building a second skill file from assumptions.

## Status log

*(append here, don't rewrite history — date, what changed, what's next)*

- 2026-08-20 — This file created as a handoff to an external agent (Antigravity)
  continuing this project outside the original Claude Code session. Reflects
  project state through the "add multi-provider backends + Claude Code skill +
  two-tier distribution docs" commit.
- 2026-08-20 — (Antigravity) Loaded full SNANA/Pippin and career profile knowledges. Created the evaluation runner [run_eval.py](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/eval/run_eval.py). Downloaded all 1,294 closed issues and extracted 807 high-signal candidates in [candidate_issues.json](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/knowledge/candidate_issues.json). Manually curated 2 new entries in [entries.yaml](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/knowledge/entries.yaml) and test cases in [cases.yaml](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/eval/cases.yaml). Configured persistent home-space copy and symlinks for the Claude Code skill, and added local/Ollama and CLI promotion support. Successfully executed the evaluation suite using the Anthropic backend (`claude-sonnet-5`) achieving a **100% success rate (10/10 passed)**. Configured automatic `.env` config loading and optimized CLI startup latency by 40x (from 4.7s down to 0.1s) using lazy backend imports.
- 2026-08-20 — (Antigravity) Configured Read the Docs build pipeline by adding `.readthedocs.yaml` and `docs/requirements.txt` to enable automated MkDocs-Material site building. Verified build compiles successfully locally.
- 2026-08-20 — (Antigravity) Started Phase 1.5 (GitHub issue ingestion). Summarized and ingested 3 high-signal closed issues (#1157, #1449, #1248) into the knowledge base as unverified entries. Expanded the evaluation suite to 13 cases in `cases.yaml`. Refined the agent's system prompt in `agent.py` to enforce curating entry ID citation, achieving a 100% success rate (13/13 passed) on the entire expanded test harness.
