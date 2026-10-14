"""Generic congressional ballot polls (Silver Bulletin database, back to 1994).

Silver Bulletin publishes a downloadable file of every generic ballot poll in its
database. Place the download in data/inbox/generic_ballot/. Because the exact
column names are unverified, config/sources.yaml carries a column_map from the
file's names to ours; the parser fails loudly if they do not match.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import pick_up_inbox, vintage_dir

NAME = "generic_ballot"
CLEAN_NAME = "generic_ballot_polls"
KEYS = ["pollster", "end_date", "population"]

DEFAULT_MAP = {
    "pollster": "pollster",
    "end_date": "end_date",
    "population": "population",
    "dem": "dem",
    "rep": "rep",
}


def standardize(df: pd.DataFrame, column_map: dict | None = None) -> pd.DataFrame:
    cmap = {**DEFAULT_MAP, **(column_map or {})}  # ours -> theirs
    missing = [theirs for theirs in cmap.values() if theirs not in df.columns]
    if missing:
        raise ValueError(
            f"{NAME}: expected columns {missing}. Columns present: {list(df.columns)}. "
            "Update column_map in config/sources.yaml."
        )
    out = pd.DataFrame({ours: df[theirs] for ours, theirs in cmap.items()})
    out["end_date"] = pd.to_datetime(out["end_date"], errors="coerce").dt.date.astype("string")
    out["dem"] = pd.to_numeric(out["dem"], errors="coerce")
    out["rep"] = pd.to_numeric(out["rep"], errors="coerce")
    out = out.dropna(subset=["end_date", "dem", "rep"])
    out["margin"] = out["dem"] - out["rep"]  # positive = Democratic lead, in points
    return out


def fetch(vintage: str, cfg: dict) -> list[Path]:
    vdir = vintage_dir(NAME, vintage)
    files = pick_up_inbox(NAME, vdir, ("*.csv",))
    if not files:
        raise RuntimeError(
            f"{NAME}: no files. Download the poll database from the Silver Bulletin "
            f"generic ballot page into data/inbox/{NAME}/"
        )
    return files


def clean(vintage: str, cfg: dict) -> pd.DataFrame:
    vdir = vintage_dir(NAME, vintage, create=False)
    frames = [standardize(pd.read_csv(p), cfg.get("column_map")) for p in sorted(vdir.glob("*.csv"))]
    if not frames:
        raise RuntimeError(f"no poll files found in {vdir}")
    out = pd.concat(frames, ignore_index=True)
    out["vintage"] = vintage
    return out
