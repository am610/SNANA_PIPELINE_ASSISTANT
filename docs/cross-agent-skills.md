# Cross-Agent Skills & MCP Integration

The SNANA Pipeline Assistant is built on open agent standards. It allows researchers to use the **same** domain debugging intelligence, operational order, and read-only tools across:
- **Claude Code** (via Marketplace Plugin)
- **OpenAI Codex** (via Agent Skill)
- **Google Gemini CLI** (via Agent Skill)
- **Standalone CLI** (`isnana` / `snana-assistant`)

```text
                         SNANA Pipeline Assistant
                                   │
                  Canonical Domain Procedure & Safety
                     (agent-skill/snana-assistant/)
                                   │
                 ┌─────────────────┴─────────────────┐
                 ▼                                   ▼
      AI Coding Agent Skills              Deterministic Read-Only MCP
   (Claude Code / Codex / Gemini)           (snana-assistant-mcp)
                 │                                   │
                 └─────────────────┬─────────────────┘
                                   ▼
                        Standalone CLI & Eval
                         (isnana / snana-assistant)
```

---

## 1. Claude Code

### Option A: Install from Marketplace
Add the repository-hosted marketplace and install the plugin:
```bash
/plugin marketplace add am610/SNANA_PIPELINE_ASSISTANT
/plugin install snana-assistant@snana-tools
```

### Option B: Direct Skill Copy
Copy the canonical skill directory into your Claude skills directory:
```bash
cp -R agent-skill/snana-assistant ~/.claude/skills/
```

---

## 2. OpenAI Codex

Codex discovers skills adhering to the open Agent Skills specification.

### Installation
Run the included install helper:
```bash
# Global install (~/.agents/skills/snana-assistant):
./integrations/codex/install-skill.sh --user

# Repository-scoped install (.agents/skills/snana-assistant):
./integrations/codex/install-skill.sh --repo
```

### MCP Registration
To give Codex access to the deterministic read-only tools, register `snana-assistant-mcp` in your Codex configuration:
```json
{
  "mcpServers": {
    "snana-assistant": {
      "command": "snana-assistant-mcp",
      "args": []
    }
  }
}
```

---

## 3. Google Gemini CLI

Gemini CLI natively supports Agent Skills and MCP servers.

### Installation
Install directly via git URL:
```bash
gemini skills install https://github.com/am610/SNANA_PIPELINE_ASSISTANT.git \
  --path agent-skill/snana-assistant
```
Or when working in a local clone:
```bash
gemini skills link ./agent-skill/snana-assistant
```

### MCP Registration
Register `snana-assistant-mcp` with Gemini CLI:
```bash
gemini mcp add snana-assistant --command snana-assistant-mcp
```

---

## 4. Exposed Read-Only MCP Tools

The `snana-assistant-mcp` server exposes 9 strictly bounded, read-only tools:

| Tool Name | Purpose | Safety Guarantees |
| :--- | :--- | :--- |
| `search_knowledge` | BM25 lexical search over 120+ curated failure modes | Read-only; returns cited entry IDs |
| `search_manual` | Paragraph search over section-chunked LaTeX manual | Read-only; extracts formula & parameter context |
| `check_job_status` | Inspects Slurm (`squeue`) or PBS (`qstat`) jobs | Read-only; cannot submit, modify, or cancel jobs |
| `read_log_tail` | Tails batch/pipeline logs & flags OOM/aborts | Bounded (max 1000 lines); rejects binary files |
| `diff_config` | Compares edited config against Pippin staging copy | Identifies stale staging bugs |
| `list_directory` | Bounded file listing (`ls`) | Max 200 entries; reports truncation |
| `search_files` | Bounded pattern grep (`grep -r`) | Max 50 hits, depth 4; skips binaries and symlink trees |
| `read_text_file` | Inspects small text or YAML configs | Rejects binary/FITS/archives; max 500 KB limit |
| `inspect_snana_environment` | Safe inspection of SNANA and HPC environment paths | Never exposes secrets, tokens, or passwords |

---

## 5. Adding New Skills (For Collaborators)

Collaborators can contribute new domain skills (e.g., host galaxy matching, SALT3 calibration, cosmology chains):
1. Create a directory: `agent-skill/<your-skill-name>/`
2. Add a `SKILL.md` with standard YAML frontmatter (`name`, `description`).
3. Add supporting documentation under `references/`.
4. Run `python3 scripts/verify_integrations.py` to confirm cross-platform compatibility across Claude, Codex, and Gemini.
