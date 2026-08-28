#!/usr/bin/env python3
"""Sync the built knowledge base into the installable package.

Single source of truth: ``knowledge/``. The copies under
``src/snana_assistant/data/`` are what actually ships in the wheel/sdist
(declared as package-data in ``pyproject.toml``), so they must be regenerated
from ``knowledge/`` before every build.

Usage::

    python scripts/sync_package_data.py           # copy knowledge/ -> src/.../data/
    python scripts/sync_package_data.py --check    # exit 1 if out of sync (CI gate)

The release workflow runs ``--check`` after the copy so a release can never
ship a stale knowledge base.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "knowledge"
DEST_DIR = REPO_ROOT / "src" / "snana_assistant" / "data"

DATA_FILES = ["entries.yaml", "manual_chunks.json"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not copy; exit non-zero if the packaged copies differ from knowledge/.",
    )
    args = parser.parse_args()

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    exit_code = 0

    for name in DATA_FILES:
        src = SRC_DIR / name
        dest = DEST_DIR / name
        if not src.exists():
            print(f"ERROR: source file missing: {src}", file=sys.stderr)
            return 2

        in_sync = dest.exists() and filecmp.cmp(src, dest, shallow=False)

        if args.check:
            if in_sync:
                print(f"OK    {name} (packaged copy matches knowledge/)")
            else:
                print(
                    f"STALE {name}: {dest} differs from {src}. "
                    f"Run `python scripts/sync_package_data.py` and commit.",
                    file=sys.stderr,
                )
                exit_code = 1
        else:
            if in_sync:
                print(f"unchanged  {name}")
            else:
                shutil.copy2(src, dest)
                print(f"synced     {name} -> {dest.relative_to(REPO_ROOT)}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
