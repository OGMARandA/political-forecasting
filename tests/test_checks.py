import pandas as pd

from pipelines.checks import validate


def _macro(**over):
    df = pd.DataFrame({"state": ["CO", "TX"], "series": ["u", "u"], "date": ["2026-01-01"] * 2,
                       "value": [4.0, 3.5], "vintage": ["2026-02-01"] * 2})
    for k, v in over.items():
        df[k] = v
    return df


def test_clean_table_passes():
    assert validate("state_macro", _macro()) == []


def test_flags_empty_unknown_and_missing_columns():
    assert "empty" in validate("state_macro", _macro().iloc[0:0])[0]
    assert "no schema" in validate("nope", _macro())[0]
    assert "missing required" in validate("state_macro", _macro().drop(columns=["value"]))[0]


def test_flags_bad_state_duplicates_and_non_numeric():
    issues = validate("state_macro", _macro(state=["ZZ", "ZZ"]))
    assert any("unrecognised state" in i for i in issues)
    assert any("duplicate" in i for i in issues)
    issues = validate("state_macro", _macro(value=["4.0", "oops"]))
    assert any("non-numeric" in i for i in issues)
