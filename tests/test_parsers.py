import zipfile
from datetime import date

import pandas as pd
import pytest

from pipelines import bureau_public, fec, fred_state, generic_ballot, mit_results, nyfed_hhdc
from pipelines.geo import STATES, to_postal


def test_states_reference_is_complete():
    assert len(STATES) == 51
    assert to_postal("Colorado") == "CO" and to_postal("co") == "CO"
    assert to_postal("Atlantis") is None


def test_fred_parse_drops_missing_values():
    payload = {"observations": [
        {"date": "2026-01-01", "value": "4.1"},
        {"date": "2026-02-01", "value": "."},
        {"date": "2026-03-01", "value": "4.3"},
    ]}
    df = fred_state.parse_observations(payload, "CO", "unemployment_rate")
    assert list(df["value"]) == [4.1, 4.3]
    assert set(df["state"]) == {"CO"}


def test_nyfed_expected_quarter_respects_release_lag():
    # Q2 2026 ended Jun 30; released Aug 11 (42 days). On Aug 1 it is not out yet.
    assert nyfed_hhdc.latest_expected_quarter(date(2026, 8, 1)) == (2026, 1)
    assert nyfed_hhdc.latest_expected_quarter(date(2026, 8, 12)) == (2026, 2)
    assert nyfed_hhdc.latest_expected_quarter(date(2026, 1, 20)) == (2025, 3)


def test_nyfed_standardize_wide_to_long():
    df = pd.DataFrame({
        "state": ["CO", "Texas", "ZZ"],
        "period": ["2026Q2"] * 3,
        "c1": [1.0, 2.0, 9.0],
        "c2": [3.0, None, 9.0],
    })
    out = nyfed_hhdc.standardize(df, {"c1": "card_early_delinquency", "c2": "auto_early_delinquency"},
                                 "state", "period")
    assert set(out["state"]) == {"CO", "TX"}            # unknown state dropped
    assert len(out) == 3                                 # missing value dropped
    assert set(out["metric"]) == {"card_early_delinquency", "auto_early_delinquency"}


def test_nyfed_standardize_fails_loudly_on_layout_change():
    df = pd.DataFrame({"state": ["CO"], "period": ["2026Q2"], "other": [1]})
    with pytest.raises(ValueError, match="Columns present"):
        nyfed_hhdc.standardize(df, {"c1": "m"}, "state", "period")


def test_fec_parse_weball(tmp_path):
    row = ["H8CO00001", "SMITH, JANE", "C", "DEM", "DEM", "1500.50", "0", "900", "0", "0",
           "600.5", "0", "0", "0", "0", "0", "0", "1400", "CO", "08", "", "", "", "", "",
           "0", "0", "09/30/2026", "0", "0"]
    p = tmp_path / "weball26.zip"
    with zipfile.ZipFile(p, "w") as z:      # FEC ships a zip holding one text file
        z.writestr("weball26.txt", "|".join(row) + "\n")
    df = fec.parse_weball(p, 2026)
    assert df.loc[0, "office"] == "house"
    assert df.loc[0, "receipts"] == 1500.50
    assert df.loc[0, "state"] == "CO" and df.loc[0, "district"] == "08"


def test_mit_standardize():
    raw = pd.DataFrame({
        "year": ["2022", "2022"], "state_po": ["CO", "CO"], "office": ["US HOUSE", "US HOUSE"],
        "district": ["008", "008"], "candidate": ["A", "B"], "party": ["DEMOCRAT", "REPUBLICAN"],
        "candidatevotes": ["51", "49"], "totalvotes": ["100", "100"], "stage": ["GEN", "GEN"],
    })
    out = mit_results.standardize(raw)
    assert list(out["office"]) == ["house", "house"]
    assert out["vote_share"].tolist() == [0.51, 0.49]


def test_generic_ballot_standardize_computes_margin():
    raw = pd.DataFrame({
        "pollster": ["X"], "end_date": ["2026-10-05"], "population": ["lv"],
        "dem": [52.0], "rep": [44.0],
    })
    out = generic_ballot.standardize(raw)
    assert out.loc[0, "margin"] == 8.0


def test_bureau_standardize_requires_schema_and_cleans():
    good = pd.DataFrame({"bureau": [" TransUnion "], "state": ["Colorado"], "metric": ["m"],
                         "period": ["2026Q2"], "value": ["1.5"], "source_report": ["r.pdf"]})
    out = bureau_public.standardize(good)
    assert out.loc[0, "bureau"] == "transunion" and out.loc[0, "state"] == "CO"
    with pytest.raises(ValueError):
        bureau_public.standardize(good.drop(columns=["source_report"]))
