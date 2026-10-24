"""Version and release metadata for DubStudio."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Dict

APP_VERSION = "1.1.3"
SCHEMA_VERSION = 2
MIN_COMPATIBLE_SCHEMA_VERSION = 1

# Embedded commit hash (updated during release script)
BUILD_COMMIT_HASH = "dev-build"


def get_git_commit_hash() -> str:
    """Retrieve current git commit hash or embedded fallback."""
    if BUILD_COMMIT_HASH and BUILD_COMMIT_HASH != "dev-build":
        return BUILD_COMMIT_HASH

    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    return "local-dev"


def get_version_info() -> Dict[str, str | int]:
    """Return dictionary with application version metadata."""
    return {
        "version": APP_VERSION,
        "commit": get_git_commit_hash(),
        "schema_version": SCHEMA_VERSION,
        "min_compatible_schema_version": MIN_COMPATIBLE_SCHEMA_VERSION,
    }
