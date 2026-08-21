# SNANA Pipeline Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Test Suite](https://img.shields.io/badge/Evaluation--Harness-100%25%20Passed-success)](eval/results.md)


An LLM-powered operations assistant for SNANA/Pippin pipelines. Automatically diagnoses pipeline failures (stale locks, cached config mismatches, out-of-memory errors) using a curated, structured knowledge base and NERSC/Slurm scheduler state. Follows operational-first debugging discipline to rule out simple causes before speculating about code-level bugs.

---

## Quickstart

```bash
pip install snana-assistant[all]
snana-assistant init
snana-assistant diagnose "BBC aborts citing sigint, tried sigint_fix, still fails"
```

---

## Two ways to run this

This assistant is distributed in two tiers, sharing the same underlying knowledge base ([`entries.yaml`](knowledge/entries.yaml)):

* **Quick Start — Claude Code Skill** ([`skill/SKILL.md`](skill/SKILL.md)): Zero setup, uses whatever Claude Code session you already have running. Best-effort (model and tool execution depend on your Claude Code plan, not pinned, and not covered by the eval harness).
* **Scripted & Reproducible — Standalone CLI** (this package): Pinned model, deterministic Python tools, covered by an evaluation suite ([`cases.yaml`](eval/cases.yaml)). Runs non-interactively (cron/CI/scripted) and supports local offline models.

---

## How It Works

```mermaid
graph TD
    User([User Query]) --> Agent[Agent Loop]
    Agent --> KB[BM25 + Morphological Knowledge Base]
    Agent --> Tools[CLI Diagnostic Tools]
    Tools --> Slurm[check_job_status]
    Tools --> Config[diff_config]
    Tools --> Logs[read_log_tail]
    Tools --> Manual[search_manual]
    KB --> Result[\[entry-id\] Cited Cause + Fix]
```

1. **Scheduler State:** Checks Slurm queue for completing (`CG`), pending (`PD`), or job-name truncation conflicts.
2. **Config Staging:** Compares your source configuration against Pippin's output staging directory copy to catch cached config mismatches.
3. **Log Scanning:** Tails execution logs and parses standard patterns (OOM, killed, timeout, segmentation faults).
4. **Knowledge Search:** Queries a compiled, structured database of historical failure modes.
5. **LaTeX Manual Index:** Fallback search over section-chunked SNANA manual LaTeX files.

---

## Container (no clone, no build)

```bash
docker pull ghcr.io/am610/snana-pipeline-assistant:latest
docker run --rm --env-file .env ghcr.io/am610/snana-pipeline-assistant \
  diagnose "BBC aborts citing sigint, tried sigint_fix, still fails"
```

On HPC systems without a Docker daemon, Singularity/Apptainer can run the same
image directly: `singularity run docker://ghcr.io/am610/snana-pipeline-assistant:latest diagnose "..."`.
Built and pushed automatically on every change to `main` (see
`.github/workflows/publish-image.yml`) — always current with this repo.

## Local Offline Mode

DOE/HPC users wary of sending logs to external APIs can configure the tool to run entirely offline with a local model:

1. Start [Ollama](https://ollama.com/) locally: `ollama run llama3`
2. Run `snana-assistant init` and select the local model as your default backend.
3. Knowledge Base searches and SNANA LaTeX manual lookups run fully offline, zero-key, immediately after install.
