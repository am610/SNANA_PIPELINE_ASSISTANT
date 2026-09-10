#!/usr/bin/env python3
"""Syncs the canonical Agent Skill (agent-skill/snana-assistant/) to downstream targets:
- skill/SKILL.md (compatibility path for existing Claude Code installs)
- integrations/claude-marketplace/plugins/snana-assistant/skills/snana-assistant/

Validates that no drift exists between canonical source and packaged targets.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "agent-skill" / "snana-assistant"
COMPAT_SKILL = ROOT / "skill" / "SKILL.md"
CLAUDE_PLUGIN_SKILL_DIR = (
    ROOT
    / "integrations"
    / "claude-marketplace"
    / "plugins"
    / "snana-assistant"
    / "skills"
    / "snana-assistant"
)


def sync(check_only: bool = False) -> bool:
    if not CANONICAL_DIR.exists():
        print(f"Error: Canonical skill directory not found: {CANONICAL_DIR}", file=sys.stderr)
        return False

    canonical_skill_file = CANONICAL_DIR / "SKILL.md"
    drift_detected = False

    # 1. Check/sync compatibility skill/SKILL.md
    if COMPAT_SKILL.exists():
        if not filecmp.cmp(canonical_skill_file, COMPAT_SKILL, shallow=False):
            if check_only:
                print(f"DRIFT DETECTED: {COMPAT_SKILL} differs from canonical {canonical_skill_file}")
                drift_detected = True
            else:
                shutil.copy2(canonical_skill_file, COMPAT_SKILL)
                print(f"Synced {canonical_skill_file} -> {COMPAT_SKILL}")
    else:
        if check_only:
            print(f"DRIFT DETECTED: {COMPAT_SKILL} does not exist")
            drift_detected = True
        else:
            COMPAT_SKILL.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(canonical_skill_file, COMPAT_SKILL)
            print(f"Created {COMPAT_SKILL} from {canonical_skill_file}")

    # 2. Check/sync Claude plugin skill directory if parent plugin dir exists
    plugin_parent = CLAUDE_PLUGIN_SKILL_DIR.parent
    if plugin_parent.exists() or not check_only:
        CLAUDE_PLUGIN_SKILL_DIR.mkdir(parents=True, exist_ok=True)
        # Copy SKILL.md and references
        dest_skill_file = CLAUDE_PLUGIN_SKILL_DIR / "SKILL.md"
        if dest_skill_file.exists():
            if not filecmp.cmp(canonical_skill_file, dest_skill_file, shallow=False):
                if check_only:
                    print(f"DRIFT DETECTED: {dest_skill_file} differs from canonical {canonical_skill_file}")
                    drift_detected = True
                else:
                    shutil.copy2(canonical_skill_file, dest_skill_file)
                    print(f"Synced {canonical_skill_file} -> {dest_skill_file}")
        else:
            if check_only:
                print(f"DRIFT DETECTED: {dest_skill_file} does not exist")
                drift_detected = True
            else:
                shutil.copy2(canonical_skill_file, dest_skill_file)
                print(f"Created {dest_skill_file} from {canonical_skill_file}")

        # Sync references
        canonical_refs = CANONICAL_DIR / "references"
        dest_refs = CLAUDE_PLUGIN_SKILL_DIR / "references"
        if canonical_refs.exists():
            dest_refs.mkdir(parents=True, exist_ok=True)
            for ref_file in canonical_refs.glob("*.md"):
                target_ref = dest_refs / ref_file.name
                if target_ref.exists():
                    if not filecmp.cmp(ref_file, target_ref, shallow=False):
                        if check_only:
                            print(f"DRIFT DETECTED: {target_ref} differs from canonical {ref_file}")
                            drift_detected = True
                        else:
                            shutil.copy2(ref_file, target_ref)
                            print(f"Synced {ref_file} -> {target_ref}")
                else:
                    if check_only:
                        print(f"DRIFT DETECTED: {target_ref} does not exist")
                        drift_detected = True
                    else:
                        shutil.copy2(ref_file, target_ref)
                        print(f"Created {target_ref} from {ref_file}")

    if check_only and drift_detected:
        print("Error: Skill drift detected between canonical and packaged copies!", file=sys.stderr)
        return False

    print("Skill sync / drift check completed successfully.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Sync or verify Agent Skill packages.")
    parser.add_argument("--check", action="store_true", help="Check for drift without modifying files (CI mode)")
    args = parser.parse_args()

    success = sync(check_only=args.check)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
