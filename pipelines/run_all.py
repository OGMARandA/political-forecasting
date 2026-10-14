"""Run the pipelines: fetch raw files, clean them, validate, and append to data/clean.

Usage (from the project root):
    python -m pipelines.run_all                      # every enabled source
    python -m pipelines.run_all --sources fec nyfed_hhdc
    python -m pipelines.run_all --skip-fetch         # re-clean the latest raw vintage
    python -m pipelines.run_all --vintage 2026-10-14

A source that fails never blocks the others. Results and problems are written to
output/run_log.json, and the exit code is 1 if any source failed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from .checks import validate
from .common import append_clean, latest_vintage, output_root, today
from .config import load_config
from .registry import SOURCES


def run_source(name: str, cfg: dict, vintage: str, skip_fetch: bool) -> dict:
    mod = SOURCES[name]
    result = {"source": name, "vintage": vintage, "status": "ok", "rows": 0, "issues": []}
    try:
        if skip_fetch:
            vintage = latest_vintage(name) or vintage
            result["vintage"] = vintage
        else:
            result["files"] = [p.name for p in mod.fetch(vintage, cfg)]
        df = mod.clean(vintage, cfg)
        issues = validate(mod.CLEAN_NAME, df)
        if issues:
            result.update(status="failed_checks", issues=issues)
            return result
        append_clean(mod.CLEAN_NAME, df, mod.KEYS)
        result["rows"] = int(len(df))
    except Exception as exc:  # noqa: BLE001 - one bad source must not stop the run
        result.update(status="error", issues=[f"{type(exc).__name__}: {exc}"])
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--sources", nargs="*", help="source names (default: all enabled)")
    ap.add_argument("--vintage", default=None, help="YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--skip-fetch", action="store_true", help="clean the latest raw vintage only")
    args = ap.parse_args(argv)

    config = load_config()
    configured = config.get("sources", {})
    names = args.sources or [
        n for n in SOURCES if configured.get(n, {}).get("enabled", True)
    ]
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        print(f"unknown sources: {unknown}; available: {sorted(SOURCES)}")
        return 2

    vintage = args.vintage or today()
    results = []
    for n in names:
        print(f"== {n}")
        r = run_source(n, configured.get(n, {}), vintage, args.skip_fetch)
        print(f"   {r['status']}  rows={r['rows']}  {'; '.join(r['issues'])}")
        results.append(r)

    out = output_root()
    out.mkdir(parents=True, exist_ok=True)
    log = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "results": results}
    (out / "run_log.json").write_text(json.dumps(log, indent=2))
    return 0 if all(r["status"] == "ok" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
