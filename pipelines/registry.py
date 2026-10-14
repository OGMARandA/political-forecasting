"""Registry of ingest modules. Each exposes NAME, CLEAN_NAME, KEYS, fetch(), clean()."""
from __future__ import annotations

from . import bureau_public, fec, fred_state, generic_ballot, mit_results, nyfed_hhdc

SOURCES = {
    m.NAME: m
    for m in (fred_state, nyfed_hhdc, fec, mit_results, generic_ballot, bureau_public)
}
