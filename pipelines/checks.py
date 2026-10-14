"""Schema and sanity checks applied to every clean table before it is saved."""
from __future__ import annotations

import pandas as pd

from .geo import POSTAL_CODES

SPECS: dict[str, dict] = {
    "state_macro": {
        "required": ["state", "series", "date", "value", "vintage"],
        "keys": ["state", "series", "date"],
        "state_col": "state",
        "numeric": ["value"],
    },
    "hhdc_state": {
        "required": ["state", "period", "metric", "value", "vintage"],
        "keys": ["state", "period", "metric"],
        "state_col": "state",
        "numeric": ["value"],
    },
    "fec_candidates": {
        "required": ["cand_id", "cycle", "name", "party", "office", "receipts", "vintage"],
        "keys": ["cand_id", "cycle"],
        "state_col": None,
        "numeric": ["receipts"],
    },
    "election_results": {
        "required": ["year", "state", "office", "district", "candidate", "party",
                     "candidate_votes", "total_votes", "vintage"],
        "keys": ["year", "state", "office", "district", "candidate", "stage"],
        "state_col": "state",
        "numeric": ["candidate_votes", "total_votes"],
    },
    "generic_ballot_polls": {
        "required": ["pollster", "end_date", "population", "dem", "rep", "margin", "vintage"],
        "keys": ["pollster", "end_date", "population"],
        "state_col": None,
        "numeric": ["dem", "rep", "margin"],
    },
    "bureau_state_metrics": {
        "required": ["bureau", "state", "metric", "period", "value", "source_report", "vintage"],
        "keys": ["bureau", "state", "metric", "period"],
        "state_col": "state",
        "numeric": ["value"],
    },
}


def validate(name: str, df: pd.DataFrame) -> list[str]:
    """Return a list of human-readable problems; empty means the table passes."""
    if name not in SPECS:
        return [f"no schema registered for table '{name}'"]
    spec = SPECS[name]
    issues: list[str] = []
    if df is None or len(df) == 0:
        return [f"{name}: table is empty"]
    missing = [c for c in spec["required"] if c not in df.columns]
    if missing:
        return [f"{name}: missing required columns {missing}"]
    for col in spec["numeric"]:
        bad = pd.to_numeric(df[col], errors="coerce").isna() & df[col].notna()
        if bad.any():
            issues.append(f"{name}: {int(bad.sum())} non-numeric values in '{col}'")
    key_cols = [k for k in spec["keys"] if k in df.columns]
    dupes = df.duplicated(subset=key_cols + ["vintage"], keep=False)
    if dupes.any():
        issues.append(f"{name}: {int(dupes.sum())} rows duplicate the key {key_cols}+vintage")
    sc = spec.get("state_col")
    if sc:
        allowed = POSTAL_CODES | {"US"}
        bad_states = sorted(set(df[sc].dropna().astype(str)) - allowed)
        if bad_states:
            issues.append(f"{name}: unrecognised state codes {bad_states[:10]}")
    return issues
