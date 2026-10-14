"""NY Fed Household Debt and Credit: state-level delinquency and balance series.

The NY Fed publishes quarterly (Q2 2026 came out Aug 11, 2026) from its Consumer
Credit Panel, built on Equifax data. This module tries a configured URL template,
and falls back to files you drop into data/inbox/nyfed_hhdc/ (xlsx or csv).

IMPORTANT: the URL template and the column_map in config/sources.yaml are
unverified. Confirm them against a live file on the first run; the parser fails
loudly with the columns it found if the layout does not match.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .common import download, pick_up_inbox, vintage_dir
from .geo import to_postal

NAME = "nyfed_hhdc"
CLEAN_NAME = "hhdc_state"
KEYS = ["state", "period", "metric"]

RELEASE_LAG_DAYS = 42  # reports land roughly six weeks after quarter end


def latest_expected_quarter(today: date) -> tuple[int, int]:
    """Most recent (year, quarter) whose end date plus the release lag has passed."""
    candidates = []
    for year in (today.year - 1, today.year):
        for q, (m, d) in enumerate([(3, 31), (6, 30), (9, 30), (12, 31)], start=1):
            if date(year, m, d) + timedelta(days=RELEASE_LAG_DAYS) <= today:
                candidates.append((year, q))
    return max(candidates)


def fetch(vintage: str, cfg: dict) -> list[Path]:
    vdir = vintage_dir(NAME, vintage)
    files: list[Path] = []
    template = cfg.get("url_template")
    if template:
        year, q = latest_expected_quarter(date.fromisoformat(vintage))
        url = template.format(year=year, q=q)
        try:
            files.append(download(url, vdir, f"hhdc_{year}Q{q}{Path(url).suffix}"))
        except RuntimeError as exc:
            print(f"[{NAME}] direct download failed ({exc}); looking in inbox")
    files += pick_up_inbox(NAME, vdir, ("*.xlsx", "*.xls", "*.csv"))
    if not files:
        raise RuntimeError(
            f"{NAME}: no files. Download the state-level data from the NY Fed Household "
            f"Debt and Credit page and place it in data/inbox/{NAME}/"
        )
    return files


def standardize(
    df: pd.DataFrame, column_map: dict, state_col: str, period_col: str
) -> pd.DataFrame:
    """Wide table (one column per metric) -> long: state, period, metric, value."""
    needed = [state_col, period_col] + list(column_map)
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(
            f"{NAME}: expected columns {missing} not found. Columns present: {list(df.columns)}. "
            "Update column_map in config/sources.yaml."
        )
    long = df[needed].melt(
        id_vars=[state_col, period_col], var_name="raw_metric", value_name="value"
    )
    long["metric"] = long["raw_metric"].map(column_map)
    long["state"] = long[state_col].map(to_postal)
    long = long.rename(columns={period_col: "period"})
    long = long[long["state"].notna()]
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"])
    return long[["state", "period", "metric", "value"]]


def _read(path: Path, cfg: dict) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path, sheet_name=cfg.get("sheet", 0), header=cfg.get("header_row", 0))


def clean(vintage: str, cfg: dict) -> pd.DataFrame:
    vdir = vintage_dir(NAME, vintage, create=False)
    frames = []
    for p in sorted(vdir.glob("*")):
        if p.suffix.lower() in {".xlsx", ".xls", ".csv"}:
            frames.append(
                standardize(
                    _read(p, cfg),
                    cfg["column_map"],
                    cfg.get("state_col", "state"),
                    cfg.get("period_col", "period"),
                )
            )
    if not frames:
        raise RuntimeError(f"no data files found in {vdir}")
    out = pd.concat(frames, ignore_index=True)
    out["vintage"] = vintage
    return out
