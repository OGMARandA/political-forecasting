"""End-to-end: inbox files -> raw vintage -> clean table, with isolation between sources."""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from pipelines import run_all
from pipelines.common import clean_root, inbox_root

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_ROOT", str(tmp_path))
    (tmp_path / "config").mkdir()
    shutil.copy(PROJECT / "config" / "sources.yaml", tmp_path / "config" / "sources.yaml")
    return tmp_path


def _drop(source: str, name: str, df: pd.DataFrame) -> None:
    d = inbox_root() / source
    d.mkdir(parents=True, exist_ok=True)
    df.to_csv(d / name, index=False)


def test_pipeline_ingests_inbox_sources_and_isolates_failures(sandbox):
    _drop("generic_ballot", "polls.csv", pd.DataFrame({
        "pollster": ["A", "B"], "end_date": ["2026-10-01", "2026-10-03"],
        "population": ["lv", "rv"], "dem": [51, 49], "rep": [43, 44]}))
    _drop("bureau_public", "tu.csv", pd.DataFrame({
        "bureau": ["transunion"], "state": ["CO"], "metric": ["card_90plus_dq"],
        "period": ["2026Q2"], "value": [1.9], "source_report": ["tu_q2_2026.pdf"]}))

    # mit_results has no inbox files, so it must fail without stopping the others.
    code = run_all.main(["--sources", "generic_ballot", "bureau_public", "mit_results",
                         "--vintage", "2026-10-14"])
    assert code == 1

    log = json.loads((sandbox / "output" / "run_log.json").read_text())
    status = {r["source"]: r["status"] for r in log["results"]}
    assert status == {"generic_ballot": "ok", "bureau_public": "ok", "mit_results": "error"}

    polls = pd.read_csv(clean_root() / "generic_ballot_polls.csv")
    assert sorted(polls["margin"]) == [5.0, 8.0]
    assert (polls["vintage"] == "2026-10-14").all()
    assert (sandbox / "data" / "raw" / "generic_ballot" / "2026-10-14" / "manifest.json").exists()


def test_rerun_same_vintage_is_idempotent(sandbox):
    _drop("generic_ballot", "polls.csv", pd.DataFrame({
        "pollster": ["A"], "end_date": ["2026-10-01"], "population": ["lv"],
        "dem": [51], "rep": [43]}))
    for _ in range(2):
        assert run_all.main(["--sources", "generic_ballot", "--vintage", "2026-10-14"]) == 0
    assert len(pd.read_csv(clean_root() / "generic_ballot_polls.csv")) == 1


def test_unknown_source_is_rejected(sandbox):
    assert run_all.main(["--sources", "nope"]) == 2
