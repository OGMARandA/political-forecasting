import numpy as np
import pandas as pd
import pytest

from models.csi import build_csi

QUARTERS = [str(p) for p in pd.period_range("2019Q1", "2025Q4", freq="Q")]


def _panel(spike_state="AA", spike_from="2025Q3", seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for st in ["AA", "BB", "CC"]:
        level = 5.0
        for q in QUARTERS:
            level += rng.normal(0, 0.1)
            bump = 3.0 if (st == spike_state and q >= spike_from) else 0.0
            rows.append({"state": st, "component": "card_early_delinquency",
                         "period": q, "value": level + bump})
    return pd.DataFrame(rows)


W = {"card_early_delinquency": 1.0}


def test_regional_deterioration_scores_high_and_peers_do_not():
    out = build_csi(_panel(), W)
    last = out[out["period"] == "2025Q4"].set_index("state")["csi"]
    assert last["AA"] > 2.0
    assert last["BB"] < 2.0 and last["CC"] < 2.0
    assert last["AA"] > last["BB"] and last["AA"] > last["CC"]


def test_no_lookahead_future_data_cannot_change_past_scores():
    base = build_csi(_panel(), W)
    earlier = base[base["period"] == "2024Q4"].set_index("state")["csi"]
    altered_panel = _panel()
    mask = altered_panel["period"] >= "2025Q1"
    altered_panel.loc[mask, "value"] += 100.0      # wild future values
    altered = build_csi(altered_panel, W)
    after = altered[altered["period"] == "2024Q4"].set_index("state")["csi"]
    pd.testing.assert_series_equal(earlier, after)


def test_as_of_period_truncates():
    out = build_csi(_panel(), W, as_of_period="2024Q2")
    assert out["period"].max() == "2024Q2"


def test_negative_weight_flips_direction():
    pos = build_csi(_panel(), {"card_early_delinquency": 1.0})
    neg = build_csi(_panel(), {"card_early_delinquency": -1.0})
    m = pos.merge(neg, on=["state", "period"], suffixes=("_p", "_n"))
    np.testing.assert_allclose(m["csi_p"], -m["csi_n"])


def test_needs_history_before_scoring_and_rejects_gaps():
    out = build_csi(_panel(), W, min_history=8)
    assert out["period"].min() >= "2021Q1"          # 4 lag + 8 history quarters needed
    gappy = _panel()
    gappy = gappy[gappy["period"] != "2022Q2"]
    with pytest.raises(ValueError, match="non-contiguous"):
        build_csi(gappy, W)


def test_missing_component_renormalizes_weights():
    p = _panel()
    p2 = p.assign(component="auto_early_delinquency")
    both = pd.concat([p, p2.iloc[: len(p2) // 2 * 0]])  # auto absent entirely
    out = build_csi(both, {"card_early_delinquency": 1.0, "auto_early_delinquency": 1.0})
    assert (out["n_components"] == 1).all()
