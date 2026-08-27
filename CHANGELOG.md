# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2] - 2026-08-27

### Changed
- **Lookup questions no longer open with a knowledge-base search -- 5 round trips down
  to 3.** `SYSTEM_PROMPT` mandated `search_knowledge` on the very first turn of *every*
  query. The curated database holds failure modes, so for "what does this input file do"
  it returned nothing useful while costing a full model round trip the user waited
  through. The prompt now classifies the request first: a SYMPTOM (failure, error, crash,
  abort, wrong output) still requires `search_knowledge` verbatim on turn one, preserving
  every citation guarantee; a LOOKUP goes straight to the tool that answers it.

  Measured A/B on the same queries: lookup 5 -> 3 round trips, 25.8s -> 18.1s (-30%);
  symptom unchanged at 2 round trips with `search_knowledge` still first. Eval 22/22,
  including all 20 citation cases.

## [0.3.1] - 2026-08-27

### Added
- **Streamed output.** `diagnose` and `chat` now print the answer as it is generated
  instead of after it completes. This does not make the work finish sooner -- it removes
  the dead time where the terminal sat blank, which is most of what "slow" felt like.
  Measured: first visible text at 2.5s instead of 4.7s (**47% less dead time**) on a
  short query; the gap is larger on long answers.

  Streaming is on when stdout is a terminal and off when piped or redirected, so
  scripted callers still get one clean block. `--no-stream` forces the old behaviour.
  Anthropic backend only; other backends accept `on_text` and ignore it.

### Changed
- **Prompt caching on the Anthropic backend -- ~48% off the input-token bill.** Every
  turn resent the entire conversation: the system prompt, ~2.7k tokens of byte-identical
  tool schemas, and every prior tool result. Measured on a 3-turn query, input tokens
  outnumbered output 24:1, so input dominated cost. One cache breakpoint on the system
  block (the prefix is ordered tools -> system -> messages, so it covers the schemas too)
  plus a rolling breakpoint at the end of the conversation.

  Measured A/B on the same query: billed input-token equivalents 10,825 -> 5,570
  (**-48.5%**), wall time 8.8s -> 8.2s (-6.5%). Savings are larger in `chat`, where
  history compounds every turn.

  Caveat: cache entries expire after ~5 minutes. Back-to-back turns within a `diagnose`
  run or an active `chat` session hit warm; an occasional one-shot run pays the 1.25x
  write surcharge and never reads it back, making that query marginally more expensive.
  Clear win for multi-turn use, roughly neutral for infrequent single queries.

  Set `SNANA_ASSISTANT_NO_CACHE=1` to disable. OpenAI caches automatically with no code
  change; Gemini explicit caching is a separate API and is not wired up.

## [0.3.0] - 2026-08-27

### Added
- **`list_directory` and `search_files` -- the assistant can now browse the filesystem.**
  Previously every filesystem tool required a path the user already knew (`read_file`,
  `read_log_tail`, `diff_config`), so "check the files in this directory and see which
  script uses this input" was impossible: the assistant correctly reported it had no way
  to list a directory and asked the user to paste an `ls`. `list_directory` is `ls`;
  `search_files` is a bounded `grep -r` over file contents, which is what answers "which
  script calls X" -- grep the filename and the calling Pippin YAML or submit script falls
  out, instead of being inferred from naming convention.
- `SYSTEM_PROMPT` now directs the assistant to find things itself rather than asking the
  user for a listing or a path it could discover.

  Bounds, because a Pippin output tree is enormous: 200 entries per listing, 50 matches
  per search, depth 4, binary/FITS/gzip files skipped, symlinks not followed (`/project2`
  is dense with them and following can loop). Truncation is always reported, never silent.

  Diagnose mode only -- setup mode drafts configs from templates and has no reason to
  browse.

## [0.2.1] - 2026-08-27

### Fixed
- **The assistant could describe a named file without reading it.** Asked about a
  `sim_*.input`, it would produce a confident, plausible description inferred purely
  from the filename and SNANA naming conventions, only admitting it had not opened the
  file when challenged. `SYSTEM_PROMPT` now requires `read_file` before any claim about
  a named file's contents, requires following `INPUT_FILE_INCLUDE` references, and
  forbids falling back to the filename when a read fails.

  Verified by direct A/B against a real user file: without the rule the assistant
  answered "Based on standard SNANA naming conventions... using the SALT2 light-curve
  model" and never opened the file (the file actually uses SALT3); with it, the file is
  read and reported correctly.

### Added
- `cwd` field on eval cases, so a case can run from a directory and name a file by a
  bare filename -- the phrasing that triggers filename-guessing.
- Eval coverage for the file-review path (`eval/fixtures/sim_ia_salt3_lowz.input`, a
  fixture whose contents contradict its name). Note this is coverage, not a regression
  guard: control runs with the rule removed still passed, so the behaviour is model
  variance rather than something the harness reliably detects. See the case comment.

## [0.2.0] - 2026-08-27

### Added
- **`snana-assistant chat` -- multi-turn sessions.** Previously every invocation was a
  standalone question: the message list was local to `Backend.diagnose()` and discarded
  on return, so follow-ups started from nothing. `chat` threads one history through the
  session, so "what about line 12?" or "why does that matter?" resolve against what was
  already established, and files already read are not re-read. `/reset` clears the
  conversation, `/exit` (or Ctrl-D) quits.
- `Backend.diagnose()` accepts an optional `history` list, appended to in place. Omit it
  for the previous one-shot behaviour -- `diagnose` is unchanged. History contents are
  provider-specific and must be used only with the backend that created them.
- `Agent.session()` / `Session.ask()` for programmatic multi-turn use.

### Fixed
- The final assistant turn is now appended to the message list before returning. It was
  previously dropped on the return path, which was invisible in one-shot mode but would
  have left a resumed conversation blind to the assistant's own last answer.
- `log_uncaptured_query` fires at most once per chat session. Per-turn logging would
  file every follow-up as its own unmatched failure mode, polluting `feedback` data.

### Changed
- Chat sessions use `CHAT_SYSTEM_PROMPT`, which scopes the "always call search_knowledge
  on the very first turn" rule to new problems rather than every message. Set once at
  session start, since the OpenAI backend bakes the system prompt into the message list
  and cannot swap it mid-conversation.

## [0.1.1] - 2026-08-27

### Fixed
- **Empty or truncated `diagnose` output on file-review queries.** The agent loop's
  defaults (`max_turns=6`, `max_tokens=1024`) were sized for curated-failure-mode
  lookups, which resolve in 2-3 turns. Informational queries -- "check this .input
  file, what does it depend on, what does it do?" -- spend their first three turns on
  `search_knowledge`/`search_gotchas`/`search_manual` before `read_file` opens
  anything, then follow `INPUT_FILE_INCLUDE` chains, so they ran out of loop and
  returned a partial sentence or no output at all. Raised to `max_turns=15`,
  `max_tokens=4096` across all backends. This surfaced when the `read_file` tool was
  added without a matching budget increase.

### Added
- `--max-turns` / `--max-tokens` flags on `snana-assistant diagnose`, so users can
  escalate a truncated investigation without editing the source.
- Eval case + fixtures (`eval/fixtures/`) covering the file-review query shape, and
  `expect_contains` assertions in the harness for cases with no entry ID to cite.
  Every case now also fails on a truncated response.

### Changed
- A run that exhausts `max_turns` is always marked `[incomplete: ...]`. Previously
  the warning appeared only when *zero* text had accumulated, so a lone preamble
  sentence was returned looking like a finished answer.

## [0.1.0] - 2026-08-21

### Added
- **Multi-Provider Backends:** Support for Anthropic (`google-genai`), OpenAI, and Gemini APIs behind a pluggable `Backend` interface, auto-detected from environment variables.
- **Standalone CLI:** Commands to `diagnose` pipeline failures and `promote` unverified knowledge entries.
- **Zero-Setup UX (`snana-assistant init`):** Configuration wizard that auto-detects NERSC/Perlmutter directories (`$SNDATA_ROOT`, `$SNANA_DIR`), sources default setup commands, and probes for local Ollama instances to offer a zero-cost local LLM option.
- **BM25 Search Retrieval:** Pure Python BM25 lexical search ranking combined with morphological similarity (common prefix/substring overlap) fallback for robust query matching.
- **LaTeX Manual Ingestion:** Tooling to chunk the 15,000+ line `snana_manual.tex` by logical section headings and serve it via chunked retrieval.
- **Batch Ingestion Script (`batch_summarize.py`):** Multi-issue summarization helper that sequentially parses candidate GitHub issues and appends them as `status: unverified` entries.
- **Claude Code Skill:** Zero-setup session skill matching the operational debugging checklist.
- **Evaluation Suite:** Harness containing 15 real failure cases with 100% verification coverage.
