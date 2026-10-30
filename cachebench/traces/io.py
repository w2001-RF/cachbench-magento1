"""Lecture et écriture des traces au format CSV commun.

Colonnes : ts,op,key,size,cost_ms,kind,cacheable,tags,text
Les tags sont séparés par « | ». Le module PHP écrit exactement ce format.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Iterator

from .request import GET, Request

COLUMNS = ["ts", "op", "key", "size", "cost_ms", "kind", "cacheable", "tags", "text"]


def write_csv(requests: Iterable[Request], path: str | Path) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in requests:
            w.writerow([
                f"{r.ts:.3f}", r.op, r.key, r.size, f"{r.cost_ms:.3f}", r.kind,
                int(r.cacheable), "|".join(r.tags), r.text or "",
            ])
            n += 1
    return n


def read_csv(path: str | Path) -> Iterator[Request]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["ts"] == "ts":
                continue  # en-tête répété (journaux écrits par une ancienne version du module PHP)
            tags = row.get("tags") or ""
            yield Request(
                ts=float(row["ts"]),
                key=row["key"],
                size=int(row.get("size") or 1),
                cost_ms=float(row.get("cost_ms") or 0.0),
                kind=row.get("kind") or "",
                cacheable=(row.get("cacheable") or "1") not in ("0", "false", "False"),
                tags=tuple(t for t in tags.split("|") if t),
                text=row.get("text") or None,
                op=row.get("op") or GET,
            )
