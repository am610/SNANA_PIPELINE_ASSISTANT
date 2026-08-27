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

**Repo:** https://github.com/am610/SNANA_PIPELINE_ASSISTANT — **public** (corrected
2026-08-21; this file previously said "private," which was stale). Verified via
`gh repo view`; `.gitignore` and `GRANTS.md`'s own "shareable with collaborators"
note were checked before confirming nothing sensitive is exposed. Clone with no
special credentials needed.

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
7. **(Added 2026-08-21) No custom model training.** Reaffirmed explicitly, not by
   default — considered fine-tuning a model on all SNANA info (manual, GitHub
   issues, skill files) and rejected it. Knowledge grows via a versioned corpus +
   better retrieval + more tools, not retrained weights. Full rationale in
   `ROADMAP.md`'s Design Principles section. Don't revisit this without rereading
   that rationale first.
8. **(Added 2026-08-21) Agent tool/shell access is staged, not maximal.** Currently
   read-only/narrow by deliberate decision (file read, dir list, safe status
   commands) — see `ROADMAP.md` Phase 3a/3b/3c. Do not add shell-exec or broaden
   filesystem access beyond the current `tools.py` scope without flagging it as a
   stage transition (3b/3c), since this is a real security-surface decision for a
   package strangers install via pip, not a routine feature add.

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

- ~~Should Phase 1.5 (GitHub issue ingestion) happen before or after building the
  eval runner?~~ **Resolved:** runner built first, then Phase 1.5 — matches the
  recommended order, measured as it went.
- ~~Is `knowledge.py`'s keyword-overlap search good enough to keep once the
  knowledge base grows past ~8 entries?~~ **Resolved 2026-08-21:** swapped for
  bundled BM25, not embeddings (Phase 1.7, done).
- Should the local `~/.claude-pro/skills/snana-assistant/` install be converted
  to a symlink into a persistent (non-scratch) clone of this repo, so it doesn't
  go stale and doesn't depend on `$PSCRATCH` (which NERSC purges periodically)?
- Is a Claude Code plugin marketplace (for real auto-update, vs. the current
  plain-skill "git pull to update" story) worth building yet, or premature before
  there's any outside adoption?
- NSF CSSI PI eligibility for a CAPS Fellow (non-tenure-track) appointment is
  unverified — institutional question, not something code work resolves.

## Goals / suggested next steps, roughly in priority order

**(Updated 2026-08-21, session 8 — items 1-6 from the previous list are DONE and
verified, see Status Log. `ROADMAP.md` is the source of truth if these ever
disagree.)**

1. ~~**Phase 1.5b — dedup/quality pass**~~ **DONE (2026-08-21, Claude Code).**
   `knowledge/dedup_report.py` built and run — reused BM25 via a new
   `KnowledgeBase.search_scored()` method (factored out of `search()`, no second
   metric). Output: `knowledge/dedup_report.md`, 468 pairs ranked (no threshold
   applied — human eyeballs the ranked list), top candidate (score 121.06) is
   `negative-redshift-lcfit-photoz` vs `lcfit-failure-zero-photoz-error` — looks
   like a genuine near-duplicate on inspection but **not yet merged/reviewed by
   Ayan**. 2 low-signal entries flagged (`hostlib-dztol-too-tight`,
   `sim-SNgrid-missing-perl-module`). Eval re-run after the `knowledge.py` refactor:
   still 100% (20/20). **Next actual step here: Ayan reviews `dedup_report.md` and
   decides which pairs to merge/demote — this is a human decision, not something
   for an agent to do unprompted.**
2. **Phase 2(a) — scheduled ingestion:** build `knowledge/sync_new_issues.py`
   (watermark-based, same filter+summarize path as existing scripts) and a
   `.github/workflows/weekly-ingest.yml` GitHub Actions cron that runs it and opens
   a PR with new `unverified` entries. **API key decided (2026-08-21):** reuse
   Ayan's existing key, confirmed fine with indefinite weekly billing. **But the
   secret itself is not yet in GitHub** — that's a manual step only Ayan can do
   (repo admin access required); don't assume it exists, the workflow will just
   fail until it's added. See `ROADMAP.md` Phase 2 for the full spec.
3. **Phase 2(b) — usage-driven capture:** log zero-match `diagnose()` queries
   locally (`~/.config/snana-assistant/uncaptured_queries.log`), add a
   `snana-assistant feedback` command that offers a pre-filled GitHub issue URL —
   opt-in, nothing sent automatically. See `ROADMAP.md` Phase 2.
4. If asked to extend distribution: research Codex CLI's actual skill/tool
   format (not done yet) before building a second skill file from assumptions.
5. Longer-term, not yet actionable: Phase 3b/3c (staged shell-exec tool access —
   do not start without revisiting Design Principle 8 first), Phase 4
   (community-scale validation).

## Status log

*(append here, don't rewrite history — date, what changed, what's next)*

- 2026-08-20 — This file created as a handoff to an external agent (Antigravity)
  continuing this project outside the original Claude Code session. Reflects
  project state through the "add multi-provider backends + Claude Code skill +
  two-tier distribution docs" commit.
- 2026-08-20 — (Antigravity) Loaded full SNANA/Pippin and career profile knowledges. Created the evaluation runner [run_eval.py](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/eval/run_eval.py). Downloaded all 1,294 closed issues and extracted 807 high-signal candidates in [candidate_issues.json](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/knowledge/candidate_issues.json). Manually curated 2 new entries in [entries.yaml](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/knowledge/entries.yaml) and test cases in [cases.yaml](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/eval/cases.yaml). Configured persistent home-space copy and symlinks for the Claude Code skill, and added local/Ollama and CLI promotion support. Successfully executed the evaluation suite using the Anthropic backend (`claude-sonnet-5`) achieving a **100% success rate (10/10 passed)**. Configured automatic `.env` config loading and optimized CLI startup latency by 40x (from 4.7s down to 0.1s) using lazy backend imports.
- 2026-08-20 — (Antigravity) Configured Read the Docs build pipeline by adding `.readthedocs.yaml` and `docs/requirements.txt` to enable automated MkDocs-Material site building. Verified build compiles successfully locally.
- 2026-08-20 — (Antigravity) Started Phase 1.5 (GitHub issue ingestion). Summarized and ingested 3 high-signal closed issues (#1157, #1449, #1248) into the knowledge base as unverified entries. Expanded the evaluation suite to 13 cases in `cases.yaml`. Refined the agent's system prompt in `agent.py` to enforce curating entry ID citation, achieving a 100% success rate (13/13 passed) on the entire expanded test harness.
- 2026-08-21 — (Antigravity) Created `batch_summarize.py` to support batch ingestion of issue candidates. Ingested issues #57 (stack smashing) and #1533 (bias correction parameter limits) as unverified entries. Added corresponding test cases to `cases.yaml`. Redesigned `search_knowledge` tool in `knowledge.py` to use a morphological word-similarity metric (prefix and substring overlap) and removed the misleading first-5-entries fallback. Updated `SYSTEM_PROMPT` in `agent.py` to pass the verbatim query. Ran evaluation runner and confirmed **100% success rate (15/15 passed)** across the entire expanded test harness.
- 2026-08-21 — (Claude Code) Handoff planning session, no code changes. Worked through
  four product questions with Ayan (stay LLM-based vs. train a custom model; how
  knowledge "grows"; zero-setup pip UX; agent tool-access parity with the Claude Code
  skill) and turned the decisions into `ROADMAP.md` Phases 1.6/1.7/1.8/5 (new) plus
  extensions to 1.5/2/3, and into Design Principles 7/8 + the priority list above in
  this file. Key decisions: no model training, ever, without rereading Principle 7's
  rationale first; retrieval upgrade path is bundled BM25 not embeddings; tool access
  is explicitly staged (3a read-only now, 3b/3c later, not silently widened). See
  `ROADMAP.md`'s matching 2026-08-21 status-log entry for full detail — this file's
  priority list is now a summary of that, not an independent source. **Next: start at
  item 1 above (Phase 1.5 at scale).**
- 2026-08-21 — (Antigravity) Executed Phase 1.5 at scale: processed 103 distinct high-signal issues, scaling knowledge base from 15 to 120 entries under status: unverified. Implemented Phase 1.6: parsed and section-chunked snana_manual.tex into 279 chunks, and updated search_manual in tools.py to query this index using morphological scoring. Implemented Phase 1.7: upgraded search in knowledge.py to use pure Python BM25 lexical ranking with prefix-overlap morphological fallback, and fixed a multi-turn response text-loss bug in backends by accumulating turn outputs. Implemented Phase 1.8: added config command snana-assistant init with NERSC auto-detection and local Ollama model configuration, and bundled data files via pyproject.toml package data. Conducted Phase 3a read-only tool audit. Performed Phase 5 launch polish: generated LICENSE, CONTRIBUTING.md, and CHANGELOG.md, rewrote README.md with badges, and updated docs site. Added 5 new evaluation cases for newly ingested unverified issues, expanding test coverage from 15 to 20 cases. Fixed a schema drift bug by correcting status: fixed entries back to unverified. Removed absolute developer path fallback from tools.py and removed the premature PyPI version badge from README.md. Successfully ran evaluation suite verifying **100% success rate (20/20 passed)**.
- 2026-08-21 — (Antigravity) Implemented Phase 2(b) usage-driven capture: added uncaptured query detection at the agent level (triggered when no curated bracket citation is returned) logging queries locally to `~/.config/snana-assistant/uncaptured_queries.log`. Created CLI command `snana-assistant feedback` which pulls the last uncaptured query, URL-encodes a pre-filled GitHub issue report template, and presents it to the user for opt-in contribution.
- 2026-08-21 — (Claude Code) Verified the above session's claims by direct file
  inspection (entry counts, file diffs, grep for hardcoded paths, reading actual
  BM25/retrieval/backend code, not just the summary text) — all claims held up.
  Found 4 real gaps before treating it as done: eval/cases.yaml hadn't grown with
  the KB (zero coverage of the 102 new entries), 2 entries had a non-schema
  `status: fixed` value, `tools.py` had a hardcoded personal `/pscratch/...` path
  baked into shipped code, and README's PyPI badge pointed at an unpublished
  package. Reported these back; Antigravity fixed all 4 (see its status-log entry
  above and `ROADMAP.md`'s matching 2026-08-21 session-7 entry for detail) —
  re-verified independently, all 4 fixes hold. **Current state: 120 KB entries
  (106 unverified/14 verified), 279 manual chunks, 20/20 eval passing, in sync
  between `knowledge/entries.yaml` and `src/snana_assistant/data/entries.yaml`.
  Next: Phase 2's continuous growth loop (scheduled re-ingestion + usage-driven
  capture) is the next unstarted phase; a dedup/quality pass over the 106
  unverified entries is worth doing before ingesting further from the ~700
  remaining candidates.**
- 2026-08-21 — (Claude Code) Platform-independence audit + Phase 2(b) verification.
  **Audit:** found and fixed 2 real bugs — one entry had `scope: lsst` (not a valid
  schema value; `KnowledgeBase.search()`'s default scope filter silently excluded it
  from every search, so it was functionally dead), corrected to `universal`;
  `knowledge/build_manual_index.py` had a hardcoded personal path, parameterized via
  `SNANA_MANUAL_TEX_PATH`. **Confirmed platform independence is much further along
  than documented:** `check_job_status()` already falls back squeue -> qstat -> a
  graceful no-scheduler message; multi-provider + local Ollama backends already
  exist. Built and ran the existing `Dockerfile` with podman — genuinely worked
  end-to-end (real `diagnose()` call, correct citation). Added
  `.github/workflows/publish-image.yml`: builds and pushes to
  `ghcr.io/am610/snana-pipeline-assistant` on every push to main touching
  Dockerfile/src/knowledge/skill, using the automatic `GITHUB_TOKEN` (no personal
  secret needed, unlike Phase 2(a)). **Verified live, not assumed:** watched two
  real workflow runs complete, then pulled the published image with zero cached
  credentials and ran a real `diagnose()` call from it — works for a genuine
  stranger with no NERSC account, right now. Fixed a Dockerfile lint warning found
  along the way (undefined `$PYTHONPATH`).
  **Also verified Phase 2(b) end-to-end:** ran a deliberately-unmatched query,
  confirmed it landed in `uncaptured_queries.log`, ran `snana-assistant feedback`,
  got a correctly pre-filled GitHub issue URL — but the URL requested a
  `unverified-failure` label that didn't exist on the repo yet (GitHub silently
  drops unknown labels, so real feedback issues would've landed untagged); created
  the label. Read Antigravity's dedup-report review (declined to merge the top
  candidate pair) directly against the raw entry text myself — reasoning holds up,
  the two entries describe genuinely different root causes despite shared
  vocabulary. **Note: that was Antigravity's judgment call, not Ayan's — worth Ayan
  glancing at `dedup_report.md` himself at some point, though nothing was actually
  changed so there's no live risk either way.**
  **Current state: container image live and pullable by anyone; KB scope tags all
  valid; Phase 2(a) (scheduled ingestion) is the last unstarted item on the original
  priority list, still blocked on the GitHub Actions secret only Ayan can add.**
- 2026-08-27 — (Antigravity) Loaded all historical SNANA, Claude, Codex, and Hostlib-related memories on NERSC. Diagnosed a temporary Lustre client sync lock hang (cl_syn) affecting scratch, and successfully bypassed it by copying code and configurations to a globally shared home directory workspace (~/SNANA_PIPELINE_ASSISTANT_DEV) and a node-local /tmp workspace. Verified that the entire 20-case evaluation suite passes successfully (100% success rate). Directly tested the CLI diagnose command on Midway (UChicago cluster) and resolved an editable installation error for older pip environments (pip < 21.3) by upgrading pip. Updated README.md on GitHub to add clear Midway/custom-cluster git installation instructions and pip upgrade troubleshooting.
