"""Filesystem locations for the SLATE package.

Every path derives from this file's location, so the package resolves
its databases and data cache the same way regardless of the process
working directory. Run the server from the repo root or from anywhere
else; the files land in the same place.

SLATE_DATA_CACHE overrides the market-data cache directory (absolute or
relative path) for setups that keep data outside the package.
"""

import os
from pathlib import Path

# <repo>/slate_core/config/paths.py -> package root one level up
_PKG_ROOT = Path(__file__).resolve().parents[1]

# Package directory as a plain string for f-string path building.
CORE_ROOT = str(_PKG_ROOT)

# Repo root (parent of the package) — reference only; nothing resolves
# against it by default anymore.
REPO_ROOT = str(_PKG_ROOT.parent)

_env_cache = os.environ.get("SLATE_DATA_CACHE")
DATA_CACHE_DIR = str(Path(_env_cache).resolve()) if _env_cache else str(_PKG_ROOT / "data_cache")


def db_path(name: str) -> str:
    """Absolute path of a database or artifact file inside the package."""
    return f"{CORE_ROOT}/{name}"
