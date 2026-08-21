# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
