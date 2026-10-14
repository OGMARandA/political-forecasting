import json

import pandas as pd
import pytest

from pipelines import common


@pytest.fixture(autouse=True)
def project_root(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_ROOT", str(tmp_path))
    return tmp_path


def test_vintage_dir_and_latest(project_root):
    common.vintage_dir("src", "2026-01-05")
    common.vintage_dir("src", "2026-03-01")
    assert common.latest_vintage("src") == "2026-03-01"
    assert common.latest_vintage("nothing") is None


def test_manifest_records_hash_and_redacts_secrets(project_root):
    vdir = common.vintage_dir("src", "2026-01-05")
    (vdir / "a.json").write_text("{}")
    common.add_manifest_entry(
        vdir, "a.json", url="https://example.org/x", params={"api_key": "SECRET", "id": "1"}
    )
    manifest = json.loads((vdir / "manifest.json").read_text())
    entry = manifest["files"][0]
    assert entry["params"] == {"api_key": "REDACTED", "id": "1"}
    assert len(entry["sha256"]) == 64
    assert "SECRET" not in json.dumps(manifest)


def test_inbox_pickup_copies_and_records(project_root):
    inbox = common.inbox_root() / "src"
    inbox.mkdir(parents=True)
    (inbox / "p.csv").write_text("a,b\n1,2\n")
    vdir = common.vintage_dir("src", "2026-01-05")
    found = common.pick_up_inbox("src", vdir, ("*.csv",))
    assert [p.name for p in found] == ["p.csv"]
    manifest = json.loads((vdir / "manifest.json").read_text())
    assert manifest["files"][0]["url"] == "inbox"


def test_append_clean_dedupes_on_keys_and_vintage(project_root):
    a = pd.DataFrame({"state": ["CO"], "series": ["u"], "date": ["2026-01-01"],
                      "value": [4.0], "vintage": ["2026-02-01"]})
    common.append_clean("t", a, ["state", "series", "date"])
    # same key and vintage with a corrected value: newest write wins
    b = a.assign(value=[4.5])
    common.append_clean("t", b, ["state", "series", "date"])
    # same key, later vintage: both kept
    c = a.assign(value=[4.7], vintage=["2026-03-01"])
    path = common.append_clean("t", c, ["state", "series", "date"])
    out = pd.read_csv(path)
    assert len(out) == 2
    assert sorted(out["value"]) == [4.5, 4.7]


def test_as_of_returns_point_in_time_view(project_root):
    df = pd.DataFrame(
        {
            "state": ["CO", "CO", "CO", "TX"],
            "date": ["2026-01-01"] * 4,
            "value": [4.0, 4.5, 5.0, 3.0],
            "vintage": ["2026-02-01", "2026-03-01", "2026-04-01", "2026-03-15"],
        }
    )
    view = common.as_of(df, "2026-03-20", ["state", "date"]).set_index("state")
    assert view.loc["CO", "value"] == 4.5   # April revision not yet known
    assert view.loc["TX", "value"] == 3.0
    early = common.as_of(df, "2026-02-15", ["state", "date"])
    assert list(early["state"]) == ["CO"]     # TX did not exist yet


def test_append_clean_requires_vintage(project_root):
    with pytest.raises(ValueError):
        common.append_clean("t", pd.DataFrame({"a": [1]}), ["a"])
