# Google Gemini CLI Integration

Gemini CLI supports the open **Agent Skills** specification and Model Context Protocol (MCP). This integration allows Gemini CLI to use the identical canonical domain skill and safe read-only tools.

## 1. Install the Canonical Skill

Install directly from GitHub via the Gemini CLI skills manager:

```bash
gemini skills install https://github.com/am610/SNANA_PIPELINE_ASSISTANT.git \
  --path agent-skill/snana-assistant
```

Or, when working in a local clone:

```bash
gemini skills link ./agent-skill/snana-assistant
```

## 2. Register the Read-Only MCP Server

Ensure `isnana` is installed with MCP support:
```bash
pip install "isnana[mcp]"
# Or in editable development clone:
pip install -e ".[mcp]"
```

Register `snana-assistant-mcp` with Gemini CLI:

```bash
gemini mcp add snana-assistant --command snana-assistant-mcp
```

Or add to your Gemini configuration (`~/.gemini/config.json` or project settings):

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

In your Gemini CLI session:
> "My Pippin stage failed with Killed. Diagnose using snana-assistant."

Gemini CLI will activate the canonical skill, invoke `search_knowledge` or `read_log_tail` through MCP, and output the structured diagnosis adhering to the contract.
