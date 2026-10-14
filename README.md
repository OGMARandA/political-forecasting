# OGMA Political Forecasting: data architecture and pipelines

Shared data layer for the 2026 midterm forecasts (House, Senate, governors) and the regional
credit-stress index (CSI). Built October 14, 2026. See the project plan doc for scope and timeline.

## How it fits together

```
config/sources.yaml          every source: URL, cadence, geography, terms, verification status
data/inbox/<source>/         files you download by hand drop here
data/raw/<source>/<date>/    immutable downloads + manifest.json (URL, SHA-256, size, time)
data/clean/<table>.csv       standardized tables, every row stamped with its vintage
pipelines/                   one ingest module per source, checks.py, run_all.py
models/csi.py                credit-stress index (config/csi_weights.yaml holds the fixed weights)
output/run_log.json          what the last run did and any problems
tests/                       27 tests; run `python -m pytest`
```

`data/` and `output/run_log.json` are git-ignored (see `.gitignore`): code and config live in git,
downloaded data does not.

Rules the design enforces:
- **Raw is immutable.** Files are stored once, hashed, and never edited.
- **Vintages.** Every clean row carries the retrieval date. Backtests use `as_of(df, date, keys)`
  to see only what was published by then.
- **Fail loudly.** Parsers raise with the columns they found when a file layout changes, and
  `checks.py` blocks a table from being saved if it has missing columns, duplicates, bad state
  codes or non-numeric values.
- **One bad source never blocks the rest.** `run_all` isolates failures and exits 1 if any occurred.

## Run it

```
pip install -r requirements.txt
export FRED_API_KEY=...            # free key from fred.stlouisfed.org
python -m pipelines.run_all        # every enabled source
python -m pipelines.run_all --sources fec nyfed_hhdc
python -m pipelines.run_all --skip-fetch      # re-clean the latest raw vintage
python -m pytest
```

Set `PF_ROOT` to point at a different project root (the tests do).

## First live run checklist (all sources start "unverified")

Built without access to the live sites, so confirm each of these on the first run:

1. **fred_state:** set `FRED_API_KEY`; confirm state series IDs (`{ST}UR`, `{ST}STHPI`).
2. **nyfed_hhdc:** confirm the download URL template or place the file in `data/inbox/nyfed_hhdc/`;
   inspect the state-level sheet, then replace the placeholder `column_map` in `sources.yaml`.
3. **fec:** confirm the weball file layout against FEC's data dictionary.
4. **mit_results:** download House, Senate and president files from Harvard Dataverse into
   `data/inbox/mit_results/`.
5. **generic_ballot:** download the poll database from the Silver Bulletin page into
   `data/inbox/generic_ballot/`, then confirm the `column_map`.
6. **bureau_public:** archive published TransUnion, Equifax and Experian reports (add them under
   `documents:`) and transcribe state tables into `data/inbox/bureau_public/*.csv`.

Then update each source's `status` to `verified`.

## Data terms

Use published releases only, with attribution, and check each source's terms before
republishing figures. Do not use data from licensed products or client work.

## Not built yet

District-level House lean on the new maps, early-vote and turnout feeds, the national
environment model, and the simulation engine. The CSI calculation exists; its inputs come from
the NY Fed and bureau tables once the first live pulls are confirmed.
