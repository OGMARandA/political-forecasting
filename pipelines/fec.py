"""FEC candidate summary files (weball), one per two-year cycle.

Bulk files are pipe-delimited with no header row. The column list below is the
published weball layout; confirm it against FEC's data dictionary on first use.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import download, vintage_dir

NAME = "fec"
CLEAN_NAME = "fec_candidates"
KEYS = ["cand_id", "cycle"]

URL_TEMPLATE = "https://www.fec.gov/files/bulk-downloads/{year}/weball{yy}.zip"

WEBALL_COLUMNS = [
    "CAND_ID", "CAND_NAME", "CAND_ICI", "PTY_CD", "CAND_PTY_AFFILIATION",
    "TTL_RECEIPTS", "TRANS_FROM_AUTH", "TTL_DISB", "TRANS_TO_AUTH", "COH_BOP",
    "COH_COP", "CAND_CONTRIB", "CAND_LOANS", "OTHER_LOANS", "CAND_LOAN_REPAY",
    "OTHER_LOAN_REPAY", "DEBTS_OWED_BY", "TTL_INDIV_CONTRIB", "CAND_OFFICE_ST",
    "CAND_OFFICE_DISTRICT", "SPEC_ELECTION", "PRIM_ELECTION", "RUN_ELECTION",
    "GEN_ELECTION", "GEN_ELECTION_PRECENT", "OTHER_POL_CMTE_CONTRIB",
    "POL_PTY_CONTRIB", "CVG_END_DT", "INDIV_REFUNDS", "CMTE_REFUNDS",
]
OFFICE = {"H": "house", "S": "senate", "P": "president"}


def parse_weball(path: Path, cycle: int) -> pd.DataFrame:
    raw = pd.read_csv(
        path, sep="|", header=None, names=WEBALL_COLUMNS, dtype=str, compression="infer"
    )
    num = lambda s: pd.to_numeric(s, errors="coerce")  # noqa: E731
    out = pd.DataFrame(
        {
            "cand_id": raw["CAND_ID"],
            "cycle": cycle,
            "name": raw["CAND_NAME"],
            "party": raw["CAND_PTY_AFFILIATION"],
            "incumbency": raw["CAND_ICI"],  # I incumbent, C challenger, O open seat
            "office": raw["CAND_ID"].str[0].map(OFFICE),
            "state": raw["CAND_OFFICE_ST"],
            "district": raw["CAND_OFFICE_DISTRICT"],
            "receipts": num(raw["TTL_RECEIPTS"]),
            "disbursements": num(raw["TTL_DISB"]),
            "cash_on_hand": num(raw["COH_COP"]),
            "individual_contributions": num(raw["TTL_INDIV_CONTRIB"]),
            "coverage_end": raw["CVG_END_DT"],
        }
    )
    return out


def fetch(vintage: str, cfg: dict) -> list[Path]:
    vdir = vintage_dir(NAME, vintage)
    files = []
    for year in cfg.get("cycles", [2026, 2024, 2022]):
        url = URL_TEMPLATE.format(year=year, yy=str(year)[-2:])
        files.append(download(url, vdir, f"weball{str(year)[-2:]}.zip"))
    return files


def clean(vintage: str, cfg: dict) -> pd.DataFrame:
    vdir = vintage_dir(NAME, vintage, create=False)
    frames = []
    for p in sorted(vdir.glob("weball*.zip")):
        yy = int(p.stem.replace("weball", ""))
        cycle = 2000 + yy
        frames.append(parse_weball(p, cycle))
    if not frames:
        raise RuntimeError(f"no FEC files found in {vdir}")
    out = pd.concat(frames, ignore_index=True)
    out["vintage"] = vintage
    return out
