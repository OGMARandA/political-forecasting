"""Credit-stress index (CSI): a state-level score of how much household credit
conditions worsened over the past year, relative to that state's own history.

Method (per state s, component k, quarter t):
  1. change      = value_t - value_{t-4}                 (one-year change)
  2. surprise z  = (change - mean of PRIOR changes) / std of PRIOR changes
                   (expanding window that excludes t, so nothing from the future
                    can leak into the score; needs `min_history` quarters first)
  3. clip z to +/- `clip`
  4. CSI_{s,t}   = sum_k w_k * z_k / sum_k |w_k|, over components available at t

Weights are fixed in config/csi_weights.yaml BEFORE looking at election results.
A positive weight means "higher value = more stress"; use a negative weight for
a series where higher means less stress.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def load_weights(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def _check_contiguous(p: pd.DataFrame) -> None:
    bad = []
    for (state, comp), g in p.groupby(["state", "component"]):
        if (g["ord"].diff().dropna() != 1).any():
            bad.append((state, comp))
    if bad:
        raise ValueError(f"non-contiguous quarters for (state, component): {bad[:5]}")


def build_csi(
    panel: pd.DataFrame,
    weights: dict,
    *,
    lag: int = 4,
    min_history: int = 8,
    clip: float = 4.0,
    as_of_period: str | None = None,
) -> pd.DataFrame:
    """panel columns: state, component, period ('2025Q2'), value. Returns state, period, csi, n_components."""
    p = panel.copy()
    p["q"] = pd.PeriodIndex(p["period"], freq="Q")
    if as_of_period is not None:
        p = p[p["q"] <= pd.Period(as_of_period, freq="Q")]
    p["ord"] = p["q"].map(lambda x: x.ordinal)
    p = p.sort_values(["state", "component", "ord"]).reset_index(drop=True)
    _check_contiguous(p)

    grp = p.groupby(["state", "component"])["value"]
    p["chg"] = grp.diff(lag)

    def prior_z(s: pd.Series) -> pd.Series:
        mean = s.expanding(min_periods=min_history).mean().shift(1)
        std = s.expanding(min_periods=min_history).std().shift(1)
        return (s - mean) / std.replace(0.0, np.nan)

    p["z"] = p.groupby(["state", "component"])["chg"].transform(prior_z).clip(-clip, clip)

    wide = p.pivot_table(
        index=["state", "ord"], columns="component", values="z", aggfunc="first", dropna=False
    )
    w = pd.Series(weights).astype(float)
    w = w[[c for c in w.index if c in wide.columns and w[c] != 0]]
    if w.empty:
        raise ValueError("no weighted components are present in the panel")
    wide = wide[w.index]
    avail = wide.notna()
    num = (wide.fillna(0.0) * w).sum(axis=1)
    den = (avail * w.abs()).sum(axis=1)
    out = pd.DataFrame(
        {"csi": num / den.replace(0.0, np.nan), "n_components": avail.sum(axis=1)}
    ).reset_index()
    out["period"] = out["ord"].map(lambda o: str(pd.Period(ordinal=int(o), freq="Q")))
    out = out.dropna(subset=["csi"])
    return out[["state", "period", "csi", "n_components"]].reset_index(drop=True)
