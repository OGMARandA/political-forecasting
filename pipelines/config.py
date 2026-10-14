"""Loads config/sources.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml

from .common import root


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else root() / "config" / "sources.yaml"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
