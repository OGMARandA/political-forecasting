# Data dictionary

All clean tables live in `data/clean/<table>.csv`. Every table has a `vintage` column
(YYYY-MM-DD, the day the raw file was retrieved). Never read a clean table directly in a
backtest: use `pipelines.common.as_of(df, date, keys)` so that later revisions cannot leak
into earlier forecasts.

State codes are USPS postal codes (CO, TX). `US` is allowed for national rows.

## state_macro (from `fred_state`)
Key: state, series, date (+ vintage)

| Column | Meaning |
| --- | --- |
| state | Postal code |
| series | `unemployment_rate` (percent) or `house_price_index` (FHFA, index) |
| date | Observation date (first day of period) |
| value | Observation |
| vintage | Retrieval date |

## hhdc_state (from `nyfed_hhdc`)
Key: state, period, metric (+ vintage). Source: NY Fed Consumer Credit Panel (Equifax data).

| Column | Meaning |
| --- | --- |
| state | Postal code |
| period | Quarter, e.g. `2026Q2` |
| metric | Our name, mapped in `config/sources.yaml` (e.g. `card_early_delinquency`, `mortgage_serious_delinquency_flow`) |
| value | Percent of balances (confirm units on first live file) |

Metric definitions follow the NY Fed: early delinquency = newly 30+ days late; serious delinquency
flow = balances newly 90+ days late divided by balances current or under 90 days late the previous
quarter. The student loan series is distorted by the re-reporting of defaulted debt.

## fec_candidates (from `fec`)
Key: cand_id, cycle (+ vintage)

| Column | Meaning |
| --- | --- |
| cand_id | FEC candidate ID (first letter H, S or P sets `office`) |
| cycle | Two-year election cycle |
| name, party | Candidate name and party code as filed |
| incumbency | I incumbent, C challenger, O open seat |
| office | house, senate, president |
| state, district | Office state and district |
| receipts, disbursements, cash_on_hand, individual_contributions | US dollars |
| coverage_end | Last reporting period end date |

## election_results (from `mit_results`)
Key: year, state, office, district, candidate, stage (+ vintage)

| Column | Meaning |
| --- | --- |
| year | Election year |
| state, office, district | Race identifiers; office is house, senate or president |
| stage | `gen` or `pri` and similar, as published |
| special | Special election flag as published |
| candidate, party | As published |
| candidate_votes, total_votes | Votes |
| vote_share | candidate_votes / total_votes |

## generic_ballot_polls (from `generic_ballot`)
Key: pollster, end_date, population (+ vintage)

| Column | Meaning |
| --- | --- |
| pollster | Pollster name |
| end_date | Last field date |
| population | lv (likely voters), rv (registered voters) or as published |
| dem, rep | Percent supporting each party |
| margin | dem - rep, in points; positive means a Democratic lead |

## bureau_state_metrics (from `bureau_public`)
Curated CSV schema for transcribed published tables. Key: bureau, state, metric, period (+ vintage)

| Column | Meaning |
| --- | --- |
| bureau | transunion, equifax or experian |
| state | Postal code |
| metric | Metric name as OGMA standardizes it |
| period | Reporting period, e.g. `2026Q2` |
| value | Number as published |
| source_report | File name of the archived raw report this value came from |

## Credit-stress index output (from `models/csi.py`)
| Column | Meaning |
| --- | --- |
| state, period | Geography and quarter |
| csi | Weighted average of component surprise z-scores; positive means worsening stress |
| n_components | Number of components available for that state-quarter |
