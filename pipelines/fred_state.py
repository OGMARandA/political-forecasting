"""State macro series from FRED: unemployment rate and FHFA house price index.

Needs a free FRED API key in the FRED_API_KEY environment variable. FRED also
serves historical vintages (ALFRED) through realtime_start / realtime_end; set
`realtime_vintage: true` in config to request each series as known on the
vintage date, which is what historical backtests should use.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from .common import download, vintage_dir
from .geo import STATES

NAME = "fred_state"
CLEAN_NAME = "state_macro"
KEYS = ["state", "series", "date"]

API = "https://api.stlouisfed.org/fred/series/observations"
# FRED series templates; {st} is the state postal code.
SERIES = {
    "unemployment_rate": "{st}UR",
    "house_price_index": "{st}STHPI",
}


def parse_observations(payload: dict, state: str, series: str) -> pd.DataFrame:
    """Turn a FRED observations payload into rows; '.' (missing) values are dropped."""
    rows = []
    for obs in payload.get("observations", []):
        raw = obs.get("value")
        if raw in (None, ".", ""):
            continue
        rows.append({"state": state, "series": series, "date": obs["date"], "value": float(raw)})
    return pd.DataFrame(rows, columns=["state", "series", "date", "value"])


def fetch(vintage: str, cfg: dict) -> list[Path]:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY is not set (free key: fred.stlouisfed.org/docs/api)")
    vdir = vintage_dir(NAME, vintage)
    realtime = bool(cfg.get("realtime_vintage", False))
    files: list[Path] = []
    for st in STATES:
        for series, template in SERIES.items():
            params = {
                "series_id": template.format(st=st),
                "api_key": key,
                "file_type": "json",
                "observation_start": cfg.get("observation_start", "1976-01-01"),
            }
            if realtime:
                params["realtime_start"] = vintage
                params["realtime_end"] = vintage
            files.append(download(API, vdir, f"{st}_{series}.json", params=params))
    return files


def clean(vintage: str, cfg: dict) -> pd.DataFrame:
    vdir = vintage_dir(NAME, vintage, create=False)
    frames = []
    for st in STATES:
        for series in SERIES:
            p = vdir / f"{st}_{series}.json"
            if p.exists():
                frames.append(parse_observations(json.loads(p.read_text()), st, series))
    if not frames:
        raise RuntimeError(f"no FRED files found in {vdir}")
    out = pd.concat(frames, ignore_index=True)
    out["vintage"] = vintage
    return out
