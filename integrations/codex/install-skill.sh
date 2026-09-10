#!/usr/bin/env bash
# Helper script to install the canonical snana-assistant skill for OpenAI Codex
# Supports user-global (~/.agents/skills/snana-assistant) or project-local (.agents/skills/snana-assistant)

set -euo pipefail

TARGET_MODE="${1:---user}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CANONICAL_SKILL="${REPO_ROOT}/agent-skill/snana-assistant"

if [ ! -d "${CANONICAL_SKILL}" ]; then
    echo "Error: Canonical skill directory not found at ${CANONICAL_SKILL}" >&2
    exit 1
fi

if [ "${TARGET_MODE}" = "--repo" ]; then
    DEST_DIR="${REPO_ROOT}/.agents/skills/snana-assistant"
elif [ "${TARGET_MODE}" = "--user" ]; then
    DEST_DIR="${HOME}/.agents/skills/snana-assistant"
else
    DEST_DIR="${TARGET_MODE}"
fi

echo "Installing snana-assistant Agent Skill to: ${DEST_DIR}"
mkdir -p "${DEST_DIR}"
cp -R "${CANONICAL_SKILL}/"* "${DEST_DIR}/"

echo "Skill successfully installed!"
echo "Next step: Configure the read-only MCP server in your Codex config as described in integrations/codex/README.md."
