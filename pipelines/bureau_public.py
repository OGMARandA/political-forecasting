"""Publicly released credit bureau statistics (TransUnion, Equifax, Experian).

Bureaus publish state-level delinquency and credit-health figures inside reports,
press releases and PDFs, not as stable machine-readable feeds. This module does
two things:

1. fetch(): downloads the report pages and PDFs listed in config/sources.yaml so
   the raw evidence is stored with a hash and retrieval date.
2. clean(): ingests curated CSVs placed in data/inbox/bureau_public/ in a fixed
   schema (bureau, state, metric, period, value, source_report). A person or an
   extraction step transcribes the tables, and the source_report column ties each
   number back to a stored raw file.

Use published releases only, with attribution, and check each bureau's terms
before redistributing figures. Nothing from licensed products or client work.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import download, pick_up_inbox, vintage_dir
from .geo import to_postal

NAME = "bureau_public"
CLEAN_NAME = "bureau_state_metrics"
KEYS = ["bureau", "state", "metric", "period"]

REQUIRED = ["bureau", "state", "metric", "period", "value", "source_report"]


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{NAME}: curated CSV is missing columns {missing}")
    out = df[REQUIRED].copy()
    out["state"] = out["state"].map(to_postal)
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["state", "value"])
    out["bureau"] = out["bureau"].str.strip().str.lower()
    return out


def fetch(vintage: str, cfg: dict) -> list[Path]:
    vdir = vintage_dir(NAME, vintage)
    files: list[Path] = []
    for i, doc in enumerate(cfg.get("documents", [])):
        name = doc.get("filename") or f"doc_{i}{Path(doc['url']).suffix or '.html'}"
        try:
            files.append(download(doc["url"], vdir, name))
        except RuntimeError as exc:
            print(f"[{NAME}] skipped {doc['url']}: {exc}")
    files += pick_up_inbox(NAME, vdir, ("*.csv",))
    if not any(p.suffix == ".csv" for p in files):
        raise RuntimeError(
            f"{NAME}: no curated CSV found. Transcribe published state tables into "
            f"data/inbox/{NAME}/*.csv using the schema in docs/data_dictionary.md"
        )
    return files


def clean(vintage: str, cfg: dict) -> pd.DataFrame:
    vdir = vintage_dir(NAME, vintage, create=False)
    frames = [standardize(pd.read_csv(p)) for p in sorted(vdir.glob("*.csv"))]
    if not frames:
        raise RuntimeError(f"no curated CSV found in {vdir}")
    out = pd.concat(frames, ignore_index=True)
    out["vintage"] = vintage
    return out
