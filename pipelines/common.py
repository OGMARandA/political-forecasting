"""Shared plumbing: paths, vintage-aware storage, downloads and manifests.

Every downloaded file lands once, untouched, under data/raw/<source>/<YYYY-MM-DD>/
with a manifest entry (URL, SHA-256, size, retrieval time). Cleaned tables carry a
`vintage` column so a backtest can ask "what did we know on date X?" with as_of().
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

USER_AGENT = "OGMA-political-forecasting/0.1 (research; contact via OGMAra.com)"
SECRET_PARAMS = {"api_key", "apikey", "key", "token"}


# ---------------------------------------------------------------- paths
def root() -> Path:
    return Path(os.environ.get("PF_ROOT", Path(__file__).resolve().parents[1]))


def raw_root() -> Path:
    return root() / "data" / "raw"


def clean_root() -> Path:
    return root() / "data" / "clean"


def inbox_root() -> Path:
    return root() / "data" / "inbox"


def output_root() -> Path:
    return root() / "output"


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def vintage_dir(source: str, vintage: str | None = None, create: bool = True) -> Path:
    d = raw_root() / source / (vintage or today())
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def latest_vintage(source: str) -> str | None:
    base = raw_root() / source
    if not base.exists():
        return None
    dirs = sorted(p.name for p in base.iterdir() if p.is_dir())
    return dirs[-1] if dirs else None


# ---------------------------------------------------------------- manifests
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _redact(params: dict | None) -> dict:
    return {
        k: ("REDACTED" if k.lower() in SECRET_PARAMS else v)
        for k, v in (params or {}).items()
    }


def add_manifest_entry(
    vdir: Path, filename: str, *, url: str = "", params: dict | None = None, note: str = ""
) -> None:
    mpath = vdir / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {"files": []}
    p = vdir / filename
    manifest["files"] = [e for e in manifest["files"] if e["filename"] != filename]
    manifest["files"].append(
        {
            "filename": filename,
            "url": url,
            "params": _redact(params),
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "note": note,
        }
    )
    mpath.write_text(json.dumps(manifest, indent=2))


# ---------------------------------------------------------------- acquisition
def download(
    url: str,
    vdir: Path,
    filename: str | None = None,
    *,
    params: dict | None = None,
    retries: int = 3,
    timeout: int = 120,
    headers: dict | None = None,
) -> Path:
    """Stream a URL to vdir/filename, retrying, and record it in the manifest.

    Error messages never include the request URL, so API keys in query strings
    cannot leak into logs.
    """
    filename = filename or (url.rstrip("/").split("/")[-1].split("?")[0] or "download")
    dest = vdir / filename
    tmp = dest.with_suffix(dest.suffix + ".part")
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    last = "unknown error"
    for attempt in range(1, retries + 1):
        try:
            with requests.get(
                url, params=params, headers=hdrs, timeout=timeout, stream=True
            ) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            tmp.replace(dest)
            add_manifest_entry(vdir, filename, url=url, params=params)
            return dest
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            last = f"{type(exc).__name__} status={status}"
            if tmp.exists():
                tmp.unlink()
            if attempt < retries:
                time.sleep(min(2**attempt, 10))
    raise RuntimeError(f"download failed after {retries} attempts for {filename}: {last}")


def pick_up_inbox(source: str, vdir: Path, patterns: tuple[str, ...] = ("*",)) -> list[Path]:
    """Copy manually placed files from data/inbox/<source>/ into the raw vintage."""
    src = inbox_root() / source
    found: list[Path] = []
    if not src.exists():
        return found
    for pat in patterns:
        for p in sorted(src.glob(pat)):
            if p.is_file():
                dest = vdir / p.name
                shutil.copy2(p, dest)
                add_manifest_entry(vdir, p.name, url="inbox", note="manually placed file")
                found.append(dest)
    return found


# ---------------------------------------------------------------- clean tables
def _as_text(df: pd.DataFrame) -> pd.DataFrame:
    out = df.astype(object)
    out = out.where(df.notna(), "")
    return out.astype(str)


def append_clean(name: str, df: pd.DataFrame, keys: list[str]) -> Path:
    """Append a cleaned table, de-duplicating on keys + vintage (newest write wins)."""
    if "vintage" not in df.columns:
        raise ValueError(f"{name}: clean tables must carry a 'vintage' column")
    path = clean_root() / f"{name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    new = _as_text(df)
    if path.exists():
        old = pd.read_csv(path, dtype=str, keep_default_na=False)
        combined = pd.concat([old, new], ignore_index=True)
    else:
        combined = new
    combined = combined.drop_duplicates(subset=keys + ["vintage"], keep="last")
    combined = combined.sort_values(keys + ["vintage"]).reset_index(drop=True)
    combined.to_csv(path, index=False)
    return path


def read_clean(name: str) -> pd.DataFrame:
    return pd.read_csv(clean_root() / f"{name}.csv")


def as_of(
    df: pd.DataFrame, as_of_date: str, keys: list[str], vintage_col: str = "vintage"
) -> pd.DataFrame:
    """Return, for each key, the latest row whose vintage is on or before as_of_date.

    This is the point-in-time view backtests must use so that later revisions
    cannot leak into earlier forecasts.
    """
    stamp = pd.to_datetime(df[vintage_col])
    sub = df.loc[stamp <= pd.Timestamp(as_of_date)].copy()
    sub["_v"] = pd.to_datetime(sub[vintage_col])
    sub = sub.sort_values("_v").groupby(keys, dropna=False).tail(1)
    return sub.drop(columns="_v").reset_index(drop=True)
