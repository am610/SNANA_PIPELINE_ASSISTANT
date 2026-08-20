#!/bin/bash
# Syncs current dev workspace changes to the persistent home directory copy
# which in turn keeps the active Claude Code skill in sync.
cp -f knowledge/entries.yaml ~/SNANA_PIPELINE_ASSISTANT/knowledge/entries.yaml
cp -f skill/SKILL.md ~/SNANA_PIPELINE_ASSISTANT/skill/SKILL.md
echo "Synced entries.yaml and SKILL.md to persistent home space (~/SNANA_PIPELINE_ASSISTANT/)."
