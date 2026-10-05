"""Filesystem locations shared by the SQLite stores."""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def data_dir() -> Path:
    """SQLite / artifact directory — override with VANTAGE_DATA_DIR (research runs, tests)."""
    raw = os.environ.get("VANTAGE_DATA_DIR", "").strip()
    return Path(raw) if raw else _DEFAULT_DATA_DIR
