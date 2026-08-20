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

### Phase 2 — Review-gated feedback loop
- New failure cases (from you or other users) submitted as `status: unverified` entries
- Lightweight review/promotion step before an entry is trusted and surfaced to other
  users
- Turns the static v1 knowledge base into one that improves with use

### Phase 3 — Platform independence
- Scheduler abstraction beyond Slurm
- Environment-specific vs. universal entries already separated (Phase 1 design), so
  this phase is mostly packaging: pip-installable add-on that a user installs
  alongside their own SNANA environment and points at their own output directory
- Local/open-weight backend option matters most here (DOE/HPC users wary of sending
  logs to an external API)

### Phase 4 — Community-scale validation
- Test against failure cases from other users'/institutions' pipelines, not just this
  account's history
- This is also where a funded proposal (see `GRANTS.md`) would carry the work past
  what's feasible as an unfunded side project

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
