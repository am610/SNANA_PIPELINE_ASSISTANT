# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
