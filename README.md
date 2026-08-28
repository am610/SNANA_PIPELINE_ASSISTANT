# SNANA Pipeline Assistant

[![Documentation Status](https://readthedocs.org/projects/snana-pipeline-assistant/badge/?version=latest)](https://snana-pipeline-assistant.readthedocs.io/en/latest/?badge=latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Test Suite](https://img.shields.io/badge/Evaluation--Harness-100%25%20Passed-success)](eval/results.md)


An LLM-powered operations assistant for SNANA/Pippin pipelines. Automatically diagnoses pipeline failures (stale locks, cached config mismatches, out-of-memory errors) using a curated, structured knowledge base and NERSC/Slurm scheduler state. Follows operational-first debugging discipline to rule out simple causes before speculating about code-level bugs.

![demo: snana-assistant diagnose finding a cited, verified failure mode](assets/demo.gif)

---

## Quickstart

> **Not distributed via PyPI.** `pip install snana-assistant` will not work and is not
> planned — install from source (below) or use the
> [container](#container-no-clone-no-build). Both track `main` directly, which is what
> cluster users and collaborators actually want.

### Option A: From Source (Recommended for Collaborators / Midway)
To run on Midway or other clusters, clone and install locally. 

First, ensure you are using **Python 3.10 or higher**. You can set up your environment using either **Conda** or a standard **virtualenv**:

#### 1. Setup using Conda (Recommended if Conda is active on your cluster)
```bash
# Create and activate a Python 3.10 environment
conda create -n snana_env python=3.10 -y
conda activate snana_env

# Clone and install the package
git clone https://github.com/am610/SNANA_PIPELINE_ASSISTANT.git
cd SNANA_PIPELINE_ASSISTANT
pip install --upgrade pip
pip install -e .[all]
```

#### 2. Setup using a standard virtualenv
```bash
git clone https://github.com/am610/SNANA_PIPELINE_ASSISTANT.git
cd SNANA_PIPELINE_ASSISTANT

# (Optional: load python/3.10 if default is older)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip  # Crucial on older cluster environments
pip install -e .[all]
```

#### Then, configure and run:
```bash
snana-assistant init

# Set your API key (supports ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY)
export ANTHROPIC_API_KEY="your-api-key"

snana-assistant diagnose "BBC aborts citing sigint, tried sigint_fix, still fails"
```

#### Subsequent Sessions (Re-activating)
In future cluster logins, you can run the assistant from **any directory** (it does not need to be the cloned repository directory) by running:

```bash
# If you set up using Conda:
conda activate snana_env

# If you set up using a virtualenv:
source /path/to/SNANA_PIPELINE_ASSISTANT/.venv/bin/activate

# (Optional) Auto-load your API key every session by appending it once to ~/.bashrc:
# echo 'export ANTHROPIC_API_KEY="your-api-key"' >> ~/.bashrc
# snana-assistant diagnose "BBC aborts citing sigint, tried sigint_fix, still fails"
```

---

## Two ways to run this

This assistant is distributed in two tiers, sharing the same underlying knowledge base ([`entries.yaml`](knowledge/entries.yaml)):

* **Quick Start — Claude Code Skill** ([`skill/SKILL.md`](skill/SKILL.md)): Zero setup, uses whatever Claude Code session you already have running. Best-effort (model and tool execution depend on your Claude Code plan, not pinned, and not covered by the eval harness).
* **Scripted & Reproducible — Standalone CLI** (this package): Pinned model, deterministic Python tools, covered by an evaluation suite ([`cases.yaml`](eval/cases.yaml)). Runs non-interactively (cron/CI/scripted) and supports local offline models.

---

## Finding things: the assistant browses for you

You don't need to know a path, or paste an `ls`. The assistant can list directories and
grep file contents itself, so questions like these work directly:

```bash
snana-assistant diagnose "check the files in this directory and see which script uses sim_ia_salt_des5yr.input"
snana-assistant diagnose "where is DES-SN5YR_DES.HOSTLIB referenced?"
```

It will `list_directory` to see what exists, `search_files` to find which script or YAML
references the file, then read the hits to confirm — rather than inferring from naming
convention or asking you to supply the path.

Searches are bounded so a Pippin output tree can't swamp the answer: 200 entries per
listing, 50 matches per search, 4 levels deep, binaries/FITS/gzip skipped, symlinks not
followed. Anything truncated is reported.

---

## Interactive sessions (`chat`)

`diagnose` answers one question and forgets it. For anything that takes a few
follow-ups, use `chat` — the conversation is carried across turns, so the assistant
remembers what you asked, what it answered, and which files it already read:

```bash
snana-assistant chat
```

```
you> check sim_ia_salt_des5yr.input -- what does it do and what does it depend on?
...
you> what about that WGTMAP path, will it resolve under Pippin?
you> /reset     # start a fresh conversation
you> /exit      # quit (Ctrl-D also works)
```

Long sessions accumulate context — every file and manual chunk the assistant read stays
in the conversation and is resent each turn, which costs tokens. `/reset` when you move
to an unrelated problem.

Programmatic equivalent:

```python
from snana_assistant.agent import Agent

session = Agent().session()
session.ask("what does sim_ia_salt_des5yr.input do?")
session.ask("and what was the GENVERSION in it?")   # remembers the file
```

---

## Asking about config files, not just failures

Besides diagnosing crashes, `diagnose` will read and review a config/input file you point it
at — what it does, what it depends on, and whether any keys look wrong:

```bash
snana-assistant diagnose "check sim_ia_salt_des5yr.input -- is it written correctly, \
  what dependency files does it call, and what is it supposed to do?"
```

These reviews cost more agent turns than a failure lookup, because the assistant searches the
knowledge base, gotchas, and manual before it opens the file, then follows any
`INPUT_FILE_INCLUDE` chain. If an answer ever comes back tagged

```
[incomplete: stopped after 15 tool-use turns without reaching a final answer -- rerun with a higher --max-turns]
```

rerun with a bigger budget:

```bash
snana-assistant diagnose "..." --max-turns 25 --max-tokens 8192
```

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

---

## Speed and cost

Answers stream as they are written, so you see output in ~2s rather than waiting for the
whole reply. Pipe or redirect the output and it reverts to a single clean block for
scripts; `--no-stream` forces that explicitly.

The prompt prefix (system prompt + tool schemas + conversation so far) is cached between
turns, which cuts input-token cost roughly in half — measured 10,825 → 5,570 billed input
equivalents on a 3-turn query. Savings are largest in `chat`, where history compounds.
Cache entries expire after ~5 minutes, so an occasional one-shot query pays a small write
surcharge without benefiting; set `SNANA_ASSISTANT_NO_CACHE=1` to disable.

Most remaining latency is simply the number of sequential model calls an investigation
needs — each tool round trip is 1.5–3.5s. Raise or lower it with `--max-turns`.

---

## Local Offline Mode

DOE/HPC users wary of sending logs to external APIs can configure the tool to run entirely offline with a local model:

1. Start [Ollama](https://ollama.com/) locally: `ollama run llama3`
2. Run `snana-assistant init` and select the local model as your default backend.
3. Knowledge Base searches and SNANA LaTeX manual lookups run fully offline, zero-key, immediately after install.

---

## Contributing Feedback

If the assistant cannot diagnose your issue, it logs the uncaptured query locally. You can generate a pre-filled, templated GitHub issue to submit the new failure mode for verification:

```bash
snana-assistant feedback
```
This command URL-encodes your query and generates a draft issue link, keeping your actual data private unless you choose to submit it.

