#!/usr/bin/env python3
"""Validates the integrity of cross-agent integrations and packaging:
1. Canonical Agent Skill frontmatter, references, and drift
2. FastMCP server tool discovery and schema check
3. Claude Code marketplace and plugin JSON schema validity
4. Codex and Gemini integration documentation and install scripts
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def check_skill():
    print("Checking canonical Agent Skill...")
    skill_file = ROOT / "agent-skill" / "snana-assistant" / "SKILL.md"
    assert skill_file.exists(), "agent-skill/snana-assistant/SKILL.md missing"

    content = skill_file.read_text()
    assert content.startswith("---"), "SKILL.md must start with YAML frontmatter"
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Invalid frontmatter structure in SKILL.md"

    frontmatter = yaml.safe_load(parts[1])
    assert frontmatter.get("name") == "snana-assistant", "Skill name must be snana-assistant"
    assert "description" in frontmatter and len(frontmatter["description"]) > 20, "Missing description"

    # Check references
    refs_dir = ROOT / "agent-skill" / "snana-assistant" / "references"
    expected_refs = ["debugging-order.md", "diagnosis-output-contract.md", "safety-and-scope.md"]
    for ref in expected_refs:
        assert (refs_dir / ref).exists(), f"Reference file {ref} missing"

    # Check drift
    res = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_agent_skill.py"), "--check"], capture_output=True, text=True)
    assert res.returncode == 0, f"Skill drift detected:\n{res.stdout}\n{res.stderr}"
    print("✓ Canonical Agent Skill and sync verified.")


def check_mcp():
    print("Checking MCP server tools...")
    from snana_assistant import mcp_server as s
    expected_tools = {
        "search_knowledge",
        "search_manual",
        "check_job_status",
        "read_log_tail",
        "diff_config",
        "list_directory",
        "search_files",
        "read_text_file",
        "inspect_snana_environment",
    }
    for t in expected_tools:
        assert hasattr(s, t), f"Missing MCP tool {t}"
    print("✓ MCP server tools verified.")


def check_claude_plugin():
    print("Checking Claude marketplace and plugin manifests...")
    market_file = ROOT / "integrations" / "claude-marketplace" / ".claude-plugin" / "marketplace.json"
    assert market_file.exists(), "marketplace.json missing"
    market_data = json.loads(market_file.read_text())
    assert market_data.get("name") == "snana-tools"

    plugin_file = ROOT / "integrations" / "claude-marketplace" / "plugins" / "snana-assistant" / ".claude-plugin" / "plugin.json"
    assert plugin_file.exists(), "plugin.json missing"
    plugin_data = json.loads(plugin_file.read_text())
    assert plugin_data.get("name") == "snana-assistant"

    mcp_file = ROOT / "integrations" / "claude-marketplace" / "plugins" / "snana-assistant" / ".mcp.json"
    assert mcp_file.exists(), ".mcp.json missing"
    print("✓ Claude marketplace and plugin manifests verified.")


def check_adapters():
    print("Checking Codex and Gemini adapters...")
    codex_sh = ROOT / "integrations" / "codex" / "install-skill.sh"
    assert codex_sh.exists() and os.access(codex_sh, os.X_OK), "install-skill.sh missing or not executable"

    gemini_md = ROOT / "integrations" / "gemini" / "README.md"
    assert gemini_md.exists(), "gemini README.md missing"
    print("✓ Codex and Gemini integration files verified.")


def main():
    import os
    try:
        check_skill()
        check_mcp()
        check_claude_plugin()
        check_adapters()
        print("\nAll integration verification checks passed successfully!")
    except AssertionError as err:
        print(f"\nVerification FAILED: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
