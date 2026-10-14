"""MIT Election Data and Science Lab: certified House, Senate and presidential results.

Files are distributed through Harvard Dataverse (dataset pages are listed in
config/sources.yaml). Download the CSV/TAB files by hand into
data/inbox/mit_results/ the first time; the loader handles House, Senate and
president files by their standard column names and tags each row with an office.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import pick_up_inbox, vintage_dir
from .geo import to_postal

NAME = "mit_results"
CLEAN_NAME = "election_results"
KEYS = ["year", "state", "office", "district", "candidate", "stage"]

OFFICE_ALIASES = {
    "us house": "house", "us senate": "senate", "us president": "president",
    "u.s. house": "house", "u.s. senate": "senate", "u.s. president": "president",
}


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    need = ["year", "state_po", "office", "candidate", "party", "candidatevotes", "totalvotes"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(
            f"{NAME}: missing columns {missing}. Columns present: {list(df.columns)}"
        )
    out = pd.DataFrame(
        {
            "year": pd.to_numeric(df["year"], errors="coerce"),
            "state": df["state_po"].map(to_postal),
            "office": df["office"].str.lower().map(OFFICE_ALIASES).fillna(df["office"].str.lower()),
            "district": df["district"].astype(str) if "district" in df.columns else "0",
            "stage": df["stage"].astype(str).str.lower() if "stage" in df.columns else "gen",
            "special": df["special"].astype(str).str.upper() if "special" in df.columns else "FALSE",
            "candidate": df["candidate"],
            "party": df["party"],
            "candidate_votes": pd.to_numeric(df["candidatevotes"], errors="coerce"),
            "total_votes": pd.to_numeric(df["totalvotes"], errors="coerce"),
        }
    )
    out = out.dropna(subset=["year", "state", "candidate_votes", "total_votes"])
    out["year"] = out["year"].astype(int)
    out["vote_share"] = out["candidate_votes"] / out["total_votes"]
    return out


def _read(path: Path) -> pd.DataFrame:
    sep = "\t" if path.suffix.lower() in {".tab", ".tsv"} else ","
    return pd.read_csv(path, sep=sep, dtype=str, low_memory=False)


def fetch(vintage: str, cfg: dict) -> list[Path]:
    vdir = vintage_dir(NAME, vintage)
    files = pick_up_inbox(NAME, vdir, ("*.csv", "*.tab", "*.tsv"))
    if not files:
        raise RuntimeError(
            f"{NAME}: no files. Download the House, Senate and president datasets from "
            f"Harvard Dataverse (see config/sources.yaml) into data/inbox/{NAME}/"
        )
    return files


def clean(vintage: str, cfg: dict) -> pd.DataFrame:
    vdir = vintage_dir(NAME, vintage, create=False)
    frames = [
        standardize(_read(p))
        for p in sorted(vdir.glob("*"))
        if p.suffix.lower() in {".csv", ".tab", ".tsv"}
    ]
    if not frames:
        raise RuntimeError(f"no result files found in {vdir}")
    out = pd.concat(frames, ignore_index=True)
    out["vintage"] = vintage
    return out
