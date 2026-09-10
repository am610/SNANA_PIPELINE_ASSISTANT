# OpenAI Codex Integration

This directory configures the canonical **snana-assistant** Agent Skill and read-only MCP server for use with OpenAI Codex.

## 1. Install the Canonical Skill

Run the installation helper:

```bash
# Global install (available across all your projects):
./integrations/codex/install-skill.sh --user
# Installs to ~/.agents/skills/snana-assistant/

# Or repository-scoped install:
./integrations/codex/install-skill.sh --repo
# Installs to .agents/skills/snana-assistant/
```

Codex automatically discovers skills adhering to the open Agent Skills specification from `.agents/skills/` or `~/.agents/skills/`.

## 2. Register the Read-Only MCP Server

Ensure `isnana` is installed with MCP support:
```bash
pip install "isnana[mcp]"
# Or in development clone:
pip install -e ".[mcp]"
```

Add the server to your Codex MCP configuration (e.g., `~/.codex/config.json` or project MCP configuration):

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

## 3. Verify Setup

In Codex, query:
> "Check the status of my SNANA pipeline run. What is the operational debugging sequence?"

Codex will load the skill procedure, query `check_job_status` or `read_log_tail` via MCP, and follow the operational-first debugging order.
