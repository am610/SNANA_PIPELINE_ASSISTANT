"""Centralized read-only safety policies and bounds enforcement for SNANA Pipeline Assistant.

Enforces:
- Read-only filesystem operations
- Path canonicalization and traversal guards
- Symlink loop/recursion guards
- Bounded line counts, byte sizes, match counts, and search depth
- Binary/FITS/archive skipping
- Scheduler commands strictly read-only (no job submission or manipulation)
- Sanitized environment inspection (no secrets, passwords, or full dumps)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Set

# Limits
MAX_LOG_TAIL_LINES = 1000
DEFAULT_LOG_TAIL_LINES = 200
MAX_FILE_LINES = 1000
DEFAULT_FILE_LINES = 500
MAX_FILE_BYTES = 500_000  # 500 KB limit for read_file
MAX_DIR_ENTRIES = 200
MAX_SEARCH_HITS = 50
MAX_SEARCH_DEPTH = 4

# Skip directories and binary extensions
SKIP_DIRS: Set[str] = {
    ".git", "__pycache__", ".ipynb_checkpoints", "node_modules", ".venv", ".tox"
}

BINARY_SUFFIXES: Set[str] = {
    ".fits", ".gz", ".tar", ".zip", ".npy", ".npz", ".pdf", ".png", ".jpg", ".jpeg",
    ".pyc", ".so", ".o", ".root", ".hdf5", ".h5", ".pkl", ".parquet", ".whl",
}

# Sensitive keys that should NEVER be exposed in environment inspection
SENSITIVE_ENV_SUBSTRINGS = (
    "KEY", "TOKEN", "SECRET", "PASS", "CRED", "AUTH", "ID_RSA", "SESSION"
)

# Allowed SNANA / HPC relevant environment variables
SAFE_SNANA_ENV_VARS = (
    "SNDATA_ROOT",
    "MY_SNDATA_ROOT",
    "SNANA_DIR",
    "PIPPIN_DIR",
    "PIPPIN_OUTPUT",
    "SBATCH_TEMPLATES",
    "SNANA_DEBUG",
    "SNANA_LSST_ROOT",
    "DES_ROOT",
    "SCRATCH",
    "PSCRATCH",
    "NERSC_HOST",
    "SLURM_CLUSTER_NAME",
    "SLURM_SUBMIT_DIR",
    "USER",
    "SHELL",
    "PYTHONPATH",
)


def looks_binary(path: Path | str) -> bool:
    """Check if a file appears to be binary based on suffix or initial null bytes."""
    p = Path(path)
    if p.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        with open(p, "rb") as f:
            chunk = f.read(2048)
            return b"\0" in chunk
    except Exception:
        return True


def canonicalize_path(path: str | Path) -> Path:
    """Expand user and resolve path safely."""
    p = Path(path).expanduser()
    try:
        return p.resolve()
    except Exception:
        return p.absolute()


def sanitize_environment() -> dict[str, str]:
    """Return only safe, non-sensitive SNANA/HPC environment variables."""
    sanitized = {}
    for k in SAFE_SNANA_ENV_VARS:
        if k in os.environ:
            val = os.environ[k]
            # Safety check against accidentally sensitive values
            if any(s in k.upper() for s in SENSITIVE_ENV_SUBSTRINGS):
                continue
            sanitized[k] = val

    # Include any custom SNANA_* environment variables if not sensitive
    for k, v in os.environ.items():
        if k.startswith("SNANA_") or k.startswith("PIPPIN_"):
            if not any(s in k.upper() for s in SENSITIVE_ENV_SUBSTRINGS):
                sanitized[k] = v

    return sanitized
