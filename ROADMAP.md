# SNANA Pipeline Assistant — Roadmap

An LLM-based operations assistant for SNANA/Pippin pipelines: ingests logs, YAML configs,
and Slurm output, and helps diagnose failures using a curated, growing knowledge base of
known failure modes. Intended eventually as community cyberinfrastructure for SN
cosmology pipelines (DES, LSST-DESC, Roman, Euclid), not a single-user tool.

Started: 2026-08-20.

## Design principles (agreed, so later phases don't require a rewrite)

1. **Structured knowledge, not prose.** Every entry has fields: symptom, cause, fix,
   scope tag, verification status, source. See `KNOWLEDGE.md` for the schema and seed
   entries.
2. **Scope-tagged from day one.** Every entry is tagged `universal` / `slurm` /
   `perlmutter` so platform-independence later is a filter on existing data, not a
   rewrite.
3. **Scheduler access behind a thin interface.** `get_job_status()` etc. have a Slurm
   implementation now; other schedulers (PBS) or a no-scheduler mode plug in later
   without touching core logic.
4. **Retrieval decoupled from the data source.** Core logic points at "a directory of
   structured entries," not hardcoded files, so swapping in a growing/curated knowledge
   base later is a config change.
5. **Backend-agnostic inference.** Support both a hosted-API backend (BYOK — user
   supplies their own Anthropic/OpenAI key, no subscription required) and a local
   open-weight model backend (e.g., via Ollama/vLLM) for clusters where sending logs
   externally isn't desired.

**Reaffirmed 2026-08-21: this project does not train or fine-tune a custom model.**
Considered explicitly and rejected. Reasons, specific to this project (not a generic
RAG-vs-fine-tuning take):
- Knowledge here is a fact list that keeps growing (new gotchas, new GH issues), not a
  behavior to bake in — a new entry is a YAML append today; baked into weights it's a
  retraining run every time.
- No fine-tuning-scale data exists or will soon: 15 curated entries, ~805 raw issue
  candidates. That's a retrieval corpus, not thousands of clean (query, correct
  diagnosis) pairs.
- The agent's actual job — follow the operational debugging order, call tools, map a
  novel symptom onto known patterns — is reasoning on top of facts, not recall. That
  rides the frontier model's improving capability for free; a fine-tuned snapshot is
  frozen at whatever it was trained from.
- Traceability: the project's ground rule (`AGENTS.md`) is "don't fabricate, every
  claim checked against a real source." RAG lets the agent cite `[entry-id]` back to a
  verified source. Opaque fine-tuned weights can't do that — worse for exactly the
  standard already set here, and worse for grant reviewers who'll ask how you know an
  answer is right.
- "Growth over time" therefore means: knowledge corpus growth, retrieval-quality
  growth, and tool-capability growth — three axes, all versioned in git/releases, none
  of them a training run. See Phases 1.6-1.8, 2, 3 below.

## Phased plan

### Phase 1 — Working v1 (target: ~2026-09-20, one month)
- Curated, structured knowledge base seeded from existing gotchas (see `KNOWLEDGE.md`)
- Retrieval + agent tool-use loop over that knowledge base
- Eval set: ~15-20 real past failure cases (from session history), measured
  diagnosis accuracy
- Single cluster (Perlmutter/Slurm) scope is fine for v1 — the abstraction seams from
  above make this a deliberate, bounded first slice, not a shortcut that has to be
  undone later
- Deliverable: public (or initially private) GitHub repo, README, demo

### Phase 1.5 — SNANA GitHub issue history as knowledge-base seed corpus
- `RickKessler/SNANA` has ~1,749 closed issues (some fraction are merged PRs, not
  pure issues — needs filtering) going back years — real, public, already-written
  symptom/resolution pairs. Confirmed via `gh api` on 2026-08-20.
- Too large to hand-curate or fit in a single prompt (unlike the 8 seed entries) —
  this is the natural first real payload for both the eval set (closed issues with
  a resolved thread = ready-made test cases) and the Phase 2 review-gated ingestion
  path (ingest as `status: unverified`, LLM-summarized into the schema, human/
  maintainer-reviewed before promotion).
- Not built yet. Needs: PR-vs-issue filtering, dedup, an LLM summarization pass
  issue-thread -> {symptom, cause, fix, scope}, and noise filtering (low-signal or
  unresolved threads). Scope this as its own session, likely right after the basic
  agent loop is working end-to-end.
- **Status 2026-08-21: partially done (5/805 candidates ingested by hand).**
  `batch_summarize.py` exists (built 2026-08-21) but has only been run on 2 issues at
  a time. Next step is running it at scale over the full 805-candidate list — but
  run a dedup pass first (many of the 1,294 closed issues will cluster on the same
  root cause; expect a real yield of ~80-150 distinct entries after filtering, not
  805). Keep everything from this pass at `status: unverified` per the Phase 2 design
  — do not bulk-promote.

### Phase 1.6 — Manual ingestion (new, 2026-08-21)
- Chunk `snana_manual.tex` by section (the line-range table already in
  `~/.claude/snana-knowledge/overview.md` gives natural chunk boundaries) into
  retrieval passages.
- Ship the chunked index as package data alongside `entries.yaml`, same "built once,
  shipped to users" model as Phase 1.8 below.
- Before marking this done: confirm `search_manual` (referenced in `agent.py`'s
  `SYSTEM_PROMPT`) is doing real chunked retrieval over this index and not a raw
  grep — unverified as of this writing.

### Phase 1.7 — Retrieval upgrade (decided 2026-08-21: bundled BM25, not embeddings)
- Current `KnowledgeBase.search()` (prefix/substring overlap) is a placeholder,
  documented as such in `knowledge.py`. Replace with BM25 (pure Python, e.g.
  `rank-bm25`) once the KB is large enough that lexical ranking starts mattering —
  which Phase 1.5's scaled ingestion will make true almost immediately.
- Explicitly rejected for now: a bundled local embeddings model (adds ~100-400MB to
  install size + CPU inference cost per query, against the "lightweight pip install"
  goal) and BYOK embeddings API (would make knowledge-base *lookup* — which should
  work immediately after `pip install` with zero key — depend on network + an API
  key). Revisit only if BM25 proves insufficient at real scale.

### Phase 1.8 — Packaging & zero-setup UX (new, 2026-08-21)
- Ship the *built* knowledge base (+ manual index, once 1.6 lands) as package data —
  the ingestion pipeline (GH issue summarization, manual chunking) is a
  maintainer-side job that runs periodically and gets committed; a user's
  `pip install` never triggers it themselves.
- Add a `snana-assistant init` command: probe `$SNDATA_ROOT` / `$SNANA_DIR` / common
  Perlmutter paths first; if found, configure silently; if not, ask once and persist
  to `~/.config/snana-assistant/config.yaml` so it never asks again.
- `init` should also detect a local Ollama endpoint and offer it as the no-API-key
  path to full `diagnose()` mode, not just the lookup-only path.
- Goal: `search_knowledge` works fully offline, zero API key, immediately after
  `pip install`. Full `diagnose()` (agent + tools) still needs BYOK or local Ollama —
  that's an existing, correct constraint, not new scope.

### Phase 1.5b — Dedup & quality pass over ingested entries (new, 2026-08-21)
- Goal: clean up the 106 `unverified` entries from Phase 1.5 *before* Phase 2
  automation starts compounding the noise further — many of the 103 source issues
  likely cluster on the same root cause.
- New script: `knowledge/dedup_report.py` — scores every entry's
  symptom+cause text against every other entry (reuse the BM25 scoring already in
  `knowledge.py` rather than building a second similarity metric) and flags pairs
  above a similarity threshold as candidate duplicates/near-duplicates.
- Also flag low-signal entries separately: `fix` field under some minimum length,
  or a `symptom` that's just the GitHub issue title copy-pasted with no concrete
  error string — tag `needs-more-detail`, don't delete.
- **Output is a human-readable report, not an automatic edit.** Per the project's
  own "don't fabricate / review before promotion" ground rule, merges and removals
  need your review — the script's job is to make that review fast, not to make the
  decision itself.

### Phase 2 — Review-gated feedback loop
- New failure cases (from you or other users) submitted as `status: unverified` entries
- Lightweight review/promotion step before an entry is trusted and surfaced to other
  users
- Turns the static v1 knowledge base into one that improves with use
- **Extended 2026-08-21 — continuous growth loop, two feeds into `unverified`:**
  (a) a scheduled job (weekly) that pulls newly-closed GitHub issues and
  auto-summarizes them — a natural fit for a scheduled cloud agent rather than
  something run by hand each time; (b) usage-driven — when a live `diagnose()` call
  finds no KB match, log the query itself as a growth candidate. A periodic
  maintainer batch still promotes `unverified -> verified`; neither feed auto-promotes.
- **Spec'd concretely 2026-08-21:**
  - **(a) Scheduled ingestion:** new script `knowledge/sync_new_issues.py` — queries
    the GitHub API for issues on `RickKessler/SNANA` closed since a stored watermark
    (`knowledge/.ingest_state.json`: last-processed issue number/date), applies the
    same high-signal filter used to build `candidate_issues.json`, runs the existing
    `batch_summarize.py` LLM-summarization path, appends new `status: unverified`
    entries, advances the watermark.
    Run this as a **GitHub Actions scheduled workflow**
    (`.github/workflows/weekly-ingest.yml`, weekly cron), not a Perlmutter cron job —
    it only needs the GitHub API + an LLM API key, not NERSC compute, so it isn't
    coupled to an active allocation/session. **Decided 2026-08-21:** reuse Ayan's
    existing Anthropic key (already used locally for CLI/eval runs) for this too —
    confirmed he's fine with it billing his account for weekly runs indefinitely.
    **Action required from Ayan, not Antigravity:** the secret has to be added to
    the GitHub repo (`gh secret set ANTHROPIC_API_KEY`, run locally so the key
    value never appears in any chat/agent transcript, or via repo Settings →
    Secrets) — Antigravity can write the workflow YAML but cannot add repo secrets
    itself (needs repo admin access). Don't assume the secret exists yet; the
    workflow will fail until it's actually added. The
    workflow should open a PR with the new entries rather than commit to `main`
    directly, so there's still a review gate — consistent with this phase's name.
  - **(b) Usage-driven capture:** when a live `diagnose()` call's `search_knowledge`
    (or `search_manual`) returns zero results, append the raw query to a local file
    (`~/.config/snana-assistant/uncaptured_queries.log`) — **never sent anywhere
    automatically**, matching the existing local/Ollama-backend principle that
    nothing leaves the user's machine without explicit action. Add a
    `snana-assistant feedback` command that shows the user their locally logged
    uncaptured queries and offers to open a pre-filled GitHub issue URL (a link the
    user clicks, not an API call Claude/the CLI makes on their behalf) so submitting
    is opt-in, not silent telemetry.

### Phase 3 — Platform independence + agent capability expansion
- Scheduler abstraction beyond Slurm
- Environment-specific vs. universal entries already separated (Phase 1 design), so
  this phase is mostly packaging: pip-installable add-on that a user installs
  alongside their own SNANA environment and points at their own output directory
- Local/open-weight backend option matters most here (DOE/HPC users wary of sending
  logs to an external API)
- **Added 2026-08-21 — agent tool-access, staged deliberately, do not silently widen
  past the current stage without revisiting this decision:**
  - **3a (now):** keep the tool set read-only/narrow — file read, directory list,
    safe status commands (current `tools.py` scope: squeue check, config diff, log
    tail, KB search). This is the safe default for a package strangers install via
    pip, and the only stage currently in scope.
  - **3b (later):** shell exec with per-command confirmation, mirroring how Claude
    Code itself gates risky actions. This is what closes the gap toward "look at my
    failing pipeline and run something for me" parity with the Claude Code skill
    experience.
  - **3c (further out, if ever):** shell exec behind an explicit opt-in flag (e.g.
    `--trusted`), off by default. Most powerful, biggest support/security burden —
    only worth it once there's real outside adoption to justify it.

### Phase 4 — Community-scale validation
- Test against failure cases from other users'/institutions' pipelines, not just this
  account's history
- This is also where a funded proposal (see `GRANTS.md`) would carry the work past
  what's feasible as an unfunded side project

### Phase 5 — Launch polish (new, 2026-08-21)
- README rewrite: value prop above the fold, quickstart in <5 lines, demo GIF/
  screenshot, badges (PyPI version, eval pass-rate, license)
- Flesh out the already-scaffolded mkdocs site with real content (currently just the
  build pipeline is configured, per `AGENTS.md` status log)
- `CONTRIBUTING.md`, a real `LICENSE`, semantic versioning + `CHANGELOG.md` so
  knowledge-base/tool growth is visible release-over-release
- GitHub social-preview image
- Keep the existing "real infrastructure, not a toy" framing — the private
  AI-industry-pivot motivation stays exactly as separated from collaborator-facing
  material as it already is (see the private-context handling note in project memory)

## Distribution: two tiers, not "free vs. proper"

Two ways to run this, with different guarantees — not a gimped-free-tier-to-upsell
structure (that would undermine the honesty this project is otherwise built on, and
would look bad in a grant proposal). Both read the same `knowledge/entries.yaml` as
the single source of truth.

- **Default (Claude Code / Codex CLI skill):** zero setup, uses whatever
  subscription/session you already have. Best-effort — model version and exact
  tool behavior depend on your session, not pinned, not covered by the eval
  harness. This is the "quick start."
- **Opt-in (API key, `agent.py` + backends):** pinned model, deterministic Python
  tools, the only path covered by `eval/cases.yaml`, the only path that works
  non-interactively (cron/CI/scripted). For people who need reproducibility or
  volume, not people who "paid for the better answer."

The README should state this plainly rather than imply one path is more real than
the other.

**Update distribution (verified via research, 2026-08-20):** a plain cloned skill
has no auto-update — `git pull` is the honest instruction. Real auto-update exists
only via a proper Claude Code plugin (a `plugin.json` manifest hosted in a
marketplace repo, installed with `/plugin install <name>@<marketplace>`, updates
checked after session startup). Not built yet — `skill/SKILL.md` is a plain skill
for now. Worth revisiting as a plugin if this gets real outside adoption.

## Status log
*(update at the end of each work session — date, what changed, next step)*

- 2026-08-20 — Workspace created. Design principles agreed. Knowledge base seeded from
  existing SNANA/Pippin gotchas (8 entries). No code written yet. Next: scope the
  retrieval + agent loop for Phase 1.
- 2026-08-20 (same day, session 2) — Completed the grants research pass. Best new find:
  Sloan Foundation "Open Source in Science" — rolling 2-page LOI through 2026-12-31,
  much lower friction than NSF CSSI; worth doing in parallel/first. Schmidt Sciences
  AI2050 also promising on eligibility (no faculty restriction) but deadline
  unconfirmed. AAG deadline confirmed (Oct 1, 2026 window opens). Simons SSRF cycle
  already closed for this year. See `GRANTS.md` for full detail. Next: decide whether
  to draft the Sloan LOI before or alongside starting Phase 1 code.
- 2026-08-20 (session 3) — Sloan LOI drafted (`grant_applications/`, gitignored —
  not in the repo history). Phase 1 code scaffold built and committed: knowledge
  loader, 4 tools (squeue, config diff, log tail, KB search) mapped onto the
  pipeline-debug checklist, BYOK Claude tool-use agent loop, CLI, 8-case eval seed
  set. Tools tested against live squeue and synthetic files — all working. Agent
  loop itself untested (no ANTHROPIC_API_KEY in this environment yet). Git repo
  initialized locally, not yet pushed to GitHub. Also logged Phase 1.5 (SNANA
  GitHub issue history as a knowledge-base seed corpus, ~1,749 closed issues,
  confirmed via `gh api`) as a concrete next-after-Phase-1 item.
  **Next: set ANTHROPIC_API_KEY and do a real end-to-end diagnose() run, then
  decide whether to push the repo to GitHub (private first) or start Phase 1.5.**
- 2026-08-20 (session 3, continued) — Pushed to
  **https://github.com/am610/SNANA_PIPELINE_ASSISTANT (private)**. Verified clean
  tree (no .venv, no grant_applications/, no build artifacts). Next: real
  end-to-end diagnose() run with an API key, then Phase 1.5.
- 2026-08-20 (session 4) — (Antigravity) Built [run_eval.py](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/eval/run_eval.py), added delay/retry handling for API rate limits, downloaded 1,294 raw closed issues, and extracted 807 candidates. Manually curated 2 new entries in [entries.yaml](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/knowledge/entries.yaml) and test cases in [cases.yaml](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/eval/cases.yaml). Linked Claude Code skill to persistent home space, and added local/Ollama and CLI promotion support. Successfully executed the 10-case evaluation suite using the Anthropic backend (`claude-sonnet-5`) achieving a **100% success rate (10/10 passed)**. Configured automatic `.env` config loading and optimized CLI startup latency by 40x (from 4.7s down to 0.1s) using lazy backend imports.
- 2026-08-21 (session 5) — (Antigravity) Created `batch_summarize.py` for batch candidate ingestion. Ingested issues #57 and #1533 as unverified entries. Expanded eval/cases.yaml to 15 cases. Redesigned `search_knowledge` tool in `knowledge.py` to use a morphological word-similarity metric (prefix and substring overlap) and removed the first-5 fallback. Updated `SYSTEM_PROMPT` in `agent.py` to pass the verbatim query. Ran evaluation runner and confirmed **100% success rate (15/15 passed)**.
- 2026-08-21 (session 6, Claude Code) — Reviewed full project state and worked through
  four open product questions with Ayan: (1) confirmed the product stays fully
  LLM-based (BYOK/local backends, not a fine-tuned custom model) — decision reaffirmed
  with explicit rationale, see Design Principles above; (2) defined "growth over time"
  as knowledge-corpus + retrieval-quality + tool-capability growth, not model
  retraining; (3) scoped a zero-setup pip UX — ship the *built* KB as package data,
  add an `init` wizard, make KB lookup work fully offline with no API key; (4) scoped
  "agent-helper" tool access (parity with the Claude Code skill experience) as a
  staged rollout rather than a single jump. Decisions made: retrieval upgrade path is
  bundled BM25, not embeddings (preserves the zero-network/zero-key lookup story);
  tool access stays read-only/narrow for now (Phase 3a), with confirmed shell-exec
  (3b) and opt-in trusted mode (3c) explicitly deferred, not silently in scope. Wrote
  all of this into Phases 1.6 (manual ingestion, new), 1.7 (retrieval upgrade, new),
  1.8 (packaging/zero-setup UX, new), extended 1.5/2/3, and added Phase 5 (launch
  polish / GitHub page, new).
  **Next (priority order): run batch ingestion at scale with a dedup pass (1.5) →
  manual chunking (1.6) → BM25 swap (1.7) → packaging/init wizard (1.8) → Phase 3a
  tool-set audit (confirm current tools.py scope matches what's documented) → Phase 5
  polish. Each is close to a prerequisite for the next, in roughly this order.**
- 2026-08-21 (session 7) — (Antigravity) Executed Phases 1.5 (at scale), 1.6, 1.7,
  1.8, 3a-audit, and 5 in one pass: ingested 103 GitHub issues -> 102 new unverified
  entries (KB 15 -> 120); chunked `snana_manual.tex` into 279 sections
  (`manual_chunks.json`), wired real chunked retrieval into `search_manual`; replaced
  keyword-overlap with real BM25 in `knowledge.py`; fixed a multi-turn text-loss bug
  in all three backends (intermediate tool-citation text was being dropped, only the
  final turn's text was returned); added `snana-assistant init` config wizard
  (`config.py`) + declared package-data in `pyproject.toml` so the built KB ships
  with the wheel; audited `tools.py` — confirmed still read-only, no shell-exec
  surface; wrote `LICENSE`/`CONTRIBUTING.md`/`CHANGELOG.md` + rewrote `README.md`.
  **Verified by Claude Code (2026-08-21, same day) via direct file inspection —
  every claim above checked out.** Found and Antigravity then fixed 4 real gaps:
  (1) eval/cases.yaml hadn't grown with the KB (still 15 cases covering only the
  original curated set, zero coverage of the 102 new entries) — fixed by sampling
  5 new entries into cases 16-20, re-ran eval: 100% (20/20); (2) 2 entries had a
  non-schema `status: fixed` value — corrected to `unverified`, both files
  re-verified in sync; (3) `tools.py`'s `search_manual` had a hardcoded personal
  `/pscratch/sd/a/ayanmitr/...` fallback path baked into shipped code — removed;
  (4) README's PyPI badge pointed at an unpublished package — removed until a real
  release exists. All 4 fixes independently re-verified against the actual files
  (not just re-reading Antigravity's summary) — hold up. **Current state: 120 KB
  entries (106 unverified/14 verified), 279 manual chunks, 20/20 eval passing.
  Next: Phase 2 continuous growth loop (scheduled re-ingestion + usage-driven
  capture) is the next unstarted phase; also worth a dedup/quality pass over the
  106 unverified entries before ingesting further from the ~700 remaining
  candidates, per Phase 1.5's own caution against bulk-ingesting noise.**
- 2026-08-21 (session 7) — (Antigravity) Executed Phase 1.5 at scale: processed 103 distinct high-signal issues, scaling active knowledge base from 15 to 120 unverified entries. Implemented Phase 1.6: parsed and section-chunked LaTeX manual into 279 chunks, and updated search_manual in tools.py to query this index using morphological similarity matching. Implemented Phase 1.7: upgraded search in knowledge.py to use pure Python BM25 lexical search ranking method with morphological prefix-overlap matching as fallback, and fixed a multi-turn response text-loss bug in backends by accumulating turn outputs. Implemented Phase 1.8: added config wizard cli command snana-assistant init with NERSC auto-detection and local Ollama model configuration, and bundled data files via pyproject.toml package data. Conducted Phase 3a read-only tool audit. Performed Phase 5 launch polish: generated LICENSE, CONTRIBUTING.md, and CHANGELOG.md, rewrote README.md with badges, and updated docs site. Added 5 new evaluation cases for newly ingested unverified issues, expanding test coverage from 15 to 20 cases. Fixed a schema drift bug by correcting status: fixed entries back to unverified. Removed absolute developer path fallback from tools.py and removed the premature PyPI version badge from README.md. Successfully ran evaluation suite verifying **100% success rate (20/20 passed)**.
- 2026-08-21 (session 7) — (Antigravity) Implemented Phase 2(b) usage-driven capture: added uncaptured query detection at the agent level (triggered when no curated bracket citation is returned) logging queries locally to `~/.config/snana-assistant/uncaptured_queries.log`. Created CLI command `snana-assistant feedback` which pulls the last uncaptured query, URL-encodes a pre-filled GitHub issue report template, and presents it to the user for opt-in contribution.
- 2026-08-21 (session 8, Claude Code) — Platform-independence audit (Phase 3) +
  Phase 2(b) verification. Found and fixed 2 bugs: invalid `scope: lsst` tag
  (silently made an entry unreachable via `KnowledgeBase.search()`'s scope filter;
  corrected to `universal`), hardcoded personal path in `build_manual_index.py`
  (parameterized via `SNANA_MANUAL_TEX_PATH`). Confirmed multi-scheduler fallback
  (squeue -> qstat -> graceful no-scheduler message) and multi-provider/local-Ollama
  backends already existed. Built and ran the existing `Dockerfile` with podman —
  real end-to-end `diagnose()` call worked. Added
  `.github/workflows/publish-image.yml` (GHCR publish on push to main, uses the
  automatic `GITHUB_TOKEN`, no personal secret needed unlike Phase 2(a)) — watched
  two real runs complete, then pulled `ghcr.io/am610/snana-pipeline-assistant` with
  zero cached credentials and ran a real `diagnose()` call from it. Fixed a
  Dockerfile lint warning (undefined `$PYTHONPATH`) found along the way. Verified
  Phase 2(b) live: unmatched query correctly logged, `snana-assistant feedback`
  produced a correct pre-filled issue URL — except it referenced a GitHub label
  (`unverified-failure`) that didn't exist yet; created it. Independently read the
  two entries in Antigravity's declined-merge dedup-report call
  (`negative-redshift-lcfit-photoz` vs `lcfit-failure-zero-photoz-error`) — holds up,
  genuinely different root causes. **Next: Phase 2(a) (scheduled ingestion) is the
  last unstarted item on the original priority list, still blocked on Ayan adding
  the GitHub Actions secret. Ayan hasn't personally reviewed `dedup_report.md` yet
  — worth doing at some point, though nothing was changed either way so there's no
  live risk.**
- 2026-08-21 (session 9, Claude Code) — Built Phase 2(a): `knowledge/sync_new_issues.py`
  + `.github/workflows/weekly-ingest.yml`. Refactored `ingest_issues.py` and
  `batch_summarize.py` to expose `is_high_signal()`/`summarize_issue()` so the new
  script reuses the existing filter/summarization logic rather than duplicating it
  (verified both refactors behavior-preserving before building on them). State
  (`.ingest_state.json`) tracks a *set* of already-seen issue numbers, not just a
  date, since a low-numbered issue can close after a higher-numbered one — found 4
  real examples of exactly this (#1590/#1689/#1698/#1709) by diffing live GitHub
  data against the original 1,294-issue snapshot. Ran the script for real (local
  key): correctly skipped #1590 (below signal threshold), summarized #1689 into a
  new entry. KB now 121 entries. Eval re-run after: still 100% (20/20).
  **Triggered the workflow live via `workflow_dispatch` and watched it run** — it
  succeeded, but only exercised the "nothing new" no-op path (0 issues found,
  since my local run had already advanced the watermark past today) — confirmed
  `ANTHROPIC_API_KEY` is genuinely empty in that run's env, exactly as expected
  with no secret set yet. **This means the actual LLM-summarization path has NOT
  been proven inside GitHub Actions itself yet** — only locally. The first real
  test of that path will be whenever a new issue closes on RickKessler/SNANA after
  Ayan adds the secret. **The only remaining step is still Ayan's:
  `gh secret set ANTHROPIC_API_KEY`, run locally so the key never appears in a
  chat transcript.** Once that's done, no further code changes are needed — the
  weekly cron (Mondays 13:00 UTC) and manual dispatch are both already live.









