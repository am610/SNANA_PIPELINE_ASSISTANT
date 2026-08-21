# SNANA Pipeline Assistant

An LLM-powered operations assistant for SNANA/Pippin pipelines (SuperNova ANAlysis — the simulation, light-curve fitting, and bias-correction engine underpinning DES, LSST-DESC, Roman, and Euclid supernova cosmology).

This assistant is designed to diagnose operational pipeline failures (stale lock files, cached-vs-source config mismatches, scheduler job-name collisions, and known configurations bugs) against a curated, structured knowledge base and local documentation.

---

## Technical Architecture

The assistant operates as a stateless agent executing a tool-use loop over a structured retrieval index and local environment-probed states:

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

### 1. Operational-First Debugging Flow
Experienced pipeline operators diagnose failures using a strict hierarchy of operational checks before looking at code or complex parameter bugs. The assistant replicates this discipline by exposing read-only tools to the LLM agent:
* **Scheduler State (`check_job_status`):** Checks the Slurm queue for active, completing (`CG`), or pending (`PD`) jobs, ruling out scheduler job-name collisions and queue limits first.
* **Config Staging Mismatches (`diff_config`):** Pippin caches configuration files in its output staging directories at runtime. The assistant diffs the user's source YAML against the staged execution copies to flag when config fixes aren't being picked up.
* **Log Scanning (`read_log_tail`):** Automatically tails execution logs and flags common low-level failure patterns, such as Out-Of-Memory (OOM) aborts, Segmentation Faults, and SIGKILLs.

### 2. The Information Retrieval (IR) Engine
To match user queries to historical failure modes and technical manuals, the assistant runs a local, zero-network retrieval engine:
* **Lexical Search (BM25):** The curated database of 120+ structured entries (symptom, cause, fix, scope, status, source) is indexed and ranked on-the-fly using the BM25 algorithm.
* **Morphological Prefix Fallback:** For short codes or technical parameters (e.g., `HOSTLIB_DZTOL`), search queries are matched using character-sequence prefixes and substrings to prevent retrieval failures on typos.
* **LaTeX Manual Indexing:** The assistant chunked the 15,000+ line LaTeX source of the official SNANA manual into 279 section-specific chunks, making the parameters searchable as cohesive paragraph blocks.

### 3. Local Offline Executions
For users operating on secure compute environments or login nodes where external internet access is restricted, the assistant can run completely offline. By running a local model server via **Ollama**, the BM25 knowledge search and manual retrieval operate locally with zero data egress.

---

## Two-Tier Distribution

The assistant is distributed across two tiers using the same underlying knowledge base:

1. **Quick Start — Claude Code Session Skill:** A zero-setup session skill that inherits the context of your active terminal session.
2. **Deterministic & Scripted — CLI Application:** A pinned-model command-line tool with deterministic Python-based tools, fully covered by a 20-case evaluation harness.

---

## Quickstart

Get started in three commands:

```bash
pip install snana-assistant[all]
snana-assistant init
snana-assistant diagnose "My LCFIT stage is stuck waiting for a lock file"
```
